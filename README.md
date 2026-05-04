# VoxSwarm — Simulation Prediction Engine

<p align="center">
  <img src="https://img.shields.io/badge/version-3.2.0-indigo?style=flat-square" />
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/Next.js-15.x-black?style=flat-square" />
  <img src="https://img.shields.io/badge/Groq-LLM-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" />
</p>

> **Simulasi opini publik berbasis multi-agen AI** — prediksi dinamika sosial, polarisasi, dan konsensus sebelum isu berkembang.

---

## Daftar Isi

- [Overview](#overview)
- [Fitur Utama](#fitur-utama)
- [Tech Stack](#tech-stack)
- [Arsitektur Sistem](#arsitektur-sistem)
- [Instalasi](#instalasi)
- [Konfigurasi](#konfigurasi)
- [Menjalankan Aplikasi](#menjalankan-aplikasi)
- [API Endpoints](#api-endpoints)
- [Struktur Proyek](#struktur-proyek)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## Overview

VoxSwarm adalah platform simulasi opini publik yang menggunakan arsitektur **multi-agent AI**. Sistem mensimulasikan diskusi antara berbagai profil sosial (Mahasiswa, Pengusaha, Pemerintah, Akademisi, dll.) yang dipandu LLM melalui Groq Cloud, lalu menganalisis dinamika sentimen, memprediksi skenario (Konsensus / Polarisasi / Status Quo), dan memvisualisasikan hasilnya secara interaktif.

Sistem ini juga dilengkapi **ML Prediction Layer** berbasis Random Forest yang belajar dari riwayat simulasi, serta **Feedback Loop** untuk mengumpulkan ground truth dari operator guna meningkatkan akurasi prediksi dari waktu ke waktu.

---

## Fitur Utama

- **Simulasi Multi-Agen Multi-Ronde** — hingga 7 agen dengan profil kepribadian unik, termasuk counter-agent untuk mencegah echo chamber
- **Mode Sosial Media** — simulasi dinamika Twitter/X: post, reply, like, quote
- **God's Eye Intervention** — injeksikan variabel eksternal di tengah simulasi
- **Agen Custom** — tambahkan hingga 5 agen dengan peran yang didefinisikan sendiri dari frontend
- **Data Real** — konteks dari RSS feed berita Indonesia (Kompas, Detik, BBC, Tempo, Antara, CNN) + Reddit
- **GraphRAG** — ekstraksi entitas dan relasi antar aktor secara otomatis
- **ML Prediction Layer** — prediksi skenario dengan Random Forest yang dilatih dari histori simulasi
- **Feedback Loop** — kumpulkan ground truth dari operator untuk auto re-training model
- **Ekspor Laporan** — unduh hasil dalam format PDF, CSV, dan Word (.docx)
- **Rate Limiting** — proteksi bawaan per IP, retry otomatis dengan exponential backoff

---

## Tech Stack

### Backend
| Komponen | Teknologi |
|---|---|
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| LLM Provider | Groq Cloud (llama-3.1-8b, llama-3.3-70b) |
| ML Layer | scikit-learn (Random Forest) |
| Data Scraping | urllib (RSS + Reddit JSON API) |
| Validasi | Pydantic v2 |

### Frontend
| Komponen | Teknologi |
|---|---|
| Framework | Next.js 15 (App Router) |
| Styling | Tailwind CSS v4 |
| Charts | Recharts |
| Runtime | Node.js 18+ |

---

## Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                   │
│  Landing Page  ·  Demo Dashboard  ·  Ekspor Laporan    │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP REST
┌─────────────────────────▼───────────────────────────────┐
│                  Backend (FastAPI)                      │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Agents   │  │ Scraper  │  │ Feedback │              │
│  │ Registry │  │ RSS+Reddit│  │  Loop   │              │
│  └────┬─────┘  └────┬─────┘  └────┬────┘              │
│       │              │              │                   │
│  ┌────▼──────────────▼─────┐  ┌────▼────┐             │
│  │    Simulation Engine    │  │   ML    │             │
│  │  (multi-agent, memory,  │  │Pipeline │             │
│  │   sentiment, GraphRAG)  │  │(RF+hist)│             │
│  └────────────┬────────────┘  └─────────┘             │
│               │                                        │
│  ┌────────────▼────────────┐                           │
│  │      LLM Client         │                           │
│  │  (Groq + retry/cache)   │                           │
│  └────────────┬────────────┘                           │
└───────────────┼────────────────────────────────────────┘
                │ HTTPS
        ┌───────▼────────┐
        │  Groq Cloud    │
        │ llama-3.1-8b   │
        │ llama-3.3-70b  │
        └────────────────┘
```

---

## Instalasi

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
# Install semua dependensi Python
pip install fastapi uvicorn[standard] groq pydantic python-dotenv \
            numpy pandas scikit-learn matplotlib seaborn
```

> **Catatan:** Pastikan `fastapi`, `uvicorn`, dan `groq` terinstall — ketiganya wajib ada.

Buat file `.env` di root proyek:

```bash
cp .env.example .env
# Edit .env dan isi GROQ_API_KEY dengan API key Anda
```

### 3. Setup Frontend

```bash
cd frontend
npm install
```

Buat file environment frontend:

```bash
# Buat file frontend/.env.local
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" > .env.local
```

---

## Konfigurasi

### File `.env` (root proyek)

```env
# ─── WAJIB ────────────────────────────────────────────────
GROQ_API_KEY=your_groq_api_key_here

# ─── Model LLM (opsional) ─────────────────────────────────
# Model untuk agent responses (cepat & hemat token)
MODEL_AGENT=llama-3.1-8b-instant

# Model untuk analisis akhir (lebih akurat)
MODEL_ANALYSIS=llama-3.3-70b-versatile

# ─── Token Budget (opsional) ──────────────────────────────
MAX_TOKENS_AGENT=350
MAX_TOKENS_RESPONSE=400
MAX_TOKENS_ANALYSIS=900

# ─── Rate Limit API Server (opsional) ────────────────────
RATE_LIMIT_WINDOW_SEC=60
RATE_LIMIT_MAX_REQUESTS=8

# ─── Sentiment Mode (opsional) ───────────────────────────
# "llm"    = akurat, menggunakan LLM call (default)
# "inline" = cepat, berbasis kamus kata kunci (hemat token)
SENTIMENT_MODE=llm

# ─── Cache RSS (opsional) ─────────────────────────────────
CONTEXT_CACHE_TTL_MINUTES=30
CONTEXT_CACHE_MAX_ENTRIES=100

# ─── ML Pipeline (opsional) ───────────────────────────────
ML_MIN_SAMPLES=5
ML_MAX_HISTORY=500
```

### File `frontend/.env.local`

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

## Menjalankan Aplikasi

### Backend

```bash
# Dari root proyek
uvicorn main:app --reload --port 8000
```

Backend akan berjalan di: **http://127.0.0.1:8000**

Dokumentasi API interaktif (Swagger UI): **http://127.0.0.1:8000/docs**

### Frontend

```bash
# Dari folder frontend/
cd frontend
npm run dev
```

Frontend akan berjalan di: **http://localhost:3000**

### Menjalankan Keduanya Sekaligus (Opsional)

```bash
# Terminal 1 — Backend
uvicorn main:app --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

---

## API Endpoints

Base URL: `http://localhost:8000`

### Simulasi

| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/start-simulation` | Jalankan simulasi multi-agen multi-ronde |
| `POST` | `/start-social` | Jalankan simulasi mode sosial media |
| `GET` | `/categories` | Daftar kategori simulasi yang tersedia |
| `POST` | `/extract-graph` | Ekstrak graf entitas dari hasil simulasi |

**Contoh request `/start-simulation`:**
```json
{
  "topik": "Kenaikan harga BBM bersubsidi",
  "kategori": "Ekonomi",
  "jumlah_ronde": 3,
  "intervensi": "Pemerintah umumkan bantuan subsidi baru",
  "agen_custom": [
    {
      "nama": "Sopir Ojol",
      "role": "Pengemudi ojek online yang sangat terdampak kenaikan BBM",
      "pengaruh": 0.7
    }
  ]
}
```

### Data & Konteks

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/fetch-context?topik=...` | Ambil berita & Reddit terkait topik |
| `GET` | `/cache-status` | Status cache konteks real |
| `POST` | `/cache-clear` | Hapus cache (semua atau per topik) |

### ML Pipeline

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/ml-status` | Status model ML saat ini |
| `POST` | `/ml-train` | Trigger training manual |
| `GET` | `/ml-metrics` | Evaluasi model (akurasi, confusion matrix) |
| `GET` | `/ml-debug` | Diagnostik distribusi label & feature importance |
| `GET` | `/ml-dataset-stats` | Statistik dataset training lengkap |

### Feedback

| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/feedback` | Submit ground truth label dari operator |
| `GET` | `/feedback-stats` | Statistik feedback terkumpul |
| `GET` | `/feedback-export` | Export semua feedback sebagai JSON |

**Contoh request `/feedback`:**
```json
{
  "topik_hash": "a3f9c12e4b78d501",
  "label_aktual": "Polarisasi",
  "confidence": 0.9,
  "catatan": "Diskusi yang sangat sengit, tidak ada titik temu"
}
```

> `topik_hash` didapat dari response field `data.topik_hash` di endpoint `/start-simulation`.

### Health

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/` | Health check server |

---

## Struktur Proyek

```
Simulation-Prediction-Engine/
│
├── main.py                        # Entry point FastAPI — semua endpoints
├── requirements.txt               # Dependensi Python (backend)
├── .env.example                   # Template environment variables
│
├── backend/
│   ├── __init__.py
│   ├── agents.py                  # Registry agen + kategori + counter-agents
│   ├── engine.py                  # Compatibility shim (re-export semua modul)
│   ├── llm.py                     # Groq client, retry, cache, call_llm()
│   ├── memory.py                  # Manajemen memori agen antar ronde
│   ├── sentiment.py               # Scoring sentimen (LLM atau inline)
│   ├── graph.py                   # GraphRAG: ekstraksi entitas & relasi
│   ├── simulation.py              # Orchestration simulasi multi-agen
│   ├── social_engine.py           # Mode simulasi sosial media
│   ├── scraper.py                 # RSS feed + Reddit JSON API + disk cache
│   ├── ml_pipeline.py             # ML layer: fitur, training, prediksi
│   ├── feedback.py                # Feedback ground truth + auto re-train
│   └── data/                      # Data persistensi (auto-created)
│       ├── simulation_history.jsonl
│       ├── feedback.jsonl
│       ├── outcome_model.pkl
│       ├── label_encoder.pkl
│       └── context_cache.json
│
├── frontend/
│   ├── package.json               # Dependensi Node.js
│   ├── next.config.mjs
│   ├── tailwind.config.js
│   └── src/
│       └── app/
│           ├── layout.js
│           ├── page.js            # Landing page
│           ├── globals.css
│           ├── demo/
│           │   └── page.js        # Dashboard utama simulasi
│           └── utils/
│               ├── eksporpdf.js
│               ├── eksporlainnya.js
│               └── timelinesosmed.js
│
└── scripts/
    └── generate_dummy_data.py     # Script untuk generate data training ML
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'fastapi'`
Pastikan semua dependensi wajib sudah terinstall:
```bash
pip install fastapi uvicorn[standard] groq pydantic python-dotenv
```

### `RuntimeError: GROQ_API_KEY is not set`
Buat file `.env` di root proyek dan isi `GROQ_API_KEY`:
```bash
echo "GROQ_API_KEY=gsk_..." > .env
```

### Error 429 (Rate Limit Groq)
Sistem sudah dilengkapi retry otomatis. Jika terlalu sering terjadi:
```env
# Di .env — naikkan jeda antar agen
AGENT_CALL_DELAY=5.0
ROUND_DELAY=5.0
# Atau aktifkan mode inline untuk hemat token
SENTIMENT_MODE=inline
```

### Port 8000 sudah dipakai
```bash
uvicorn main:app --reload --port 8001
# Update frontend/.env.local:
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
```

### Port 3000 sudah dipakai
```bash
cd frontend && npm run dev -- -p 3001
```

### Analisis menampilkan "(analisis tidak tersedia)"
Ini terjadi saat Groq API mengalami rate limit pada call analisis akhir. Coba:
1. Kurangi jumlah ronde (`jumlah_ronde: 1` atau `2`)
2. Kurangi jumlah agen (gunakan kategori spesifik, bukan "Umum")
3. Tunggu beberapa menit lalu coba lagi

### Model ML belum aktif / prediksi menggunakan rule-based
ML layer membutuhkan minimal 5 simulasi sebelum model aktif. Jalankan beberapa simulasi atau gunakan script:
```bash
python scripts/generate_dummy_data.py
# Lalu trigger training:
curl -X POST http://localhost:8000/ml-train
```

---

## Lisensi

MIT License — bebas digunakan, dimodifikasi, dan didistribusikan dengan menyertakan credit.
