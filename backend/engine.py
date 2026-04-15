import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def _build_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set on the server environment.")
    return Groq(api_key=api_key)


client = _build_client()

def call_llm(system_prompt, user_prompt, model_name="llama-3.3-70b-versatile"):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
            max_tokens=500 # jebluk celeng
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def run_simulation(topik, agents):
    # AMBIL 3 AGEN SAJA (Agar tidak kena limit TPM 6000 token)
    selected_agents = agents[:4 ] 
    riwayat = f"TOPIK: {topik}\n"
    
    for p in selected_agents:
        # Instruksi diperpendek drastis untuk menghemat token input
        system_p = f"Kamu {p['nama']}. {p['role']}. Jawab singkat 1 kalimat."
        user_p = f"Isu: {topik}. Pendapatmu?"
        
        jawaban = call_llm(system_p, user_p)
        riwayat += f"\n{p['nama']}: {jawaban}\n"

    # Summary Layer: Memaksa format tabel agar bisa dibaca page.js
    prompt_analisis = (
        f"Analisis diskusi ini:\n{riwayat}\n"
        "Buat narasi 1 paragraf dan tabel markdown: | Partisipan | Sentimen | Prediksi Hasil |"
    )
    
    analisis = call_llm("Kamu Analyst Profesional.", prompt_analisis)
    
    return {"analisis": analisis}