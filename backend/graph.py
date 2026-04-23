# backend/graph.py
# GraphRAG-lite: ekstraksi entitas & relasi dari teks diskusi.
# Menggunakan satu call LLM-JSON untuk menghasilkan graf entitas
# yang bisa divisualisasikan di frontend.

from .llm import call_llm_json, MODEL_ANALYSIS


# ---------------------------------------------------------------------------
# Entity & Relation Extraction
# ---------------------------------------------------------------------------

def extract_entities(topik: str, teks_diskusi: str) -> dict:
    """
    Ekstrak entitas (orang, organisasi, konsep, kebijakan) dan relasi
    antar entitas dari log diskusi.

    Return contoh:
        {
            "entitas": [{"nama": "...", "tipe": "...", "sentimen_umum": "..."}],
            "relasi":  [{"dari": "...", "ke": "...", "label": "..."}],
        }
    """
    system = (
        "Kamu sistem ekstraksi informasi. "
        "Identifikasi entitas dan relasi dari diskusi. "
        "Kembalikan HANYA JSON valid."
    )
    user = (
        f"Topik: {topik}\nDiskusi:\n{teks_diskusi[:600]}\n\n"
        '{"entitas":[{"nama":"...","tipe":"orang|organisasi|konsep|kebijakan","sentimen_umum":"positif|netral|negatif"}],'
        '"relasi":[{"dari":"...","ke":"...","label":"mendukung|menolak|mempengaruhi|bergantung_pada"}]}'
    )
    result = call_llm_json(system, user, max_tokens=350, model=MODEL_ANALYSIS)
    return result if result else {"entitas": [], "relasi": []}