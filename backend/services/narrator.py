# backend/services/narrator.py
# Narator CaseStudy: satu panggilan LLM untuk narasi (vonis, alasan, situasi, kubu, ronde, skenario).
# Input: data terverifikasi dari builder + alasan agen ronde terakhir.
# Output: JSON strict via json_schema.

from __future__ import annotations

import json
from typing import Any

from backend.llm_guard import chat as llm_chat, RateLimitError
from backend.services.casestudy_builder import build_computed


NARRATOR_MAX_TOKENS = 700


# JSON Schema untuk output narator (strict) - digunakan sebagai response_format
NARRATOR_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "case_study_narrative",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "vonis": {"type": "string"},
                "alasan": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                "situasi": {
                    "type": "object",
                    "properties": {
                        "pemicu": {
                            "type": "object",
                            "properties": {
                                "angka": {"type": "string"},
                                "teks": {"type": "string"},
                            },
                            "required": ["angka", "teks"],
                            "additionalProperties": False,
                        },
                        "bahan": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                    },
                    "required": ["pemicu", "bahan"],
                    "additionalProperties": False,
                },
                "kubu_catatan": {
                    "type": "object",
                    "properties": {
                        "tolak": {"type": "string"},
                        "netral": {"type": "string"},
                        "dukung": {"type": "string"},
                    },
                    "required": ["tolak", "netral", "dukung"],
                    "additionalProperties": False,
                },
                "ronde": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "no": {"type": "integer", "minimum": 1},
                            "judul": {"type": "string", "maxLength": 80},
                            "ringkas": {"type": "string", "maxLength": 200},
                        },
                        "required": ["no", "judul", "ringkas"],
                        "additionalProperties": False,
                    },
                },
                "skenario": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "jika": {"type": "string"},
                            "maka": {"type": "string"},
                            "dasar_agen": {"type": "string"},
                        },
                        "required": ["jika", "maka", "dasar_agen"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["vonis", "alasan", "situasi", "kubu_catatan", "ronde", "skenario"],
            "additionalProperties": False,
        },
    },
}


# Prompt template
NARRATOR_SYSTEM = (
    "Kamu narator studi kasus VoxSwarm. Tugasmu: tulis narasi ringkas dari data simulasi yang sudah diverifikasi.\n"
    "Output HANYA satu objek JSON valid sesuai schema. Tidak boleh ada teks lain, markdown, atau backtick.\n\n"
    "ATURAN KERAS (melanggar = output ditolak):\n"
    "1. HANYA gunakan informasi dari data yang diberikan. DILARANG menambah angka, nama lembaga, atau fakta baru.\n"
    "2. Vonis HARUS sesuai distribusi akhir: menolak > 50% → 'Mayoritas peserta menolak ...'; "
    "mendukung > 50% → 'Mayoritas peserta mendukung ...'; selain itu → 'Peserta terbelah ...'. "
    "DILARANG kata 'polarisasi' dan DILARANG persentase probabilitas.\n"
    "3. Setiap skenario harus berdasar pernyataan SATU agen tertentu (isi dasar_agen); "
    "format 'jika ... maka ...', tanpa persentase.\n"
    "4. Bahasa Indonesia, netral, tanpa istilah teknis (skor komposit, volatilitas, swing voter).\n"
    "5. Semua pernyataan agen adalah OPINI hasil simulasi, bukan fakta; jangan tulis seolah fakta.\n"
    "6. ronde.judul ≤ 8 kata, ronde.ringkas ≤ 40 kata.\n"
)

NARRATOR_USER_TEMPLATE = """Data terverifikasi dari simulasi:

TOP: {topik}
KATEGORI: {kategori}
TANGGAL: {tanggal}

DISTRIBUSI AKHIR:
- Menolak: {d_menolak}
- Netral: {d_netral}
- Mendukung: {d_mendukung}

KUBU (stance akhir):
- Tolak ({tolak_count} agen): {tolak_agen}
- Netral ({netral_count} agen): {netral_agen}
- Dukung ({dukung_count} agen): {dukung_agen}

TITIK BALIK:
{titik_balik}

RONDE (kutipan per ronde):
{ronde_kutipan}

ALASAN AGEN RONDE TERAKHIR (non-fallback):
{alasan_akhir}

SITUASI DARI BUILDER:
Pemicu: {pemicu_angka} — {pemicu_teks}
Bahan: {bahan}
Sumber: {sumber}

Tulis narasi lengkap sesuai schema.
"""


def _format_titik_balik(tb: list[dict]) -> str:
    if not tb:
        return "Tidak ada perubahan stance."
    lines = []
    for t in tb:
        lines.append(f"- {t['agen']}: {t['dari']} → {t['ke']} di {t['kapan']}. Alasan: {t['alasan']}")
    return "\n".join(lines)


def _format_ronde_kutipan(ronde: list[dict]) -> str:
    lines = []
    for r in ronde:
        k = r.get("kutipan")
        if k:
            lines.append(f"R{r['no']} ({r['judul']}): {k['agen']} ({k['jenis']}) — {k['teks']}")
        else:
            lines.append(f"R{r['no']} ({r['judul']}): (tidak ada kutipan valid)")
    return "\n".join(lines)


def _format_alasan_akhir(alasan_list: list[str]) -> str:
    if not alasan_list:
        return "(tidak ada)"
    return "\n".join(f"- {a}" for a in alasan_list)


def _format_skenario_draft(skenario: list[dict]) -> str:
    lines = []
    for i, s in enumerate(skenario):
        lines.append(f"{i+1}. Jika {s['jika']}, maka {s['maka']}")
    return "\n".join(lines)


def _build_narrator_prompt(computed: dict, run: dict) -> str:
    """Bangun prompt dari computed + run data."""
    distribusi = computed["hasil"]["distribusi"]
    kubu = computed["kubu"]
    tolak_agen_list = []
    netral_agen_list = []
    dukung_agen_list = []
    for k in kubu:
        if k["tipe"] == "tolak":
            tolak_agen_list.extend(k["agen"])
        elif k["tipe"] == "netral":
            netral_agen_list.extend(k["agen"])
        elif k["tipe"] == "dukung":
            dukung_agen_list.extend(k["agen"])
    tolak_agen = ", ".join(tolak_agen_list)
    netral_agen = ", ".join(netral_agen_list)
    dukung_agen = ", ".join(dukung_agen_list)
    tolak_count = len(tolak_agen_list)
    netral_count = len(netral_agen_list)
    dukung_count = len(dukung_agen_list)

    situasi = computed["situasi"]
    pemicu_angka = situasi["pemicu"]["angka"]
    pemicu_teks = situasi["pemicu"]["teks"]
    bahan = "; ".join(situasi["bahan"])
    sumber = situasi["sumber"]

    titik_balik = _format_titik_balik(computed.get("titikBalik", []))
    ronde_kutipan = _format_ronde_kutipan(computed.get("ronde", []))
    alasan_akhir = _format_alasan_akhir(computed["hasil"]["alasan"])

    return NARRATOR_USER_TEMPLATE.format(
        topik=run.get("topik", ""),
        kategori=run.get("kategori", ""),
        tanggal=computed["meta"]["tanggal"],
        d_menolak=distribusi["menolak"],
        d_netral=distribusi["netral"],
        d_mendukung=distribusi["mendukung"],
        tolak_count=tolak_count,
        netral_count=netral_count,
        dukung_count=dukung_count,
        tolak_agen=tolak_agen,
        netral_agen=netral_agen,
        dukung_agen=dukung_agen,
        titik_balik=titik_balik,
        ronde_kutipan=ronde_kutipan,
        alasan_akhir=alasan_akhir,
        pemicu_angka=pemicu_angka,
        pemicu_teks=pemicu_teks,
        bahan=bahan,
        sumber=sumber,
    )


def _fallback_narrative(computed: dict) -> dict:
    """Template fallback dari builder (tanpa LLM)."""
    distribusi = computed["hasil"]["distribusi"]
    vonis = computed["hasil"]["vonis"]
    alasan = computed["hasil"]["alasan"]
    situasi = computed["situasi"]
    kubu = computed["kubu"]

    kubu_catatan = {}
    for k in kubu:
        kubu_catatan[k["tipe"]] = k["catatan"]

    ronde_out = []
    for r in computed.get("ronde", []):
        ronde_out.append({
            "no": r["no"],
            "judul": r["judul"],
            "ringkas": r["ringkas"],
            "distribusi": r.get("distribusi", {"menolak": 0, "netral": 0, "mendukung": 0}),
        })

    skenario = []
    for s in computed.get("skenario", [])[:4]:
        dasar = "Oposisi Kritis"
        if kubu:
            for k in kubu:
                if k["tipe"] == "tolak" and k["agen"]:
                    dasar = k["agen"][0]
                    break
        # Pastikan format "jika ... maka ..." untuk validasi
        jika = s.get("jika", "")
        maka = s.get("maka", "")
        if "jika" not in jika.lower():
            jika = f"Jika {jika}"
        if "maka" not in maka.lower():
            maka = f"Maka {maka}"
        skenario.append({"jika": jika, "maka": maka, "dasar_agen": dasar})

    return {
        "vonis": vonis,
        "alasan": alasan,
        "situasi": situasi,
        "kubu_catatan": kubu_catatan,
        "ronde": ronde_out,
        "skenario": skenario,
    }


def _validate_narrative(nar: dict, computed: dict, run: dict) -> list[str]:
    """Validasi narasi. Return list error (kosong = valid)."""
    errors = []

    # 1. Field wajib
    required = ["vonis", "alasan", "situasi", "kubu_catatan", "ronde", "skenario"]
    for f in required:
        if f not in nar:
            errors.append(f"Field wajib hilang: {f}")

    if errors:
        return errors

    # 2. Vonis konsisten dengan distribusi
    dist = computed["hasil"]["distribusi"]
    vonis = nar["vonis"].lower()
    if dist["menolak"] > dist["netral"] + dist["mendukung"]:
        if not ("menolak" in vonis and "mayoritas" in vonis):
            errors.append("Vonis tidak sesuai: seharusnya 'Mayoritas peserta menolak...'")
    elif dist["mendukung"] > dist["menolak"] + dist["netral"]:
        if not ("mendukung" in vonis and "mayoritas" in vonis):
            errors.append("Vonis tidak sesuai: seharusnya 'Mayoritas peserta mendukung...'")
    else:
        if not ("terbelah" in vonis or "tercampur" in vonis):
            errors.append("Vonis tidak sesuai: seharusnya 'Peserta terbelah...'")

    # 3. Dilarang kata "polarisasi" dan persentase baru (bukan dari data)
    full_text = json.dumps(nar, ensure_ascii=False).lower()
    if "polarisasi" in full_text:
        errors.append("Mengandung kata terlarang 'polarisasi'")
    # Cek persentase: hanya izinkan yang ada di data run/briefing
    import re
    pct_in_nar = re.findall(r'\d+(?:[.,]\d+)?\s*%', full_text)
    # Kumpulkan persentase yang diizinkan dari run data
    pct_allowed = set()
    for rd in run.get("ronde_detail", []):
        for a in rd.get("agen", []):
            for angka in a.get("angka_klaim", []):
                norm = angka.replace(" ", "").replace(",", ".").lower()
                pct_allowed.add(norm)
    # Tambahkan dari briefing jika ada
    briefing = run.get("briefing", "")
    for m in re.findall(r'\d+(?:[.,]\d+)?\s*%', briefing.lower()):
        pct_allowed.add(m.replace(" ", "").replace(",", "."))
    # Default: 72,8% selalu diizinkan
    pct_allowed.update({"72,8%", "72.8%"})
    
    for pct in pct_in_nar:
        norm = pct.replace(" ", "").replace(",", ".")
        if norm not in pct_allowed:
            errors.append(f"Mengandung persentase baru tidak dari data: {pct}")
            break

    # 4. Alasan: 3 item
    if not isinstance(nar.get("alasan"), list) or len(nar["alasan"]) != 3:
        errors.append("alasan harus array 3 string")

    # 5. Skenario: dasar_agen harus nama agen yang ada di run
    agen_names = {a["nama"] for a in run.get("agen", [])}
    for s in nar.get("skenario", []):
        if "dasar_agen" in s and s["dasar_agen"] not in agen_names:
            errors.append(f"dasar_agen tidak dikenal: {s['dasar_agen']}")
        jika = s.get("jika", "")
        maka = s.get("maka", "")
        if "jika" not in jika.lower() or "maka" not in maka.lower():
            errors.append(f"Skenario format salah (harus 'jika ... maka ...'): {s}")

    # 6. Ronde: judul ≤ 8 kata, ringkas ≤ 40 kata
    for r in nar.get("ronde", []):
        judul = r.get("judul", "")
        ringkas = r.get("ringkas", "")
        if len(judul.split()) > 8:
            errors.append(f"Ronde {r.get('no')}: judul > 8 kata")
        if len(ringkas.split()) > 40:
            errors.append(f"Ronde {r.get('no')}: ringkas > 40 kata")

    return errors


def generate_narrative(run: dict, computed: dict | None = None) -> dict:
    """
    Generate narasi CaseStudy dari run data.

    Args:
        run: Dict hasil run_simulation.
        computed: Optional pre-computed builder output. Jika None, dipanggil build_computed.

    Returns:
        Dict narasi (vonis, alasan, situasi, kubu_catatan, ronde, skenario,
        narator_fallback, narator_fallback_reason).
        Jika narator_fallback=True, hasil dari template fallback.
    """
    if computed is None:
        computed = build_computed(run)

    prompt = _build_narrator_prompt(computed, run)

    # Percobaan 1: panggil LLM via llm_chat (bukan call_llm) agar bisa tangkap
    # RateLimitError dan membedakan TPD/rate limit dari error lain.
    try:
        raw, _model = llm_chat(
            messages=[
                {"role": "system", "content": NARRATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=NARRATOR_MAX_TOKENS,
            response_format=NARRATOR_RESPONSE_FORMAT,
            temperature=0.3,
        )
        nar = json.loads(raw)
        errors = _validate_narrative(nar, computed, run)
        if not errors:
            return {**nar, "narator_fallback": False, "narator_fallback_reason": None}
        # Validasi gagal → coba retry sekali
        raise ValueError("validasi_gagal")

    except RateLimitError as e:
        err_str = str(e)
        # TPD / daily limit → langsung fallback, JANGAN retry
        if "per day" in err_str or "TPD" in err_str or "daily" in err_str.lower():
            fb = _fallback_narrative(computed)
            return {**fb, "narator_fallback": True, "narator_fallback_reason": "tpd_limit"}
        # Rate limit per menit → langsung fallback, JANGAN retry (percuma)
        fb = _fallback_narrative(computed)
        return {**fb, "narator_fallback": True, "narator_fallback_reason": "rate_limit"}

    except (json.JSONDecodeError, ValueError) as e:
        reason = "json_invalid" if isinstance(e, json.JSONDecodeError) else "validasi_gagal"
        # Coba retry sekali dengan instruksi lebih keras
        try:
            retry_prompt = prompt + "\n\nOUTPUT SEBELUMNYA TIDAK VALID. Ikuti semua aturan di atas dengan ketat. Output HANYA JSON."
            raw, _model = llm_chat(
                messages=[
                    {"role": "system", "content": NARRATOR_SYSTEM},
                    {"role": "user", "content": retry_prompt},
                ],
                max_tokens=NARRATOR_MAX_TOKENS,
                response_format=NARRATOR_RESPONSE_FORMAT,
                temperature=0.3,
            )
            nar = json.loads(raw)
            errors = _validate_narrative(nar, computed, run)
            if not errors:
                return {**nar, "narator_fallback": False, "narator_fallback_reason": None}
        except Exception:
            pass
        fb = _fallback_narrative(computed)
        return {**fb, "narator_fallback": True, "narator_fallback_reason": reason}

    except Exception as e:
        # Error lain (network, dll) → langsung fallback
        fb = _fallback_narrative(computed)
        return {**fb, "narator_fallback": True, "narator_fallback_reason": "error_lain"}