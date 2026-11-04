# backend/memory.py
# Manajemen memori agen: update, ringkasan (cached), dan context builder.
#
# Memori tiap agen disimpan di agent["memori"] sebagai list dict
# {"ronde": int, "pendapat": str}. Ringkasan di-cache di agent["_ringkasan_cache"]
# dan hanya di-invalidasi saat update_agent_memory() dipanggil.
#
# Phase 5: Integrasi dengan MemoryStore terstruktur (argument + relationship tracking).
# MemoryStore dipakai di samping dict memori lama untuk backward compatibility.

import re

# ponytail: call_llm, MODEL_AGENT, MAX_TOKENS_SUMMARY dihapus — ga dipake setelah summarize_memory dihapus
from .core.memory_store import AgentMemoryStore


# ---------------------------------------------------------------------------
# Memory Update — Phase 5: tambah structured memory
# ---------------------------------------------------------------------------

def _get_or_create_store(agent: dict) -> AgentMemoryStore:
    """Dapatkan atau buat AgentMemoryStore untuk agen ini."""
    if "_memory_store" not in agent:
        agent["_memory_store"] = AgentMemoryStore(agent.get("nama", "Unknown"))
    return agent["_memory_store"]


def update_agent_memory(
    agent: dict,
    ronde: int,
    pendapat: str,
    sentimen: dict | None = None,
    all_opinions: list[dict] | None = None,
) -> None:
    """
    Simpan pendapat agen ke memori dan invalidasi cache ringkasan.
    Stabilization PR: juga simpan label & skor sentimen jika tersedia,
    agar change-justification di simulation.py bisa membaca skor ronde lalu.
    Backward compatible — pemanggil lama tanpa sentimen tetap tidak error.

    Phase 5: juga update structured memory (argument + relationship tracking).
    """
    entry: dict = {"ronde": ronde, "pendapat": pendapat}
    if sentimen:
        entry["label"] = sentimen.get("label")
        entry["skor"]  = sentimen.get("skor")
    agent["memori"].append(entry)
    agent.pop("_ringkasan_cache", None)

    # Phase 5: Update structured memory
    store = _get_or_create_store(agent)
    store.add_round(
        ronde=ronde,
        pendapat=pendapat,
        sentimen=sentimen or {},
        all_opinions=all_opinions,
    )


# ---------------------------------------------------------------------------
# Personality / Gaya String (cached per agen, dihitung sekali)
# ---------------------------------------------------------------------------

def _compute_gaya_str(agent: dict) -> str:
    """
    Hitung string gaya kepribadian dari kepribadian agen.
    Kepribadian tidak pernah berubah dalam satu sesi, jadi hasilnya
    di-cache langsung di dict agen — dihitung sekali, dipakai selamanya.
    """
    if "_gaya_str" in agent:
        return agent["_gaya_str"]
    kepribadian = agent.get("kepribadian", {})
    gaya = []
    if kepribadian.get("openness",      0.5) > 0.7:  gaya.append("terbuka")
    if kepribadian.get("agreeableness", 0.5) < 0.45: gaya.append("suka debat")
    if kepribadian.get("neuroticism",   0.5) > 0.55: gaya.append("emosional")
    agent["_gaya_str"] = ", ".join(gaya) if gaya else "tenang"
    return agent["_gaya_str"]


# ---------------------------------------------------------------------------
# Context Builders
# ---------------------------------------------------------------------------

def build_memory_context(agent: dict) -> str:
    """Bangun string konteks memori singkat untuk prompt agen.

    BUG-03 fix: menyertakan label stance (MENDUKUNG/NETRAL/MENOLAK) dan skor
    di setiap entri memori agar agen tidak bisa flip posisi secara diam-diam.

    Phase 5: Integrasi dengan structured memory (tanpa LLM summarize).
    """
    if not agent["memori"]:
        return ""

    terakhir = agent["memori"][-1]
    has_previous = len(agent["memori"]) >= 2

    def _stance_label_from_skor(skor) -> str:
        """Konversi skor ke label posisi yang jelas."""
        if skor is None:
            return "NETRAL"
        if skor > 0.2:
            return "MENDUKUNG"
        if skor < -0.2:
            return "MENOLAK"
        return "NETRAL"

    skor_terakhir = terakhir.get("skor")
    label_terakhir = _stance_label_from_skor(skor_terakhir)
    skor_str = f" (skor {skor_terakhir:.2f})" if skor_terakhir is not None else ""

    # Alasan terakhir dipakai utuh (maks 35 kata) agar posisi awal agen tidak hilang.
    # Phase 5: Gunakan structured memory untuk konteks (tanpa LLM)
    store = _get_or_create_store(agent)
    structured_ctx = store.build_context(agent["memori"])

    if len(agent["memori"]) >= 2:
        base_context = (
            f"{structured_ctx} "
            f"Terakhir kamu bilang: \"{terakhir['pendapat']}\" "
            f"(posisi: {label_terakhir}{skor_str}). "
        )
        if has_previous:
            mem_sebelumnya = agent["memori"][-2]
            skor_sblm = mem_sebelumnya.get("skor")
            label_sblm = _stance_label_from_skor(skor_sblm)
            skor_sblm_str = f" (skor {skor_sblm:.2f})" if skor_sblm is not None else ""
            pendapat_sblm = mem_sebelumnya["pendapat"][:40]
            return (
                base_context +
                f"Sebelumnya kamu {label_sblm}{skor_sblm_str}: '{pendapat_sblm}...'. "
                f"Kalau berubah, jelaskan pemicunya."
            )
        return base_context + "Pertahankan posisi kecuali ada alasan kuat."

    # Hanya 1 entri memori
    return (
        f"Terakhir kamu bilang: \"{terakhir['pendapat']}\" "
        f"(posisi: {label_terakhir}{skor_str}). "
        f"Pertahankan posisi kecuali ada argumen baru yang kuat."
    )


MAKS_KATA_RINGKASAN = 25


def build_round_summary(
    semua_pendapat: list[dict], maks_agen: int = 3, kecuali: str | None = None
) -> str:
    """
    Ringkasan ekstraktif ronde sebelumnya tanpa LLM dan tanpa nama agen.

    Ambil `maks_agen` alasan dengan |skor| terbesar dari agen berbeda, tiap alasan
    dipotong MAX_KATA_RINGKASAN kata. Nama persona tidak ditampilkan agar agen
    menanggapi argumennya, bukan orangnya. `kecuali` = agen yang sedang bicara,
    karena pendapatnya sendiri bukan "pihak lain".
    """
    kandidat = sorted(
        (
            p
            for p in semua_pendapat
            if (p.get("pendapat") or "").strip() and p.get("nama") != kecuali
        ),
        key=lambda p: abs((p.get("sentimen") or {}).get("skor") or 0.0),
        reverse=True,
    )
    baris: list[str] = []
    dipakai: set[str] = set()
    for p in kandidat:
        nama = p.get("nama")
        if nama in dipakai:
            continue
        kata = p["pendapat"].split()
        if not kata or kata[0].startswith("("):
            continue  # placeholder giliran gagal/fallback
        dipakai.add(nama)
        potong = " ".join(kata[:MAKS_KATA_RINGKASAN]).rstrip(",;:")
        baris.append(f'- "{potong}"')
        if len(baris) == maks_agen:
            break
    if not baris:
        return ""
    return "Pihak lain berpendapat:\n" + "\n".join(baris)


def build_influence_context(
    agen: dict,
    semua_pendapat_ronde: list[dict],
    idx_agen: int = 0,
) -> str:
    """
    Bangun string konteks pengaruh agen lain — termasuk yang sudah bicara
    di ronde yang sama (in-round context) maupun ronde sebelumnya.

    Perubahan vs versi lama:
    - Threshold pengaruh diturunkan dari 0.75 → 0.4 agar semua agen masuk
    - Prioritas: agen yang baru bicara di ronde sama (paling fresh)
    - Ambil max 3 agen (bukan 2) agar lebih banyak yang bisa direspons
    - Kutipan dipotong di kalimat pertama agar lebih natural
    - idx_agen dipakai untuk rotasi kandidat agar agen tidak semua menyerang target sama
    """
    if not semua_pendapat_ronde:
        return ""

    # Sort berdasarkan pengaruh, ambil top-5, lalu rotate berdasarkan idx_agen
    # agar setiap agen mendapat "perspektif" kandidat yang berbeda
    kandidat_sorted = sorted(
        [p for p in semua_pendapat_ronde if p["nama"] != agen["nama"]],
        key=lambda p: p.get("pengaruh", 0.5),
        reverse=True,
    )[:5]

    if not kandidat_sorted:
        return ""

    start = idx_agen % len(kandidat_sorted)
    kandidat = (kandidat_sorted[start:] + kandidat_sorted[:start])[:3]

    if not kandidat:
        return ""

    def _stance_label(skor):
        if skor is None:
            return "NETRAL"
        if skor > 0.2:
            return "MENDUKUNG"
        if skor < -0.2:
            return "MENOLAK"
        return "NETRAL"

    # Bikin konteks yang KAYAK OBROLAN BENERAN, bukan laporan formal
    baris = []
    for p in kandidat:
        pendapat_full = p["pendapat"]
        skor = p.get("sentimen", {}).get("skor")
        label = _stance_label(skor)

        # Ambil kutipan yang natural — kalimat pertama yang cukup panjang
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', pendapat_full)
        kutipan = ""
        for s in sentences:
            s = s.strip()
            if len(s) >= 30:
                kutipan = s
                break
        if not kutipan and sentences:
            kutipan = sentences[0].strip()
        if len(kutipan) > 150:
            kutipan = kutipan[:150].rsplit(" ", 1)[0]
        if len(pendapat_full) > len(kutipan) + 1:
            kutipan += "..."

        # Format yang natural — kayak orang ngomong
        if label == "MENDUKUNG":
            baris.append(f'- {p["nama"]} setuju: "{kutipan}"')
        elif label == "MENOLAK":
            baris.append(f'- {p["nama"]} menyangkal: "{kutipan}"')
        else:
            baris.append(f'- {p["nama"]} bilang: "{kutipan}"')

    konteks = "Yang baru aja ngomong:\n" + "\n".join(baris) + "\n\n"
    konteks += "Sekarang giliranmu. Tanggapi yang baru aja dikatakan — boleh setuju, sanggah, atau tambahin sudut pandangmu. "
    konteks += "Pakai kata-katamu sendiri, jangan kutip ulang."
    return konteks