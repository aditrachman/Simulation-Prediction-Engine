# backend/memory.py
# Manajemen memori agen: update, ringkasan (cached), dan context builder.
#
# Memori tiap agen disimpan di agent["memori"] sebagai list dict
# {"ronde": int, "pendapat": str}. Ringkasan di-cache di agent["_ringkasan_cache"]
# dan hanya di-invalidasi saat update_agent_memory() dipanggil.

from .llm import call_llm, MODEL_AGENT, MAX_TOKENS_SUMMARY


# ---------------------------------------------------------------------------
# Memory Update
# ---------------------------------------------------------------------------

def update_agent_memory(agent: dict, ronde: int, pendapat: str) -> None:
    """Simpan pendapat agen ke memori dan invalidasi cache ringkasan."""
    agent["memori"].append({"ronde": ronde, "pendapat": pendapat})
    agent.pop("_ringkasan_cache", None)


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
    """Bangun string konteks memori singkat untuk prompt agen."""
    if not agent["memori"]:
        return ""
    terakhir = agent["memori"][-1]
    if len(agent["memori"]) >= 3:
        ringkasan = summarize_memory(agent)
        return f"Sikapmu: {ringkasan} Terakhir: \"{terakhir['pendapat'][:80]}\""
    return f"Kamu bilang: \"{terakhir['pendapat'][:80]}\""


def build_influence_context(agen: dict, semua_pendapat_ronde: list[dict]) -> str:
    """
    Bangun string konteks pengaruh agen lain — termasuk yang sudah bicara
    di ronde yang sama (in-round context) maupun ronde sebelumnya.

    Perubahan vs versi lama:
    - Threshold pengaruh diturunkan dari 0.75 → 0.4 agar semua agen masuk
    - Prioritas: agen yang baru bicara di ronde sama (paling fresh)
    - Ambil max 3 agen (bukan 2) agar lebih banyak yang bisa direspons
    - Kutipan dipotong di kalimat pertama agar lebih natural
    """
    if not semua_pendapat_ronde:
        return ""

    # Semua agen lain, sorted pengaruh tertinggi duluan
    kandidat = sorted(
        [p for p in semua_pendapat_ronde if p["nama"] != agen["nama"]],
        key=lambda p: p.get("pengaruh", 0.5),
        reverse=True,
    )[:3]  # max 3 agen

    if not kandidat:
        return ""

    baris = []
    for p in kandidat:
        pendapat_full = p["pendapat"]
        # Ambil kalimat pertama saja (potong di titik pertama)
        kalimat_pertama = pendapat_full.split(".")[0].strip()
        # Batasi 90 karakter, potong di kata terakhir yang lengkap
        if len(kalimat_pertama) > 90:
            kalimat_pertama = kalimat_pertama[:90].rsplit(" ", 1)[0]
        kutipan = kalimat_pertama + ("..." if len(pendapat_full) > len(kalimat_pertama) + 1 else "")
        baris.append(f'- {p["nama"]} bilang: "{kutipan}"')

    konteks  = "Yang sudah disampaikan peserta lain:\n" + "\n".join(baris) + "\n"
    konteks += "Pilih SATU yang paling kamu tidak setuju atau paling menarik, lalu respons langsung ke mereka."
    return konteks