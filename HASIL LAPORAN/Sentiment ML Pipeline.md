---
tags: [project/voxswarm, type/ml-pipeline]
---

# Sentiment ML Pipeline — Model, Cross-Validation, Endpoint

VoxSwarm punya dua sistem ML yang beda fungsi: **sentiment classifier** (buat nentuin sikap agent) dan **prediction model** (buat nebak hasil diskusi).

## 1. Sentiment Analysis (`backend/sentiment.py`)

Ini yang nentuin apakah pendapat seorang agent "setuju", "netral", atau "tidak setuju". Ada 3 mode:

### Mode 1: Inline (gratis — dipake free tier)
Cocokokin kata kunci dari dictionary. Contoh kata positif: "setuju", "mendukung", "baik". Kata negatif: "tolak", "salah", "buruk". Cepet dan gratis tapi kurang akurat.

### Mode 2: ML (`backend/sentiment_ml.py`) — TF-IDF + LogisticRegression
- Pakai scikit-learn (TF-IDF Vectorizer + LogisticRegression)
- Training data: bootstrap dataset pake istilah kebijakan Indonesia
- Model disimpen ke `models/sentiment_model.pkl`
- Otomatis train pas pertama kali dipake
- Ada fungsi `explain()` — kasih tau kata mana yang paling pengaruh ke hasil sentimen

### Mode 3: LLM (paling akurat — dipake normal tier)
Panggil Groq API buat analisis sentimen per teks. Paling mahal tapi paling akurat.

## 2. ML Prediction Pipeline (`backend/ml_pipeline.py`)

Ini yang nebak skenario akhir diskusi: apakah bakal **Konsensus**, **Polarisasi**, atau **Status Quo**.

### Cara Kerja

1. **Feature Extraction** — ambil 22 fitur dari hasil simulasi. Contoh:
   - Rata-rata, standar deviasi, nilai min/max sentimen agent
   - Proporsi stance (berapa agent yang pro/kontra)
   - Volatilitas (seberapa sering agent berubah pikiran)
   - Jumlah event, dampak event
   - Depth memori (berapa banyak argumen unik)
   - Jumlah kata, entitas, kategori

2. **RandomForest Classifier** — modelnya RandomForest dari scikit-learn. Disimpen pake joblib.

3. **Training** — otomatis setiap 5 simulasi atau pas ada 3 feedback baru. Tapi training baru bener-bener jalan kalau data >= 20 simulasi.

4. **Prediction** — ngasih probabilitas buat tiap skenario. Tapi ingat: **prediksi utama tetap dari heuristic**, ML cuma experimental.

### Feedback Loop (`backend/feedback.py`)

- User/kirim ground truth lewat `POST /feedback`
- Label beneran dari operator ini dipake buat koreksi weak label
- Feedback disimpen di `backend/data/feedback.jsonl`
- Kalau total feedback >= 5, auto-trigger retrain

### Endpoint yang Tersedia

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/ml-status` | Status ML: jumlah data, model aktif? |
| GET | `/ml-metrics` | Evaluasi: akurasi, confusion matrix, precision/recall/F1 |
| GET | `/ml-debug` | Diagnostik: distribusi label, fitur penting, overfitting risk |
| GET | `/ml-dataset-stats` | Statistik dataset training lengkap + drift analysis |
| GET | `/ml-retrain-check` | Cek apakah siap retrain |
| POST | `/ml-train` | Force retrain |
| GET | `/sentiment-ml-metrics` | Evaluasi sentiment classifier (TF-IDF) |
| POST | `/feedback` | Kirim ground truth label |
| GET | `/feedback-stats` | Statistik feedback |
| DELETE | `/feedback/{hash}` | Hapus feedback |

## 3. Prediksi Heuristic (yang Jadi Patokan Utama)

Meskipun ada ML, **prediksi utama selalu dari heuristic** (di `backend/core/prediction.py`). Caranya:

1. Hitung 6 faktor: support ratio, average sentiment, polarization, opposition intensity, momentum (perubahan ronde terakhir), volatility
2. Weighted average dari 6 faktor itu
3. Sesuaikan dengan event impact
4. Keluarin probabilitas: Konsensus / Polarisasi / Status Quo

Heuristic ini lebih stabil dan gak butuh data training. ML cuma cadangan experimental.

## 4. Evaluasi Model

ML model di-evaluate pake:
- **5-fold cross-validation** (kalau data >= 20)
- **Fallback train=test** (kalau data masih sedikit)
- **Confusion matrix 3×3** (Konsensus / Polarisasi / Status Quo)
- **Precision, Recall, F1-score** per kelas

Tapi perhatian: kalau data masih < 20 sampel, akurasi tinggi bisa berarti model hafal (overfitting), bukan bener-bener belajar.

## Terkait

- [[Agent System]]
- [[Arsitektur]]
- [[Decision Intelligence Fields]]
- [[Vox Swarm]]
