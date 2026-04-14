import requests
import json
import time

def panggil_ollama(role, persona, input_teks):
    url = "http://localhost:11434/api/generate"
    
    # Prompt ini sangat penting agar AI tidak 'halu'
    prompt_lengkap = f"""
    Ini adalah simulasi debat sosial.

    Kamu WAJIB memberikan OPINI, bukan mengulang atau menjelaskan ulang isu.

    Identitas:
    {persona}

    Contoh:
    Isu: BBM naik
    Jawaban: Kenaikan ini jelas memberatkan rakyat kecil, kebijakan ini terasa tidak peka.

    Aturan:
    - Dilarang mengulang kalimat dari isu
    - Harus memberikan opini pribadi sesuai karakter
    - Harus ada sikap (setuju / tidak setuju)
    - Maksimal 2 kalimat

    Isu:
    {input_teks}

    Jawaban sebagai {role}:
    """
    
    payload = {
        "model": "gemma:2b",
        "prompt": prompt_lengkap,
        "stream": False,
        "options": {
            "temperature": 0.8, # Rendah agar konsisten, tidak ngawur
            "top_p": 0.9,
            "num_predict": 100,   # Membatasi panjang jawaban agar tidak muter-muter
            "repeat_penalty": 1.2

        }
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.json()['response'].strip()
    except Exception as e:
        return f"Koneksi gagal: {e}"

# --- KONFIGURASI AGEN ---
agen_1 = {
    "nama": "Mahasiswa",
    "persona": "Anda mahasiswa aktivis yang marah. Gunakan kata-kata protes. Jangan pernah mengulangi kata-kata lawan bicara Anda!"
}

agen_2 = {
    "nama": "Pejabat",
    "persona": "Anda adalah menteri yang kaku dan fokus pada anggaran negara. Gunakan istilah ekonomi seperti 'defisit' atau 'subsidi'. Jangan pernah setuju dengan mahasiswa!"
}

# --- ALUR SIMULASI ---
topik = "Pemerintah menaikkan harga BBM sebesar 10% per malam ini."
print(f"Isu: {topik}\n")

# Putaran 1: Mahasiswa bereaksi terhadap Isu
print(f"--- {agen_1['nama']} sedang berpikir... ---")
respon_mhs = panggil_ollama(agen_1['nama'], agen_1['persona'], topik)
print(f"[{agen_1['nama']}]: {respon_mhs}\n")

time.sleep(1) # Jeda biar CPU tidak kaget

# Putaran 2: Pejabat merespons Mahasiswa (Bukan merespons isu lagi)
print(f"--- {agen_2['nama']} sedang merespons... ---")
respon_pjb = panggil_ollama(agen_2['nama'], agen_2['persona'], respon_mhs)
print(f"[{agen_2['nama']}]: {respon_pjb}\n")