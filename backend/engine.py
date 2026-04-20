# backend/engine.py
# Upgraded: Multi-ronde simulasi sosial dengan:
#   - Persistent agent memory (evolusi opini antar ronde)
#   - Entity & relation extraction (GraphRAG-lite, tanpa DB eksternal)
#   - Sentiment scoring via LLM (bukan keyword matching)
#   - God's Eye intervention layer (skenario "bagaimana jika")
#   - Structured JSON output siap untuk visualisasi graf & tabel

import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

def _build_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set on the server environment.")
    return Groq(api_key=api_key)


client = _build_client()

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS_RESPONSE = 400
MAX_TOKENS_ANALYSIS = 800


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = MAX_TOKENS_RESPONSE) -> str:
    """Panggil LLM dan kembalikan teks respons."""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL,
            temperature=0.5,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error: {str(e)}]"


def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 600) -> dict | list:
    """
    Panggil LLM dengan ekspektasi output JSON.
    Kembalikan dict/list hasil parse, atau {} jika gagal.
    """
    raw = call_llm(system_prompt, user_prompt, max_tokens)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {}


# ---------------------------------------------------------------------------
# GraphRAG-lite: Entity & Relation Extraction
# ---------------------------------------------------------------------------

def extract_entities(topik: str, teks_diskusi: str) -> dict:
    """
    Ekstraksi entitas dan relasi dari teks diskusi (GraphRAG-lite).
    Output: { "entitas": [...], "relasi": [...] }
    """
    system = (
        "Kamu sistem ekstraksi informasi. "
        "Tugasmu mengidentifikasi entitas penting dan relasi antar-entitas dari teks diskusi. "
        "Kembalikan HANYA JSON valid, tanpa penjelasan."
    )
    user = (
        f"Topik: {topik}\n\n"
        f"Diskusi:\n{teks_diskusi}\n\n"
        "Ekstrak:\n"
        '{ "entitas": [{"nama": "...", "tipe": "orang|organisasi|konsep|kebijakan", "sentimen_umum": "positif|netral|negatif"}], '
        '"relasi": [{"dari": "...", "ke": "...", "label": "mendukung|menolak|mempengaruhi|bergantung_pada"}] }'
    )
    result = call_llm_json(system, user, max_tokens=500)
    if not result:
        return {"entitas": [], "relasi": []}
    return result


# ---------------------------------------------------------------------------
# Memory: Simpan dan bangun konteks memori per agen
# ---------------------------------------------------------------------------

def update_agent_memory(agent: dict, ronde: int, pendapat: str):
    """Tambahkan entri memori ke agen."""
    agent["memori"].append({"ronde": ronde, "pendapat": pendapat})


def build_memory_context(agent: dict) -> str:
    """Susun konteks memori agen untuk prompt ronde berikutnya."""
    if not agent["memori"]:
        return ""
    lines = [f"  [Ronde {m['ronde']}] Kamu berkata: \"{m['pendapat']}\"" for m in agent["memori"]]
    return "Pendapatmu di ronde sebelumnya:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Sentiment Scoring — berbasis LLM, bukan keyword matching
# ---------------------------------------------------------------------------

def score_sentiment(teks: str, topik: str = "") -> dict:
    """
    Skor sentimen menggunakan LLM agar memahami negasi dan konteks.

    Output: { "label": "positif|netral|negatif", "skor": float -1..1 }

    Contoh yang SALAH dengan keyword matching:
      "saya tidak setuju" → keyword 'setuju' → positif  (SALAH)
      "bukan prioritas utama" → tidak ada keyword negatif → netral (SALAH)

    LLM membaca kalimat secara utuh sehingga negasi, sarkasme,
    dan nuansa bahasa Indonesia terdeteksi dengan benar.
    """
    system = (
        "Kamu analis sentimen bahasa Indonesia yang sangat teliti. "
        "Tugasmu: tentukan apakah teks berikut mengekspresikan dukungan (positif), "
        "penolakan (negatif), atau sikap netral terhadap topik yang disebutkan. "
        "PENTING: perhatikan kata negasi seperti 'tidak', 'bukan', 'belum', 'jangan', 'kurang', 'menolak'. "
        "Kembalikan HANYA JSON valid tanpa penjelasan dalam format: "
        '{"label": "positif|netral|negatif", "skor": <angka dari -1.0 hingga 1.0>}'
        "\n\nPanduan skor:"
        "\n  1.0  = sangat mendukung / setuju penuh"
        "\n  0.5  = cenderung mendukung"
        "\n  0.0  = benar-benar netral / tidak berpihak"
        "\n -0.5  = cenderung menolak / tidak setuju"
        "\n -1.0  = sangat menolak / menentang keras"
    )
    konteks_topik = f"Topik diskusi: {topik}\n\n" if topik else ""
    user = f"{konteks_topik}Teks pendapat:\n\"{teks}\""

    result = call_llm_json(system, user, max_tokens=80)

    # Validasi hasil
    label = result.get("label", "netral")
    skor  = result.get("skor", 0.0)

    # Pastikan tipe dan rentang benar
    if label not in ("positif", "netral", "negatif"):
        label = "netral"
    try:
        skor = max(-1.0, min(1.0, float(skor)))
    except (TypeError, ValueError):
        skor = 0.0

    # Konsistensi label ↔ skor
    if label == "positif" and skor < 0:
        skor = abs(skor)
    elif label == "negatif" and skor > 0:
        skor = -abs(skor)
    elif label == "netral":
        # Jika skor ternyata kuat, koreksi label
        if skor >= 0.35:
            label = "positif"
        elif skor <= -0.35:
            label = "negatif"

    return {"label": label, "skor": round(skor, 2)}


# ---------------------------------------------------------------------------
# Multi-ronde Simulation Core
# ---------------------------------------------------------------------------

def run_simulation(
    topik: str,
    agents: list[dict],
    jumlah_ronde: int = 3,
    intervensi: str | None = None,
) -> dict:
    """
    Jalankan simulasi multi-agen multi-ronde.

    Args:
        topik: Isu/topik diskusi.
        agents: Daftar agen dari get_agents().
        jumlah_ronde: Berapa kali ronde diskusi dilakukan.
        intervensi: (God's Eye) Variabel eksternal yang diinjeksikan di ronde tengah.

    Returns:
        dict dengan kunci:
            - ronde_detail: list[dict] — output per ronde per agen
            - graf_data: dict — entitas & relasi untuk visualisasi
            - analisis: str — narasi & tabel markdown
            - prediksi: dict — probabilitas skenario
            - sentimen_agregat: dict — sentimen per agen lintas ronde
    """
    ronde_detail = []
    log_diskusi  = f"TOPIK: {topik}\n"

    for ronde_ke in range(1, jumlah_ronde + 1):
        # Injeksi intervensi di ronde tengah (God's Eye)
        topik_ronde = topik
        if intervensi and ronde_ke == (jumlah_ronde // 2) + 1:
            topik_ronde = f"{topik} [INTERVENSI BARU: {intervensi}]"
            log_diskusi += f"\n--- INTERVENSI RONDE {ronde_ke}: {intervensi} ---\n"

        output_ronde = {"ronde": ronde_ke, "agen": []}

        for agen in agents:
            konteks_memori = build_memory_context(agen)

            kepribadian = agen.get("kepribadian", {})
            sifat = []
            if kepribadian.get("openness", 0.5) > 0.7:
                sifat.append("kamu sangat terbuka pada ide baru")
            if kepribadian.get("agreeableness", 0.5) < 0.45:
                sifat.append("kamu cenderung kritis dan tidak mudah setuju")
            if kepribadian.get("neuroticism", 0.5) > 0.55:
                sifat.append("kamu cenderung emosional dalam merespons")
            sifat_str = "; ".join(sifat) if sifat else "kamu berpikir rasional"

            system_p = (
                f"Kamu {agen['nama']}. {agen['role']} "
                f"Karaktermu: {sifat_str}. "
                f"Jawab dalam 2-3 kalimat bahasa Indonesia yang natural dan sesuai karaktermu."
            )

            user_p = (
                f"{konteks_memori}\n\n"
                f"Isu yang sedang didiskusikan [Ronde {ronde_ke}]: {topik_ronde}\n"
                f"Apa pendapatmu sekarang? (Boleh berubah dari pendapat sebelumnya jika kamu mendapat informasi baru.)"
            ).strip()

            jawaban  = call_llm(system_p, user_p)

            # ← Gunakan LLM-based scoring dengan konteks topik
            sentimen = score_sentiment(jawaban, topik=topik_ronde)

            update_agent_memory(agen, ronde_ke, jawaban)

            log_diskusi += f"\n[Ronde {ronde_ke}] {agen['nama']}: {jawaban}\n"
            output_ronde["agen"].append({
                "nama":     agen["nama"],
                "pendapat": jawaban,
                "sentimen": sentimen,
            })

        ronde_detail.append(output_ronde)

    # --- GraphRAG-lite: Ekstrak entitas & relasi ---
    graf_data = extract_entities(topik, log_diskusi)

    # --- Sentimen agregat per agen (untuk visualisasi tren) ---
    sentimen_agregat = {}
    for agen in agents:
        tren = []
        for ronde in ronde_detail:
            for a in ronde["agen"]:
                if a["nama"] == agen["nama"]:
                    tren.append(a["sentimen"]["skor"])
        sentimen_agregat[agen["nama"]] = tren

    # --- Analisis akhir (narasi + tabel markdown) ---
    prompt_analisis = (
        f"Berikut adalah log diskusi multi-ronde:\n\n{log_diskusi}\n\n"
        "Tugas kamu:\n"
        "1. Buat NARASI singkat (2 paragraf) yang merangkum dinamika diskusi dan perubahan opini.\n"
        "2. Buat TABEL MARKDOWN dengan kolom: | Partisipan | Sentimen Akhir | Prediksi Sikap | Potensi Perubahan |\n"
        "3. Buat PREDIKSI SKENARIO: kemungkinan (%) untuk tiga skenario: Konsensus, Polarisasi, Status Quo.\n"
        "Jawab dalam bahasa Indonesia."
    )
    analisis_raw = call_llm(
        "Kamu analis sosial-politik profesional yang objektif dan berbasis data.",
        prompt_analisis,
        max_tokens=MAX_TOKENS_ANALYSIS,
    )

    prediksi = _parse_prediksi(analisis_raw)

    return {
        "ronde_detail":    ronde_detail,
        "graf_data":       graf_data,
        "analisis":        analisis_raw,
        "prediksi":        prediksi,
        "sentimen_agregat": sentimen_agregat,
        "jumlah_ronde":    jumlah_ronde,
        "topik":           topik,
        "intervensi":      intervensi,
    }


def _parse_prediksi(teks: str) -> dict:
    """
    Coba ekstrak persentase skenario dari teks analisis.
    Kembalikan default jika tidak ditemukan.
    """
    default = {"Konsensus": 33, "Polarisasi": 34, "Status Quo": 33}
    patterns = {
        "Konsensus":  r"[Kk]onsensus[^\d]*(\d{1,3})\s*%",
        "Polarisasi": r"[Pp]olarisasi[^\d]*(\d{1,3})\s*%",
        "Status Quo": r"[Ss]tatus\s*[Qq]uo[^\d]*(\d{1,3})\s*%",
    }
    hasil = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, teks)
        if match:
            hasil[key] = int(match.group(1))
    if len(hasil) < 3:
        return default
    total = sum(hasil.values())
    if total > 0:
        hasil = {k: round(v / total * 100) for k, v in hasil.items()}
    return hasil