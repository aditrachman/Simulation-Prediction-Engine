---
tags: [project/voxswarm, type/arsitektur]
---

# Arsitektur — Alur Request Frontend ke Backend

VoxSwarm punya dua sisi: **frontend Next.js** (yang user lihat) dan **backend FastAPI** (otak simulasi). Ini alur kerjanya.

## 1. Alur Simulasi

```
User input topik (form)
       ↓
Frontend → POST /start-simulation → FastAPI
       ↓                              ↓
  Loading screen            Ambil agent, inject konteks real
       ↓                              ↓
  Render hasil              Jalankan simulasi multi-ronde
       ↓                              ↓
  Chart + analisis          Kirim JSON response
```

### Detail langkah:

**Step 1 — User ketik topik** di halaman `/demo`. Ada pilihan kategori (Ekonomi, Politik, dll), jumlah putaran (1-5), dan mode (Cepat/Lengkap).

**Step 2 — Frontend kirim POST** ke endpoint `/start-simulation` dengan body JSON:
```json
{
  "topik": "Apakah kenaikan UMP 2025 menguntungkan buruh?",
  "kategori": "Ekonomi",
  "jumlah_ronde": 3,
  "tier": "free"
}
```

**Step 3 — Backend FastAPI** (di `main.py`) validasi dulu: rate limit, XSS check, format topik. Baru lanjut ke:

1. Ambil daftar **agent** sesuai kategori (dari `agents.py`) + inject **counter-agent** biar gak jadi echo chamber
2. Tambah **agent kontekstual** kalau ada keyword khusus (dari `agent_factory.py`)
3. Kalau mode "free": batasi maksimal 4 agent dan 2 putaran
4. Ambil **konteks real** dari RSS berita Indonesia (dari `scraper.py`)
5. Jalankan `run_simulation()` — inti dari semuanya

**Step 4 — Backcase kirim balik JSON** besar berisi: data tiap putaran, sentimen, prediksi, analisis, sampai rekomendasi strategis.

**Step 5 — Frontend render** hasilnya: kartu kesimpulan, distribusi pendapat, suara tiap agent, grafik tren, sama tombol export PDF/CSV/Word.

## 2. Komunikasi API

Backend jalan di `http://127.0.0.1:8000`. Frontend di `http://localhost:3000`. CORS sudah diatur biar dua-duanya bisa ngomong.

### Endpoint utama yang dipanggil frontend:

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| POST | `/start-simulation` | Jalankan simulasi |
| POST | `/compare-scenarios` | Bandingkan 2-5 skenario |
| POST | `/explain` | Jelaskan sentimen satu teks |
| POST | `/feedback` | Kirim ground truth label |
| GET | `/ml-status` | Cek status model ML |
| POST | `/ml-train` | Paksa retrain model |

### Yang **tidak** dipanggil frontend sekarang (tapi ada di backend):

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/fetch-context` | Preview berita real tanpa simulasi |
| POST | `/extract-graph` | Ekstraksi entitas & relasi |
| GET | `/cache-status` | Cek status cache |
| POST | `/cache-clear` | Hapus cache |
| POST | `/cache-clear-llm` | Hapus cache LLM |
| GET | `/ml-debug` | Diagnostik ML lengkap |
| GET | `/ml-dataset-stats` | Statistik dataset training |
| GET | `/ml-retrain-check` | Cek & trigger retrain |
| GET | `/ml-metrics` | Evaluasi performa model |
| GET | `/sentiment-ml-metrics` | Evaluasi sentiment classifier |
| GET | `/feedback-stats` | Statistik feedback |
| GET | `/feedback-export` | Download feedback.jsonl |
| DELETE | `/feedback/{topik_hash}` | Hapus 1 feedback |
| GET | `/categories` | Daftar kategori simulasi |
| GET | `/` | Health check |

## 3. Export & Laporan

Frontend punya 3 cara export:

- **PDF** — generate HTML, buka tab baru, trigger print. Ada cover, tabel, grafik, confusion matrix ML.
- **CSV** — data mentah tiap putaran per agent. Pakai BOM UTF-8 biar Excel gak kacau.
- **Word (.docx)** — pakai library `docx` dari CDN. Ada tabel, ringkasan, prediksi.

Semua export logic ada di `frontend/src/app/utils/` — file `eksporpdf.js`, `eksporlainnya.js`.

## 4. Catatan Teknis

- **Rate limiter** masih in-memory — gak survive restart server. Maks 8 request per 60 detik per IP.
- **LLM cache** in-memory juga — TTL 1 jam. Berguna biar gak panggil Groq terus.
- **Gak ada autentikasi** — endpoint siapa pun bisa panggil selama IP gak kena rate limit.
- **Tier system**: "free" pake inline sentiment (gratis), "normal" pake LLM analysis + GraphRAG.

## Terkait

- [[Agent System]]
- [[Sentiment ML Pipeline]]
- [[Decision Intelligence Fields]]
- [[Vox Swarm]]
