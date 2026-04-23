# backend/sentiment.py
# Sentiment scoring — dua mode:
#   "inline"  → kamus kata kunci, 0 token tambahan (rekomendasi free tier)
#   "llm"     → LLM-based, lebih akurat, +~50 token per call
#
# Pilih mode via env: SENTIMENT_MODE=inline | llm

import re

from .llm import call_llm_json, MODEL_AGENT, MAX_TOKENS_SENTIMENT, SENTIMENT_MODE


# ---------------------------------------------------------------------------
# Kamus Kata Kunci (mode inline)
# ---------------------------------------------------------------------------

_KATA_POSITIF = {
    "setuju","mendukung","bagus","baik","tepat","benar","perlu","penting",
    "manfaat","untung","pro","iya","ya","bener","oke","harus","wajib",
    "butuh","positif","dukung","sokong","sepakat","cocok","sesuai",
}
_KATA_NEGATIF = {
    "menolak","tolak","bahaya","berbahaya","buruk","salah","rugi","merugikan",
    "tidak","nggak","gak","bukan","jangan","kontra","gagal","masalah",
    "negatif","jelek","keberatan","risiko","ancaman","larang","dilarang",
    "hentikan","stop","hapus","cabut","batalkan","takut","khawatir",
    "kecewa","menyedihkan","memberatkan","mencekik","mempersulit",
}
_NEGASI = {"tidak","nggak","gak","bukan","jangan","tanpa"}


# ---------------------------------------------------------------------------
# Inline Scorer
# ---------------------------------------------------------------------------

def _score_inline(teks: str) -> dict:
    """Scoring sentimen tanpa LLM — hemat ~50 token per agen per ronde."""
    kata = re.sub(r"[^\w\s]", " ", teks.lower()).split()
    skor = 0.0
    for i, k in enumerate(kata):
        negasi = i > 0 and kata[i-1] in _NEGASI
        if k in _KATA_POSITIF:
            skor += -0.4 if negasi else 0.4
        elif k in _KATA_NEGATIF and k not in _NEGASI:
            skor += 0.4 if negasi else -0.4
    skor = max(-1.0, min(1.0, skor))
    if skor > 0.15:    label = "positif"
    elif skor < -0.15: label = "negatif"
    else:              label = "netral"; skor = 0.0
    return {"label": label, "skor": round(skor, 2)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_sentiment(teks: str, topik: str = "") -> dict:
    """
    Nilai sentimen pendapat terhadap topik.

    SENTIMENT_MODE=inline  → kamus kata kunci, 0 token (REKOMENDASI free tier)
    SENTIMENT_MODE=llm     → LLM-based, akurat, tapi ~50 token/call tambahan
    """
    if SENTIMENT_MODE == "inline":
        return _score_inline(teks)

    # Mode LLM — prompt dipersingkat maksimal
    system = (
        "Nilai sentimen pendapat terhadap ISU. 'Setuju bahwa X berbahaya' = NEGATIF terhadap X. "
        "JSON: {\"label\":\"positif|netral|negatif\",\"skor\":<-1..1>}"
    )
    user = f'ISU:"{topik[:60]}"\nPendapat:"{teks[:180]}"'
    result = call_llm_json(system, user, max_tokens=MAX_TOKENS_SENTIMENT, model=MODEL_AGENT)

    label = result.get("label", "netral")
    skor  = result.get("skor", 0.0)
    if label not in ("positif", "netral", "negatif"): label = "netral"
    try:   skor = max(-1.0, min(1.0, float(skor)))
    except: skor = 0.0

    if label == "positif":    skor = abs(skor) or 0.5
    elif label == "negatif":  skor = -abs(skor) or -0.5
    elif label == "netral":
        if skor >= 0.35:    label = "positif"
        elif skor <= -0.35: label = "negatif"
        else:               skor = 0.0
    return {"label": label, "skor": round(skor, 2)}