# backend/sentiment.py
# Sentiment scoring — dua mode:
#   "llm"    → LLM-based, akurat untuk kalimat kompleks (DEFAULT)
#   "inline" → kamus kata kunci, 0 token tambahan (fallback / free tier ketat)
#
# Set via .env: SENTIMENT_MODE=llm | inline
# DEFAULT: llm — inline tidak mampu handle negasi kompleks & kalimat ambigu
#
# Label: "positif" | "netral" | "negatif"
#   positif = mendukung / setuju / pro terhadap isu/topik
#   negatif = menolak / khawatir / kritis terhadap isu/topik
#   netral  = skeptis terhadap klaim, berimbang, atau tidak berpihak

import re

from .llm import call_llm_json, MODEL_AGENT, MAX_TOKENS_SENTIMENT, SENTIMENT_MODE


# ---------------------------------------------------------------------------
# Kamus Kata Kunci (mode inline — fallback saja)
#
# KETERBATASAN INLINE:
#   Kalimat seperti "saya tidak percaya klaim itu, tidak ada bukti kuat"
#   penuh kata negatif tapi maknanya SKEPTIS/NETRAL terhadap topik.
#   Inline scorer tidak bisa membedakan konteks ini.
#   Gunakan mode LLM untuk akurasi yang memadai.
# ---------------------------------------------------------------------------

_KATA_NEGATIF = {
    "menolak", "tolak", "kontra", "antipati", "keberatan",
    "bahaya", "berbahaya", "merugikan", "rugi", "rugikan",
    "ancaman", "mengancam", "risiko", "berisiko",
    "masalah", "bermasalah", "salah", "keliru", "cacat",
    "pelanggaran", "melanggar", "ilegal", "semena",
    "menyalahgunakan", "disalahgunakan", "penyalahgunaan", "eksploitasi",
    "khawatir", "kekhawatiran", "takut", "was-was", "resah",
    "meresahkan", "mengkhawatirkan", "memprihatinkan", "prihatin",
    "buruk", "jelek", "rusak", "merusak",
    "kecewa", "menyedihkan", "menyakitkan", "merampas",
    "mencekik", "memberatkan", "mempersulit",
    "larang", "dilarang", "hentikan", "stop", "hapus",
    "cabut", "batalkan", "cegah",
}

_KATA_POSITIF = {
    "setuju", "mendukung", "dukung", "sokong", "sepakat", "pro",
    "manfaat", "bermanfaat", "menguntungkan", "membantu",
    "meningkatkan", "memperbaiki", "solusi",
    "bagus", "baik", "tepat", "cocok", "sesuai",
    "efisien", "efektif", "inovatif",
}

_NEGASI = {"tidak", "nggak", "gak", "bukan", "jangan", "tanpa", "belum"}

_FRASA_KONTRAS = {
    "namun", "tetapi", "tapi", "meski", "meskipun",
    "walaupun", "walau", "akan tetapi", "sayangnya", "ironisnya",
}


# ---------------------------------------------------------------------------
# Inline Scorer — HANYA dipakai jika SENTIMENT_MODE=inline
# ---------------------------------------------------------------------------

def _score_inline(teks: str, topik: str = "") -> dict:
    teks_bersih = re.sub(r"[^\w\s]", " ", teks.lower())
    kata = teks_bersih.split()
    skor = 0.0

    for i, k in enumerate(kata):
        jendela = kata[max(0, i - 3):i]
        ada_negasi = any(n in jendela for n in _NEGASI)

        if k in _KATA_POSITIF:
            skor += -0.35 if ada_negasi else 0.35
        elif k in _KATA_NEGATIF:
            skor += 0.35 if ada_negasi else -0.35

        if k in _FRASA_KONTRAS:
            skor -= 0.1

    skor = max(-1.0, min(1.0, skor))

    # Threshold konservatif: butuh >= 0.35 agar tidak jatuh ke netral
    if skor >= 0.35:
        label = "positif"
    elif skor <= -0.35:
        label = "negatif"
    else:
        label = "netral"
        skor = 0.0

    return {"label": label, "skor": round(skor, 2)}


# ---------------------------------------------------------------------------
# LLM Scorer — DEFAULT
# Mampu handle: negasi ganda, kalimat skeptis, frasa ambigu, konteks topik
# ---------------------------------------------------------------------------

def _score_llm(teks: str, topik: str = "") -> dict:
    system = (
        "Klasifikasi sentimen pendapat terhadap isu Indonesia.\n"
        "  positif = MENDUKUNG / SETUJU / PRO terhadap isu\n"
        "  negatif = MENOLAK / KHAWATIR / KRITIS terhadap isu\n"
        "  netral  = berimbang atau tidak berpihak\n"
        "Contoh: 'memberatkan rakyat' → {\"label\":\"negatif\",\"skor\":-0.8}\n"
        "Contoh: 'mendukung demi kebaikan bersama' → {\"label\":\"positif\",\"skor\":0.7}\n"
        "Contoh: 'ada sisi positif dan negatif' → {\"label\":\"netral\",\"skor\":0.0}\n"
        'Balas HANYA JSON: {"label":"positif|netral|negatif","skor":<-1.0..1.0>}'
    )
    user = f'Isu: "{topik[:60]}"\nPendapat: "{teks[:200]}"'

    result = call_llm_json(system, user, max_tokens=MAX_TOKENS_SENTIMENT, model=MODEL_AGENT)

    # Jika LLM gagal hasilkan JSON valid (model 8B sering gagal) → fallback inline
    if not result or not isinstance(result, dict):
        return _score_inline(teks, topik)

    label = result.get("label", "")
    skor  = result.get("skor", None)

    # Fallback inline jika label tidak valid atau skor tidak ada
    if label not in ("positif", "netral", "negatif") or skor is None:
        return _score_inline(teks, topik)

    try:
        skor = max(-1.0, min(1.0, float(skor)))
    except Exception:
        return _score_inline(teks, topik)

    # Koreksi konsistensi label ↔ skor
    if label == "positif":
        skor = abs(skor) if skor != 0.0 else 0.5
    elif label == "negatif":
        skor = -abs(skor) if skor != 0.0 else -0.5
    else:
        # netral tapi skor kuat → koreksi label
        if skor >= 0.35:
            label = "positif"
        elif skor <= -0.35:
            label = "negatif"
        else:
            skor = 0.0

    return {"label": label, "skor": round(skor, 2)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_sentiment(teks: str, topik: str = "") -> dict:
    """
    Nilai sentimen pendapat terhadap topik.

    DEFAULT: mode LLM (akurat, ~50 token/call tambahan).
    Set SENTIMENT_MODE=inline di .env untuk hemat token di free tier.

    Label:
      positif = mendukung / pro terhadap topik
      negatif = menolak / khawatir / kritis terhadap topik
      netral  = skeptis terhadap klaim, berimbang, atau tidak berpihak
    """
    if SENTIMENT_MODE == "inline":
        return _score_inline(teks, topik)

    return _score_llm(teks, topik)