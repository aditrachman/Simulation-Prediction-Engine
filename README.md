# VoxSwarm — Social Simulation Engine

> Simulasi reaksi publik terhadap kebijakan pemerintah Indonesia sebelum diluncurkan.

## Apa ini?
VoxSwarm membantu pengambil keputusan memahami gambaran reaksi berbagai kelompok
masyarakat terhadap suatu isu atau kebijakan — sebelum kebijakan tersebut
diluncurkan ke publik.

## Untuk siapa?
- **Mahasiswa & Peneliti** — eksplorasi dinamika opini untuk riset awal
- **Jurnalis & Analis** — gambaran respons publik sebelum menulis
- **Pemda & NGO** (fase berikutnya) — uji kebijakan sebelum implementasi

## Cara Pakai

### Prasyarat
- Python **3.10** atau lebih tinggi
- Node.js **18** atau lebih tinggi
- Akun Groq dan API key dari [console.groq.com](https://console.groq.com)

### 1. Clone Repository
```bash
git clone https://github.com/aditrachman/Simulation-Prediction-Engine.git
cd Simulation-Prediction-Engine
```

### 2. Setup Backend
```bash
pip install fastapi uvicorn[standard] groq pydantic python-dotenv \
            numpy pandas scikit-learn matplotlib seaborn
```

Buat file `.env` di root proyek:
```bash
cp .env.example .env
# Edit .env dan isi GROQ_API_KEY dengan API key Anda
```

### 3. Setup Frontend
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" > .env.local
```

### 4. Jalankan
```bash
# Terminal 1 — Backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

## Tech Stack
| Lapisan | Teknologi |
|---|---|
| Backend | FastAPI, Uvicorn |
| LLM | Groq Cloud (llama-3.1-8b, llama-3.3-70b) |
| ML | scikit-learn (Logistic Regression, Random Forest) |
| Frontend | Next.js 15, Tailwind CSS v4, Recharts |
| Validasi | Pydantic v2 |

## Disclaimer
VoxSwarm adalah alat eksplorasi, bukan pengganti survei empiris.
Hasil bergantung pada konfigurasi agen dan tidak merepresentasikan opini publik aktual.
