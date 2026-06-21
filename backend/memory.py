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

from .llm import call_llm, MODEL_AGENT, MAX_TOKENS_SUMMARY
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
# Memory Summarization
# ---------------------------------------------------------------------------

def summarize_memory(agent: dict) -> str:
    """
    Ringkas riwayat memori agen menjadi 1 kalimat.
    Hasil di-cache di agent["_ringkasan_cache"]; hanya di-invalidasi oleh
    update_agent_memory() saat ada memori baru — menghilangkan call LLM
    redundan di setiap ronde selama konteks memori belum berubah.
    """
    if len(agent["memori"]) < 3:
        return ""
    if "_ringkasan_cache" in agent:
        return agent["_ringkasan_cache"]
    riwayat = " | ".join(
        f"R{m['ronde']}: {m['pendapat'][:60]}" for m in agent["memori"][:-1]
    )
    ringkasan = call_llm(
        "Ringkas jadi 1 kalimat: apa sikap agen ini?",
        f"Agen: {agent['nama']}\n{riwayat}",
        max_tokens=MAX_TOKENS_SUMMARY,
        model=MODEL_AGENT,
    )
    agent["_ringkasan_cache"] = ringkasan
    return ringkasan


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

    # Phase 5: Gunakan structured memory untuk konteks (tanpa LLM)
    store = _get_or_create_store(agent)
    structured_ctx = store.build_context(agent["memori"])

    if len(agent["memori"]) >= 2:
        base_context = (
            f"{structured_ctx} "
            f"Ronde terakhir — Posisi: {label_terakhir}{skor_str} "
            f"— Argumen: \"{terakhir['pendapat'][:80]}\" "
        )
        if has_previous:
            mem_sebelumnya = agent["memori"][-2]
            skor_sblm = mem_sebelumnya.get("skor")
            label_sblm = _stance_label_from_skor(skor_sblm)
            skor_sblm_str = f" (skor {skor_sblm:.2f})" if skor_sblm is not None else ""
            pendapat_sblm = mem_sebelumnya["pendapat"][:40]
            return (
                base_context +
                f"Ronde sebelumnya — Posisi: {label_sblm}{skor_sblm_str} "
                f"— Argumen: '{pendapat_sblm}...' "
                f"Jika kamu berubah dari {label_sblm} ke posisi berbeda, "
                f"WAJIB jelaskan di responsmu: data atau argumen baru apa yang mengubah posisimu. "
                f"Contoh: 'Ronde lalu saya {label_sblm.lower()}, tapi sekarang saya lihat bukti Y — jadi saya revisi.'"
            )
        return base_context + f"— posisi: {label_terakhir}. Pertahankan kecuali ada alasan kuat."

    # Hanya 1 entri memori
    return (
        f"Posisimu sebelumnya: {label_terakhir}{skor_str} "
        f"— Kamu bilang: \"{terakhir['pendapat'][:80]}\" "
        f"— Pertahankan posisi ini kecuali ada argumen baru yang sangat kuat."
    )


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

    baris = []
    for p in kandidat:
        pendapat_full = p["pendapat"]
        # Split per kalimat — tidak salah potong di angka desimal (3.5%) atau inisial (Dr. Smith)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', pendapat_full)
        # Ambil kalimat pertama yang >= 30 char (hindari "Iya.", "Benar.", "Tidak.")
        kutipan = ""
        for s in sentences:
            s = s.strip()
            if len(s) >= 30:
                kutipan = s
                break
        if not kutipan and sentences:
            kutipan = sentences[0].strip()
        # Fallback: potong di 150 char kalau masih terlalu panjang
        if len(kutipan) > 150:
            kutipan = kutipan[:150].rsplit(" ", 1)[0]
        if len(pendapat_full) > len(kutipan) + 1:
            kutipan += "..."
        baris.append(f'- {p["nama"]}: {kutipan}')

    konteks  = "Posisi peserta lain sejauh ini:\n" + "\n".join(baris) + "\n"
    konteks += "Respons LANGSUNG ke salah satu — gunakan kata-katamu sendiri, jangan kutip ulang."
    return konteks