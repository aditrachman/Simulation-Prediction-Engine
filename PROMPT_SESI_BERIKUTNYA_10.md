# Prompt untuk Claude — Sesi Berikutnya VoxSwarm (Sesi 10)

## Konteks Sistem

Kamu melanjutkan pengembangan **VoxSwarm** — Simulation-Prediction-Engine berbasis multi-agen LLM (Groq) + ML (scikit-learn). Stack yang sudah selesai:

```
backend/
  agents.py        — registry agen & counter-agent per kategori
  llm.py           — Groq client, retry, cache in-memory + TTL, token config
                     MAX_TOKENS_AGENT=350, MAX_TOKENS_SENTIMENT=80
                     SENTIMENT_MODE — konstanta yang sudah di-export
                     CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
                                 entry cache: {"value": str, "ts": float}
                                 expired jika CACHE_TTL > 0 dan (now - ts) > CACHE_TTL
                     clear_llm_cache() — flush manual, return jumlah entry dihapus
                     SOCIAL_TICK_DELAY = float(os.getenv("SOCIAL_TICK_DELAY", "1.0"))
                     _strip_emoji() — SATU-SATUNYA definisi, di-export ke modul lain
                     _EMOJI_PATTERN — pre-compiled regex (efisiensi)
  memory.py        — persistent agent memory per sesi
  sentiment.py     — sentiment scoring (LLM + inline fallback)
  graph.py         — GraphRAG-lite entity extraction
  simulation.py    — orchestration multi-agen multi-ronde (SEQUENTIAL)
                     SENTIMENT_MODE di-import dari llm.py
                     _strip_emoji di-import dari llm.py (BUKAN definisi lokal)
                     prompt analisis: plain text saja, TIDAK ada instruksi tabel/markdown
                     _resolve_nama(s, pengaruh_map, nama_valid) — MODULE-LEVEL private
                     _label_sentimen(skor) — MODULE-LEVEL private
                     analyze_key_actors() → pakai _resolve_nama, _label_sentimen,
                                            _build_ringkasan_agen(), _aktor_fallback()
                                            (TIDAK ada nested _resolve/_lb di dalam fungsi)
                     _aktor_fallback() → pakai _label_sentimen (bukan nested _lb)
  social_engine.py — simulasi sosial media (POST/REPLY/LIKE/QUOTE)
                     Fase 1: SEQUENTIAL loop (BUKAN ThreadPoolExecutor)
                     time.sleep(0.3) antar agen jika len(agents) > 3
                     time.sleep(SOCIAL_TICK_DELAY) di akhir setiap tick (kecuali terakhir)
                     SOCIAL_TICK_DELAY di-import dari llm.py
                     _strip_emoji di-import dari llm.py (BUKAN definisi lokal)
                     Semua komentar/docstring mencerminkan perilaku SEQUENTIAL
                     (tidak ada lagi kata "paralel" atau "bersamaan" di komentar)
  scraper.py       — RSS + Reddit fetch, disk cache TTL 30 menit
  ml_pipeline.py   — feature extraction, RandomForest, predict outcome
                     DATA_DIR: auto-detect backend/data/ atau root/data/
                     MIN_SAMPLES=5
                     train_model(): simpan model_trained_at.txt setelah training
                                    field "trained_at" ada di return dict
                     get_ml_status(): baca model_trained_at.txt → field "model_trained_at"
                     get_ml_metrics(): evaluasi LOO saat data < 20
                     weak label threshold range: 1.6
                     force_train_if_ready() → trigger manual training
                     auto-retrain periodik setiap kelipatan 5 simulasi baru
  feedback.py      — feedback loop ground truth
                     DATA_DIR di-import dari ml_pipeline.py (BUKAN hardcode)
                     FEEDBACK_FILE = DATA_DIR / "feedback.jsonl" (path selalu sama)
                     MIN_FEEDBACK_TO_RETRAIN=3
  engine.py        — compatibility shim

main.py (ROOT)     — FastAPI, semua endpoint:
                     GET  /ml-retrain-check → force_train_if_ready()
                          response: {status: "success"|"not_ready", ok, data, message}
                     POST /ml-train        → train_model(force=True)
                     GET  /ml-status       → status + debug_paths + model_trained_at
                     GET  /ml-metrics      → evaluasi performa model (LOO jika n < 20)
                     GET  /ml-debug        → distribusi label, imbalance warning, feature importance
                     GET  /ml-dataset-stats → statistik lengkap + drift summary
                     MAX_TOPIC_LENGTH = int(os.getenv("MAX_TOPIC_LENGTH", "300"))
                     SimRequest.topik    → max_length=MAX_TOPIC_LENGTH
                     SosmedRequest.topik → max_length=MAX_TOPIC_LENGTH (bukan hardcode 300)
                     FEEDBACK_FILE di-import dari backend.feedback (bukan hardcode path)

frontend/
  page.js          — Next.js client:
                     + PanelMLMetrics: fetch paralel /ml-metrics + /ml-debug + /ml-status
                     + PanelMLMetrics: state mlStatus → tampilkan model_trained_at
                     + PanelMLMetrics: tombol "Aktifkan ML Sekarang" → POST /ml-train ✅
                     + PanelMLMetrics: badge eval_method ditampilkan di sub-section Akurasi ✅
                     + PanelMLMetrics: warning overfitting jika accuracy >= 95% & n < 20
                     + PanelMLMetrics: distribusi label training dengan progress bar
                     + PanelMLMetrics: overfitting_risk badge dari /ml-debug

.env.example       — template semua env var (GROQ_API_KEY, ALLOWED_ORIGINS, model config,
                     token budget, rate limit config, SENTIMENT_MODE, ML_MIN_SAMPLES,
                     ML_MAX_HISTORY, CACHE_TTL, SOCIAL_TICK_DELAY)
```

---

## Bug & Issue yang Perlu Dikerjakan Sesi Ini

---

### 🔴 BUG #14 — `llm.py` Alignment Konstanta Tidak Konsisten Setelah Sesi 9

**File:** `backend/llm.py`

**Penyebab:** Setelah penambahan `SOCIAL_TICK_DELAY` dan `CACHE_TTL` di Sesi 9, alignment spasi antar konstanta di blok `RATE LIMIT CONFIG` tidak konsisten — sebagian pakai 1 spasi setelah `=`, sebagian pakai padding ke kolom tertentu. Ini bukan bug fungsional tapi melanggar gaya kode yang sudah ada.

**Contoh kondisi saat ini:**
```python
ROUND_DELAY         = float(os.getenv("ROUND_DELAY",         "3.0"))
SOCIAL_TICK_DELAY   = float(os.getenv("SOCIAL_TICK_DELAY",   "1.0"))
SENTIMENT_MODE      = os.getenv("SENTIMENT_MODE", "llm")   # "llm" ...
CACHE_TTL        = int(os.getenv("CACHE_TTL", "3600"))   # ← tidak aligned
```

**Yang harus dilakukan:** Seragamkan alignment `=` di seluruh blok `RATE LIMIT CONFIG` agar kolom nilai rata. Tidak ada perubahan logika. Contoh target:
```python
ROUND_DELAY       = float(os.getenv("ROUND_DELAY",       "3.0"))
SOCIAL_TICK_DELAY = float(os.getenv("SOCIAL_TICK_DELAY", "1.0"))
SENTIMENT_MODE    = os.getenv("SENTIMENT_MODE", "llm")
CACHE_TTL         = int(os.getenv("CACHE_TTL",  "3600"))
```

---

### 🔴 BUG #15 — `simulation.py` Header Modul Tidak Mencantumkan `_resolve_nama` dan `_label_sentimen`

**File:** `backend/simulation.py`

**Penyebab:** Komentar header di baris 1–11 mendaftarkan fungsi-fungsi publik modul, tapi `_resolve_nama()` dan `_label_sentimen()` yang baru ditambahkan di Sesi 9 belum tercantum. Developer yang membaca file pertama kali tidak tahu dua fungsi helper ini ada.

**Yang harus dilakukan:** Tambahkan dua baris ke komentar header:
```python
#   - _resolve_nama()         — resolve nama agen dari string bebas ke kanonik
#   - _label_sentimen()       — konversi skor float ke label positif/negatif/netral
```
Tidak ada perubahan logika.

---

### 🔴 BUG #16 — `clear_llm_cache()` Tidak Di-expose via Endpoint API

**File:** `backend/llm.py`, `main.py`

**Penyebab:** Fungsi `clear_llm_cache()` ditambahkan di Sesi 9 tapi tidak ada endpoint yang memanggilnya. Operator tidak bisa flush cache dari luar (misal setelah deploy topik baru yang sama dengan topik lama di cache).

**Yang harus dilakukan:**
- Tambahkan endpoint `POST /cache-clear-llm` di `main.py`
- Response: `{"status": "success", "cleared": <jumlah entry>}`
- Terapkan `_enforce_rate_limit` seperti endpoint lainnya
- Import `clear_llm_cache` dari `backend.llm` (atau lewat `backend.engine` jika sudah ada di shim)
- Tambahkan di tags `["Cache"]`

---

### 🟡 ISSUE #11 — `.env.example` Belum Mencantumkan `CACHE_TTL` dan `SOCIAL_TICK_DELAY`

**File:** `.env.example`

**Penyebab:** Dua konstanta baru dari Sesi 9 belum ada di `.env.example`. Developer baru yang clone repo tidak tahu variabel ini bisa dikonfigurasi.

**Yang harus dilakukan:** Tambahkan ke `.env.example` di seksi yang relevan:
```dotenv
# Cache LLM (TTL dalam detik; 0 = cache selamanya)
CACHE_TTL=3600

# Jeda antar tick simulasi sosmed (detik)
SOCIAL_TICK_DELAY=1.0
```
Posisikan `CACHE_TTL` di dekat konfigurasi cache lainnya, dan `SOCIAL_TICK_DELAY` di dekat `ROUND_DELAY`.

---

### 🟡 ISSUE #12 — `feedback.py` Tidak Punya Endpoint untuk Hapus Satu Entry Feedback

**File:** `backend/feedback.py`, `main.py`

**Penyebab:** Saat ini tidak ada cara untuk menghapus satu entry feedback yang salah label tanpa edit file `.jsonl` manual. Ini menyulitkan operasional.

**Yang harus dilakukan:**
- Tambahkan fungsi `delete_feedback_by_hash(topik_hash: str) -> bool` di `feedback.py`
  - Baca semua baris, filter baris yang `topik_hash`-nya cocok, tulis ulang file
  - Return `True` jika ada yang dihapus, `False` jika tidak ditemukan
  - Gunakan `_feedback_lock` agar thread-safe
- Tambahkan endpoint `DELETE /feedback/{topik_hash}` di `main.py`
  - Response sukses: `{"status": "success", "deleted": true}`
  - Response tidak ditemukan: HTTP 404
  - Terapkan `_enforce_rate_limit`

---

### 🟡 ISSUE #13 — `main.py` Endpoint `/cache-status` Tidak Tampilkan Info Cache LLM

**File:** `main.py`

**Penyebab:** Endpoint `/cache-status` saat ini hanya menampilkan info cache konteks real (scraper). Cache LLM (`_llm_cache`) tidak tercakup, padahal sekarang sudah punya TTL dan bisa di-flush.

**Yang harus dilakukan:** Tambahkan field `llm_cache` ke response `/cache-status`:
```json
{
  "llm_cache": {
    "entries": <jumlah entry aktif di _llm_cache>,
    "ttl_seconds": <nilai CACHE_TTL>
  }
}
```
Import yang dibutuhkan: `_llm_cache`, `_llm_cache_lock`, `CACHE_TTL` dari `backend.llm`.
Akses `len(_llm_cache)` dengan lock untuk thread-safety.

---

## Urutan Prioritas Pengerjaan Sesi Ini

```
1. 🔴 BUG #14  — Alignment konstanta llm.py
               File: llm.py
               REASON: cepat, zero risk, bersihkan technical debt Sesi 9

2. 🔴 BUG #15  — Header modul simulation.py
               File: simulation.py
               REASON: cepat, zero risk, dokumentasi akurat

3. 🔴 BUG #16  — Expose clear_llm_cache via endpoint
               File: main.py (+ verifikasi llm.py sudah punya clear_llm_cache)
               REASON: fungsionalitas penting untuk operasional

4. 🟡 ISSUE #13 — /cache-status tampilkan info LLM cache
               File: main.py
               REASON: kerjakan bersamaan BUG #16 karena file sama

5. 🟡 ISSUE #11 — .env.example update
               File: .env.example
               REASON: perlu kirim file .env.example dari developer dulu

6. 🟡 ISSUE #12 — Delete feedback by hash
               File: feedback.py, main.py
               REASON: paling kompleks, kerjakan terakhir
```

---

## File yang Perlu Diubah

| File | Bug/Issue |
|------|-----------|
| `backend/llm.py` | BUG #14 (alignment) |
| `backend/simulation.py` | BUG #15 (header modul) |
| `backend/feedback.py` | ISSUE #12 (delete_feedback_by_hash) |
| `main.py` | BUG #16 (endpoint cache-clear-llm), ISSUE #12 (endpoint DELETE /feedback), ISSUE #13 (/cache-status + llm cache info) |
| `.env.example` | ISSUE #11 (tambah CACHE_TTL, SOCIAL_TICK_DELAY) |

**File yang TIDAK boleh diubah:**
`agents.py`, `memory.py`, `sentiment.py`, `graph.py`, `ml_pipeline.py`,
`scraper.py`, `engine.py`, `social_engine.py`, `page.js`

---

## STRICT RULES — Berlaku Sepanjang Sesi

1. **Jangan ubah schema response API** — field baru boleh ditambah, field lama tidak boleh dihapus atau diubah tipenya
2. **Tidak ada LLM call baru** — jangan tambah call AI di luar yang sudah ada
3. **Thread-safe** — semua akses ke `_llm_cache` wajib pakai `_llm_cache_lock`; semua file write di `feedback.py` wajib pakai `_feedback_lock`
4. **Backward compatible** — `engine.py` adalah compatibility shim, jangan sentuh
5. **Groq free tier aware** — setiap perubahan harus mengurangi atau mempertahankan beban Groq, tidak menambah
6. **Jangan hardcode path** — selalu gunakan `DATA_DIR` dari `ml_pipeline.py` sebagai sumber kebenaran
7. **Jangan ubah kode yang tidak berkaitan** dengan bug/improvement yang dikerjakan
8. **Kirim semua file yang diubah** — developer langsung replace file di project dengan output dari Claude

---

## Catatan Penting State Sesi 9 (sudah selesai)

- `_llm_cache` sekarang bertipe `dict[str, dict]` dengan format `{"value": str, "ts": float}` — **jangan kembalikan ke `dict[str, str]`**
- `clear_llm_cache()` sudah ada di `llm.py` — tinggal di-expose via endpoint
- `SOCIAL_TICK_DELAY` sudah ada di `llm.py` dan sudah di-import di `social_engine.py`
- `CACHE_TTL` sudah ada di `llm.py`
- `_resolve_nama()` dan `_label_sentimen()` sekarang MODULE-LEVEL di `simulation.py` — **jangan buat nested lagi**
- `social_engine.py` Fase 1 sudah SEQUENTIAL dan komentar sudah sinkron — jangan ubah
- `SosmedRequest.topik` di `main.py` sudah pakai `MAX_TOPIC_LENGTH` — jangan hardcode lagi
- `main.py` ada di direktori **ROOT** (bukan di dalam `backend/`)
