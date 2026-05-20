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

def update_agent_memory(
    agent: dict,
    ronde: int,
    pendapat: str,
    sentimen: dict | None = None,
) -> None:
    """
    Simpan pendapat agen ke memori dan invalidasi cache ringkasan.
    Stabilization PR: juga simpan label & skor sentimen jika tersedia,
    agar change-justification di simulation.py bisa membaca skor ronde lalu.
    Backward compatible — pemanggil lama tanpa sentimen tetap tidak error.
    """
    entry: dict = {"ronde": ronde, "pendapat": pendapat}
    if sentimen:
        entry["label"] = sentimen.get("label")
        entry["skor"]  = sentimen.get("skor")
    agent["memori"].append(entry)
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
    """Bangun string konteks memori singkat untuk prompt agen.

    Sesi 15 — BUG #27:
    Selain mengingatkan posisi terakhir, sekarang juga menyertakan posisi
    ronde sebelumnya agar agen WAJIB menjelaskan alasan jika berubah posisi.
    """
    if not agent["memori"]:
        return ""

    terakhir = agent["memori"][-1]
    has_previous = len(agent["memori"]) >= 2

    if len(agent["memori"]) >= 3:
        ringkasan = summarize_memory(agent)
        base_context = (
            f"POSISIMU SEJAUH INI: {ringkasan} "
            f"Terakhir kamu bilang: \"{terakhir['pendapat'][:80]}\" "
        )
        if has_previous:
            pendapat_sebelumnya = agent["memori"][-2]["pendapat"][:40]
            # BUG #27 fix: minta justifikasi eksplisit jika posisi berubah
            return (
                base_context +
                f"— Ronde sebelumnya kamu bilang: '{pendapat_sebelumnya}...' "
                f"Jika kamu berubah posisi dari situ, JELASKAN di responsmu "
                f"argumen atau data baru apa yang membuatmu berubah pikiran. "
                f"Contoh: 'Ronde lalu saya bilang X, tapi sekarang saya lihat bukti Y — jadi saya revisi.'"
            )
        else:
            return base_context + "— pertahankan jika tidak ada alasan kuat untuk berubah."

    # Hanya 1 entri memori
    return (
        f"Kamu bilang: \"{terakhir['pendapat'][:80]}\" "
        f"— ini posisimu, pertahankan kecuali ada argumen baru yang sangat kuat."
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
        # Ambil kalimat pertama saja (potong di titik pertama)
        kalimat_pertama = pendapat_full.split(".")[0].strip()
        # Batasi 90 karakter, potong di kata terakhir yang lengkap
        if len(kalimat_pertama) > 90:
            kalimat_pertama = kalimat_pertama[:90].rsplit(" ", 1)[0]
        kutipan = kalimat_pertama + ("..." if len(pendapat_full) > len(kalimat_pertama) + 1 else "")
        baris.append(f'- {p["nama"]}: {kutipan}')

    konteks  = "Posisi peserta lain sejauh ini:\n" + "\n".join(baris) + "\n"
    konteks += "Respons LANGSUNG ke salah satu — gunakan kata-katamu sendiri, jangan kutip ulang."
    return konteks