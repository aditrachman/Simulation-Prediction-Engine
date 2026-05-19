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
    Bangun string konteks pengaruh agen lain dengan pengaruh tinggi.
    
    FIX BUG #18: Sekarang include kutipan pendapat dari 2 agen paling berpengaruh,
    dengan instruksi eksplisit untuk merespons atau membantah argumen mereka.
    """
    if not semua_pendapat_ronde:
        return ""
    
    # Ambil 2 agen paling berpengaruh (selain diri sendiri)
    kuat = [
        p for p in semua_pendapat_ronde
        if p["nama"] != agen["nama"] and p.get("pengaruh", 0) >= 0.75
    ][:2]  # max 2 (hemat token)
    
    if not kuat:
        return ""
    
    # Format: kutipan max 80 char per agen, dengan instruksi respons silang
    baris = []
    for p in kuat:
        kutipan = p["pendapat"][:80].rstrip()
        # Potong di kata terakhir yang lengkap jika terlalu panjang
        if len(p["pendapat"]) > 80:
            kutipan = kutipan.rsplit(' ', 1)[0] + '...' if ' ' in kutipan else kutipan
        baris.append(f"- {p['nama']}: \"{kutipan}\"")
    
    # Tambah instruksi eksplisit untuk respons silang
    konteks = "Pendapat yang perlu direspons:\n" + "\n".join(baris) + "\n"
    konteks += "Tanggapi atau balas argumen salah satu dari mereka secara langsung."
    
    return konteks