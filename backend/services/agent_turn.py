# backend/services/agent_turn.py
# Satu giliran agen = satu call LLM yang mengembalikan JSON terstruktur.
#
# Kontrak output:
#   {"stance": "menolak|netral|mendukung", "score": -1..1,
#    "alasan": "<=35 kata", "sesuai_topik": bool,
#    "berubah_karena": "string" | null}
#
# Aturan:
#   - stance dan score diambil langsung dari JSON, tidak diklasifikasi ulang.
#   - JSON invalid / sesuai_topik false / berubah tanpa alasan -> retry 1x.
#   - Masih gagal -> fallback ke stance ronde sebelumnya, "fallback": true.

import json
import re

STANCES = ("menolak", "netral", "mendukung")

TURN_MAX_TOKENS = 220
MAKS_KATA_ALASAN = 35

# Groq Structured Outputs strict: didukung gpt-oss-20b, gpt-oss-120b, qwen3.8-27b
# (semua model di CHAIN). Parser toleran tetap dipakai sebagai cadangan.
TURN_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "agent_turn",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "stance": {"type": "string", "enum": list(STANCES)},
                "score": {"type": "number"},
                "alasan": {"type": "string"},
                "sesuai_topik": {"type": "boolean"},
                "berubah_karena": {"type": "string"},
            },
            "required": ["stance", "score", "alasan", "sesuai_topik", "berubah_karena"],
            "additionalProperties": False,
        },
    },
}

_FALLBACK_ALASAN = "(agen tidak memberikan output valid)"

TURN_SYSTEM_SUFFIX = (
    "\n\nFORMAT OUTPUT: balas HANYA satu objek JSON valid, tanpa markdown.\n"
    '{"stance":"menolak|netral|mendukung","score":<-1..1>,'
    '"alasan":"<=35 kata","sesuai_topik":true|false,'
    '"berubah_karena":"pemicu perubahan atau string kosong"}\n'
    f"- alasan: argumen utamamu, maksimal {MAKS_KATA_ALASAN} kata, gaya bicaramu sendiri.\n"
    "- sesuai_topik: false hanya kalau kamu memang tidak bisa membahas topik ini.\n"
    "- berubah_karena: kalau stance-mu beda dari ronde sebelumnya, isi pemicunya "
    "dalam satu kalimat; kalau sama, kosongkan.\n"
    "Jangan menyapa nama peserta lain. Jangan buka dengan 'Kamu benar'/'Gue setuju'/"
    "'Aku setuju', kecuali menanggapi 'Pihak lain berpendapat'."
)

TURN_RETRY_SUFFIX = (
    "\n\nOutput sebelumnya tidak valid atau tidak lengkap. "
    "Balas ulang HANYA satu objek JSON valid sesuai format di atas."
)

TURN_RETRY_ALASAN_SUFFIX = (
    "\n\nPosisimu berbeda dari ronde sebelumnya. Isi berubah_karena "
    "dengan pemicu konkret perubahan itu."
)


def _potong_kata(teks: str, maks: int = MAKS_KATA_ALASAN) -> str:
    kata = teks.split()
    if len(kata) <= maks:
        return " ".join(kata)
    return " ".join(kata[:maks])


# Pembuka yang dilarang di alasan (termasuk sisa respons ke agen lain di Ronde 1).
_OPENER_TERLARANG = re.compile(
    r"^(?:\s*(?:ya|nah|oke|iya)[,!.]?\s+)?"
    r"(?:"
    r"(?:gue|gua|aku|saya|kami)\s+(?:juga\s+)?(?:setuju|sepakat)"
    r"|(?:kamu|lu|lo|anda)\s+(?:memang\s+)?(?:benar|bener|betul)"
    r")"
    r"\b[^.!?]*?[,.:;]\s*",
    re.IGNORECASE,
)

# Artefak di akhir kalimat: ";." dan ", Gua." hasil generasi model.
_ARTEFAK_AKHIR = (
    re.compile(r"\s*[;,]\s*\.\s*$"),
    re.compile(r"[,;]?\s+(?:gua|gue)\s*\.\s*$", re.IGNORECASE),
)


def bersihkan_alasan(teks: str) -> str:
    """Buang pembuka terlarang dan artefak akhir dari alasan (tanpa menyentuh JSON)."""
    bersih = (teks or "").strip()
    sebelumnya = None
    while sebelumnya != bersih:
        sebelumnya = bersih
        bersih = _OPENER_TERLARANG.sub("", bersih, count=1).strip()
    for pola in _ARTEFAK_AKHIR:
        bersih = pola.sub(".", bersih)
    bersih = re.sub(r"\s+([.!?,])", r"\1", bersih).strip()
    if bersih[:1].islower():
        bersih = bersih[0].upper() + bersih[1:]
    return bersih


_ANGKA_RE = re.compile(r"\d+(?:[.,]\d+)*\s*%?")


def _normalisasi_angka(tok: str) -> str:
    """Samakan format: '72,8 %', '72.8%', '72,80' -> satu bentuk."""
    t = re.sub(r"\s|%", "", tok)

    def _digit(nilai: str) -> str:
        return re.sub(r"\D", "", nilai)

    if len(_digit(t)) < 2:
        return ""
    # Pemisah ribuan: 3.200 / 3,200 / 1.234.567
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", t):
        return t.replace(".", "").replace(",", "")
    t = t.replace(",", ".")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def _kumpulan_angka(teks: str) -> set[str]:
    hasil = set()
    for tok in _ANGKA_RE.findall(teks or ""):
        normal = _normalisasi_angka(tok)
        if normal:
            hasil.add(normal)
    return hasil


def angka_klaim(alasan: str, sumber: str) -> list[str]:
    """
    Angka di `alasan` yang tidak ada di `sumber` (briefing + topik).

    Post-check murni Python, tanpa LLM. List kosong = tidak ada klaim angka asing.
    """
    sah = _kumpulan_angka(sumber)
    asing: list[str] = []
    for tok in _ANGKA_RE.findall(alasan or ""):
        normal = _normalisasi_angka(tok)
        if normal and normal not in sah:
            tampil = re.sub(r"\s+", "", tok)
            if tampil not in asing:
                asing.append(tampil)
    return asing


def _ekstrak_objek(raw: str) -> str | None:
    """Ambil objek JSON pertama dari teks (model kadang menambah kalimat pembuka)."""
    if not raw:
        return None
    teks = re.sub(r"```(?:json)?|```", "", raw).strip()
    awal = teks.find("{")
    if awal < 0:
        return None
    # Coba dari kurung kurawal pertama sampai akhir; kalau gagal, cari penutup terakhir.
    for kandidat in (teks[awal:], teks[awal:teks.rfind("}") + 1]):
        if not kandidat:
            continue
        try:
            json.loads(kandidat)
            return kandidat
        except json.JSONDecodeError:
            continue
    return None


def _score_dari_stance(stance: str) -> float:
    return {"mendukung": 0.6, "netral": 0.0, "menolak": -0.6}[stance]


# Score harus konsisten dengan stance. Stance menang, score disesuaikan.
_RENTANG_SCORE_STANCE = {
    "menolak": (-1.0, -0.2),
    "netral": (-0.2, 0.2),
    "mendukung": (0.2, 1.0),
}


def sesuaikan_score(score: float, stance: str) -> tuple[float, bool]:
    """Clamp score ke rentang stance. Return (score, disesuaikan)."""
    bawah, atas = _RENTANG_SCORE_STANCE[stance]
    asli = round(float(score), 2)
    baru = round(max(bawah, min(atas, asli)), 2)
    return baru, baru != asli


def parse_turn(raw: str) -> dict | None:
    """
    Parse output agen jadi dict tervalidasi. Return None kalau tidak bisa dipakai.

    Field yang hilang diisi default; stance wajib valid karena itu inti kontrak.
    """
    kandidat = _ekstrak_objek(raw)
    if kandidat is None:
        return None
    try:
        data = json.loads(kandidat)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    stance = str(data.get("stance", "")).strip().lower()
    if stance not in STANCES:
        return None

    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        score = _score_dari_stance(stance)
    score = max(-1.0, min(1.0, round(score, 2)))

    alasan = bersihkan_alasan(str(data.get("alasan") or ""))
    if not alasan:
        # Pembersihan tidak boleh mengosongkan alasan; pakai teks aslinya.
        alasan = str(data.get("alasan") or "").strip()
    alasan = _potong_kata(alasan)
    if not alasan:
        return None

    sesuai_topik = data.get("sesuai_topik", True)
    if not isinstance(sesuai_topik, bool):
        sesuai_topik = str(sesuai_topik).strip().lower() not in {"false", "0", "tidak", "no"}

    berubah = data.get("berubah_karena")
    if berubah is not None:
        berubah = _potong_kata(str(berubah).strip(), maks=25) or None

    return {
        "stance": stance,
        "score": score,
        "alasan": alasan,
        "sesuai_topik": sesuai_topik,
        "berubah_karena": berubah,
        "fallback": False,
    }


def alasan_retry(turn: dict | None, prev_stance: str | None) -> str | None:
    """Alasan giliran perlu diulang. None = output sudah layak."""
    if turn is None:
        return "invalid_json"
    if not turn["sesuai_topik"]:
        return "tidak_sesuai_topik"
    if prev_stance and turn["stance"] != prev_stance and not turn["berubah_karena"]:
        return "berubah_tanpa_alasan"
    return None


def turn_fallback(prev_stance: str | None, prev_score: float | None = None) -> dict:
    """Giliran gagal total: pertahankan posisi ronde sebelumnya."""
    stance = prev_stance if prev_stance in STANCES else "netral"
    if prev_score is not None:
        score = max(-1.0, min(1.0, float(prev_score)))
    else:
        score = _score_dari_stance(stance)
    return {
        "stance": stance,
        "score": score,
        "alasan": _FALLBACK_ALASAN,
        "sesuai_topik": None,
        "berubah_karena": None,
        "fallback": True,
    }


def execute_turn(
    llm,
    system_p: str,
    user_p: str,
    prev_stance: str | None = None,
    prev_score: float | None = None,
) -> dict:
    """
    Jalankan satu giliran agen: 1 call LLM, retry maksimal 1x.

    llm dipanggil sebagai llm(system_prompt, user_prompt) -> str.
    """
    system_p = system_p + TURN_SYSTEM_SUFFIX
    turn = parse_turn(llm(system_p, user_p))
    alasan = alasan_retry(turn, prev_stance)

    if alasan is None:
        return _finalisasi(turn)

    retry_p = user_p + TURN_RETRY_SUFFIX
    if alasan == "berubah_tanpa_alasan":
        retry_p += TURN_RETRY_ALASAN_SUFFIX
    retry_turn = parse_turn(llm(system_p, retry_p))

    # Pakai hasil retry kalau bisa diparse, kalau tidak pakai hasil pertama (kalau ada).
    if retry_turn is not None:
        turn = retry_turn
    elif turn is None:
        return _finalisasi(turn_fallback(prev_stance, prev_score))

    return _finalisasi(turn)


def _finalisasi(turn: dict) -> dict:
    """Samakan score dengan stance sebelum delta cap dipakai."""
    asli = turn["score"]
    turn["score"], disesuaikan = sesuaikan_score(asli, turn["stance"])
    turn["score_disesuaikan"] = disesuaikan
    turn["score_asli"] = asli if disesuaikan else None
    return turn
