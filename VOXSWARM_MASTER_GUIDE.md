# VoxSwarm — Master Development Guide
> Panduan lengkap untuk AI agent yang melanjutkan pengembangan VoxSwarm.
> Baca ini sampai habis sebelum menyentuh satu baris kode pun.

---

## 0. Konteks: Kamu Sedang Mengerjakan Apa

VoxSwarm adalah **simulasi opini publik Indonesia berbasis multi-agent AI**. Bayangkan kamu melempar sebuah isu ke meja diskusi, lalu beberapa orang dengan latar belakang berbeda (mahasiswa, pemerintah, jurnalis, dll.) berdebat selama beberapa ronde. VoxSwarm mensimulasikan diskusi itu, menganalisis siapa yang mendukung/menolak, dan memprediksi apakah isu akan memicu polarisasi, konsensus, atau status quo.

**Ini bukan mesin ramalan.** Ini adalah *scenario rehearsal engine* — alat eksplorasi, bukan prediksi faktual.

Referensi utama yang selalu kamu pegang:
- `VOXSWARM_PRD_ARAH_PROYEK.md` — visi dan arah produk (BACA INI DULU)
- `README.md` — cara install dan run
- `NEXT_PROMPT_FOR_CLAUDE (1).md` — bug report dari sesi sebelumnya

---

## 1. Peta Kode — Baca Sebelum Ubah Apapun

```
Simulation-Prediction-Engine/
│
├── main.py                    ← Entry point FastAPI. Semua endpoint ada di sini.
├── requirements.txt
│
├── backend/
│   ├── agents.py              ← Registry agen (Mahasiswa, Pemerintah, dll.) + counter-agents
│   ├── simulation.py          ← JANTUNG SISTEM. Loop simulasi multi-ronde per agen.
│   ├── sentiment.py           ← Scoring sentimen: LLM mode atau inline (keyword)
│   ├── memory.py              ← Update & build konteks memori agen antar ronde
│   ├── llm.py                 ← Groq client, retry, cache, call_llm()
│   ├── scraper.py             ← RSS feed + Reddit JSON API + disk cache
│   ├── ml_pipeline.py         ← Random Forest prediction dari histori simulasi
│   ├── feedback.py            ← Ground truth feedback dari operator → re-train
│   ├── graph.py               ← Ekstraksi entitas dari log diskusi (GraphRAG-lite)
│   │
│   └── core/                  ← Module arsitektur baru (Phase 2-8 PRD)
│       ├── models.py          ← AgentProfile, AgentState, SimulationEvent, dll.
│       ├── event_system.py    ← Event/intervensi sebagai object + impact scoring
│       ├── scheduler.py       ← Urutan bicara agen (sequential/random/influence_aware)
│       ├── prediction.py      ← Heuristic prediction + confidence score (tanpa ML)
│       ├── swarm.py           ← CrowdPool: rule-based crowd agents (Phase 8)
│       ├── memory_store.py    ← Structured memory: ArgumenMemory + RelationshipMemory
│       └── comparison.py      ← Bandingkan dua hasil simulasi (Phase 7)
│
└── frontend/
    └── src/app/
        ├── page.js            ← Landing page
        └── demo/page.js       ← Dashboard utama simulasi (chart, ekspor, dll.)
```

### Alur Data Utama (baca ini dulu sebelum debugging)

```
User input topik
    ↓
main.py /start-simulation
    ↓
scraper.py → ambil_konteks_real() → berita RSS + Reddit
    ↓
agents.py → get_agents() → pilih agen berdasarkan kategori
    ↓
simulation.py → run_simulation()
    │
    ├── [tiap ronde]
    │   ├── scheduler.py → get_speaking_order() → urutan agen
    │   ├── [tiap agen]
    │   │   ├── memory.py → build_memory_context() → konteks ronde lalu
    │   │   ├── llm.py → call_llm() → pendapat agen (via Groq)
    │   │   ├── sentiment.py → score_sentiment() → skor -1.0 s/d 1.0
    │   │   └── memory.py → update_agent_memory() → simpan ke memori
    │   └── [event_system.py jika ada intervensi]
    │
    ├── simulation.py → _analisis_dan_aktor() → 2 LLM call: analisis + aktor kunci
    ├── prediction.py → heuristic_predict() → prediksi rule-based
    ├── ml_pipeline.py → load_or_predict() → prediksi ML (jika model sudah ada)
    └── graph.py → extract_entities() → entitas & relasi (mode normal saja)
        ↓
Return JSON → frontend demo/page.js → render chart + laporan
```

---

## 2. Status Saat Ini — Apa yang Sudah Ada, Apa yang Belum

### ✅ Sudah Selesai (jangan rewrite, cukup perbaiki)

| Komponen | File | Keterangan |
|---|---|---|
| Simulation loop | `simulation.py` | Jalan, tapi ada beberapa bug output quality |
| Agent registry | `agents.py` | 7 agen utama + counter-agents, sudah ada `initial_stance` |
| Sentiment scoring | `sentiment.py` | Dua mode: LLM dan inline. Ada beberapa bug edge case |
| Memory context | `memory.py` | Sudah terintegrasi dengan `memory_store.py` |
| Event system | `core/event_system.py` | Selesai — intervensi sudah jadi object |
| Domain models | `core/models.py` | AgentProfile, AgentState, SimulationState, SimulationEvent |
| Scheduler | `core/scheduler.py` | 3 strategy: sequential, randomized, influence_aware |
| Heuristic prediction | `core/prediction.py` | Confidence score + reasoning sudah ada |
| Structured memory | `core/memory_store.py` | ArgumentMemory + RelationshipMemory sudah jalan |
| Scenario comparison | `core/comparison.py` | `generate_comparison_report()` sudah ada, belum ada endpoint |
| Crowd pool | `core/swarm.py` | CrowdPool sudah diinisialisasi, **tapi tidak berkontribusi ke output** |
| ML pipeline | `ml_pipeline.py` | Random Forest, butuh minimal 5 simulasi untuk aktif |
| Scraper | `scraper.py` | RSS + Reddit + disk cache sudah jalan |
| Frontend dashboard | `demo/page.js` | Chart, ekspor PDF/CSV/Word sudah ada |

### 🔴 Bug Aktif yang Harus Difix (Prioritas Tertinggi)

Lihat Section 3 untuk detail lengkap dan cara fixnya.

### ⏳ Belum Dibangun (dari PRD)

| Yang Dibutuhkan PRD | Status | Catatan |
|---|---|---|
| `core/state_engine.py` | ❌ Belum ada | Update state agen secara formal |
| `core/metrics.py` | ❌ Belum ada | Polarization, volatility, consensus metrics dedicated |
| `core/reporting.py` | ❌ Belum ada | Explainability report generator |
| Endpoint `/compare` | ❌ Belum ada | `comparison.py` sudah ada tapi belum diekspos |
| AgentFactory | ❌ Belum ada | Injeksi agen kontekstual berdasarkan keyword topik |
| Crowd berkontribusi ke analisis | ⚠️ Setengah | CrowdPool jalan tapi outputnya tidak dipakai di mana-mana |
| Prediction source label | ⚠️ Campur | Heuristic dan ML output bercampur tanpa label jelas |

---

## 3. Bug Aktif — Fix Ini Dulu Sebelum Tambah Fitur Baru

> **ATURAN PENTING:** Sebelum fix bug apapun, baca file terkait sampai habis. Banyak fix sebelumnya sudah ada di kode tapi belum sempurna.

### BUG-17 — Sentiment Mismatch: "Tidak Setuju" Diabaikan
**File:** `backend/sentiment.py` → fungsi `_score_llm()`

**Masalah:** Jika teks agen dimulai dengan kalimat positif, lalu di kalimat akhir ada "kami tidak setuju" — LLM scorer mengambil sinyal awal, mengabaikan penolakan di akhir. Hasilnya: teks yang jelas menolak dapat skor positif (+0.35).

**Root cause:** Instruksi di `_score_llm()` belum cukup tegas bahwa frasa penolakan di kalimat *manapun* adalah penentu akhir.

**Fix yang dibutuhkan:**
Perkuat instruksi BUG-17 FIX yang sudah ada di `_score_llm()`. Tambahkan:
```
"Jika ada 'kami tidak setuju', 'saya tidak setuju', 'kami menolak', 'saya menolak'
di kalimat MANAPUN — termasuk kalimat terakhir — label HARUS NEGATIF.
TIDAK ADA PENGECUALIAN. Kalimat penolakan = kesimpulan akhir, bukan hanya konteks."
```
Dan tambahkan contoh eksplisit ke dalam instruksi system prompt.

**Test case:** Teks "Dokumen menunjukkan data A cukup kuat. Namun kami tidak setuju dengan kesimpulan itu." → HARUS skor negatif (-0.5 s/d -0.7), bukan positif.

---

### BUG-18 — Oposisi Kritis Dapat Skor +1.0 (Mendukung Penuh)
**File:** `backend/sentiment.py` → fungsi `_score_llm()`

**Masalah:** Pertanyaan kritis seperti "apakah alokasi anggaran efektif dan efisien?" dari agen Oposisi Kritis dibaca sebagai dukungan (+1.0) oleh LLM scorer.

**Root cause:** LLM tidak membaca konteks *siapa yang berbicara*. Pertanyaan efisiensi dari oposisi = skeptisisme terselubung, bukan pujian.

**Fix yang dibutuhkan:**
Instruksi BUG-18 FIX sudah ada di `_score_llm()` tapi kurang kuat. Tambahkan:
```
"Pertanyaan yang mengandung kata 'apakah', 'seberapa', 'bagaimana' yang mempertanyakan
efektivitas/efisiensi/keberhasilan suatu kebijakan = NEGATIF atau NETRAL (skeptis),
BUKAN positif — terlepas dari siapa yang bertanya."
```

**Test case:** "Pertanyaan yang lebih relevan adalah apakah alokasi anggaran tersebut efektif dan efisien" → HARUS skor antara -0.3 dan 0.0, bukan +1.0.

---

### BUG-19 — Akademisi Fence-Sitting (2 Ronde Netral Berturut-turut)
**File:** `backend/simulation.py` → `_proses_satu_agen()`

**Masalah:** Akademisi bisa netral 2 ronde berturut-turut, padahal sudah ada data yang cukup untuk mengambil posisi. `conviction_rule` dan retry sudah ada tapi masih bisa di-bypass LLM.

**Fix yang dibutuhkan:**
`conviction_rule` dan BUG-19 retry sudah ada di kode. Yang perlu diperkuat adalah **post-processing enforcement** — jika setelah retry Akademisi masih netral tapi seharusnya tidak, paksa skor minimal ke ±0.25.

Tambahkan logic setelah blok retry di `_proses_satu_agen()`:
```python
# Jika masih netral setelah retry + sudah 2 ronde netral → paksa skor kecil
if ("akademisi" in agen["nama"].lower() and 
    sentimen["label"] == "netral" and 
    dua_ronde_netral):
    # Ambil arah dari initial_stance atau ronde pertama jika ada
    initial = agen.get("initial_stance", 0.0)
    forced_skor = 0.3 if initial >= 0 else -0.3
    sentimen = {"label": "positif" if forced_skor > 0 else "negatif", "skor": forced_skor}
```

---

### BUG-20 — Output Agen Terlalu Panjang
**File:** `backend/simulation.py` → fungsi `_batasi_kalimat()`

**Masalah:** Pemerintah masih bisa output 6-7 kalimat. `_batasi_kalimat()` hanya split di `.!?` — kalimat panjang dengan banyak koma tidak terpotong.

**Fix yang dibutuhkan:**
Fungsi `_batasi_kalimat()` sudah ada. Modifikasi bagian deteksi "kalimat tunggal panjang":
- Turunkan threshold dari `40` kata → `30` kata
- Tambahkan split di titik koma (`;`) sebagai pemisah tambahan
- Tambahkan hard cap: **45 kata total** — jika output > 45 kata setelah semua proses, potong di kata ke-45 lalu tambahkan titik

---

### PERF-01 — Generate Lambat (~44 LLM Calls per Simulasi)
**Status:** Sudah dimitigasi sebagian dengan `SENTIMENT_MODE=inline`.

**Solusi cepat (sudah tersedia):** Set di `.env`:
```
SENTIMENT_MODE=inline
```
Ini eliminasi ~21 LLM calls. Trade-off: akurasi sentimen sedikit turun untuk kalimat kompleks.

**Solusi jangka panjang:** Batch scoring sentiment — kumpulkan semua output satu ronde, score sekaligus dalam 1 LLM call. Implementasi ada di `simulation.py` bagian loop ronde.

---

## 4. Prioritas Pengembangan — Urutan yang Benar

Ikuti urutan ini. Jangan loncat ke fitur baru sebelum bug selesai.

### Fase A — Hotfix Output Quality (SEKARANG)
1. Fix BUG-17 di `sentiment.py`
2. Fix BUG-18 di `sentiment.py`
3. Fix BUG-20 di `simulation.py` (`_batasi_kalimat`)
4. Fix BUG-19 di `simulation.py` (Akademisi enforcement)

**Cara verifikasi:** Jalankan simulasi dengan topik "Prabowo: Dunia Banyak Pertikaian, Indonesia Harus Bangun Pertahanan". Cek:
- Jurnalis: teks menolak → skor negatif ✓
- Oposisi Kritis: pertanyaan efisiensi → skor ≤ 0 ✓
- Akademisi: tidak boleh 2 ronde netral berturut-turut ✓
- Semua agen: output ≤ 3 kalimat, ≤ 45 kata ✓

### Fase B — Fitur yang Setengah Jalan (SETELAH BUG SELESAI)

#### B1 — Ekspos Endpoint `/compare` (Scenario Comparison)
`core/comparison.py` sudah lengkap dengan `generate_comparison_report()`. Yang kurang hanya endpoint di `main.py`.

Tambahkan di `main.py`:
```python
class ComparePayload(BaseModel):
    topik: str
    intervensi_a: Optional[str] = None  # baseline (tanpa intervensi)
    intervensi_b: Optional[str] = None  # dengan intervensi
    kategori: str = "Umum"
    jumlah_ronde: int = 3

@app.post("/compare")
async def compare_scenarios(payload: ComparePayload, request: Request):
    # Jalankan 2 simulasi, bandingkan hasilnya
    # Gunakan generate_comparison_report() dari core/comparison.py
```

#### B2 — Crowd Berkontribusi ke Analisis
`CrowdPool` di `core/swarm.py` sudah jalan dan update per ronde, tapi hasilnya tidak dipakai di mana-mana.

Di `simulation.py`, setelah `crowd_data = crowd_pool.to_dict()`, integrasikan distribusi crowd ke `simulation_metrics`:
```python
if crowd_data:
    crowd_distribution = crowd_data.get("distribution", {})
    simulation_metrics["crowd_mendukung"] = crowd_distribution.get("mendukung", 0)
    simulation_metrics["crowd_menolak"] = crowd_distribution.get("menolak", 0)
    simulation_metrics["crowd_netral"] = crowd_distribution.get("netral", 0)
```
Dan tampilkan di frontend (`demo/page.js`).

#### B3 — Prediction Source Label yang Jelas
Saat ini `prediksi` (persentase) datang dari `_parse_prediksi()` yang parse teks LLM, sedangkan `prediction_confidence` datang dari heuristic. Ini dua sumber berbeda yang tidak berlabel.

Tambahkan field `prediction_source` ke return `run_simulation()`:
```python
"prediction_source": {
    "prediksi": "llm_analisis",         # atau "heuristic_fallback"
    "confidence": "heuristic",
    "ml_aktif": bool(ml_result),        # apakah ML model berkontribusi
}
```
Dan tampilkan di frontend sebagai disclaimer kecil di bawah chart prediksi.

### Fase C — Fitur Baru dari PRD (SETELAH FASE B)

#### C1 — AgentFactory (Agen Kontekstual)
Implementasi sesuai `AGENT_FACTORY_GUIDE.md` yang sudah ada:
1. Buat `backend/agent_factory.py` dengan `ARCHETYPE_POOL` + `get_contextual_agents()`
2. Edit `main.py` untuk inject agen kontekstual sebelum `run_simulation()`
3. Test: topik "kenaikan BBM" → harus inject Ibu Rumah Tangga + Buruh Pabrik

Archetype pool yang perlu dibuat (dari panduan sebelumnya):
`Perwira_TNI`, `Dokter_Nakes`, `Petani`, `Nelayan`, `Ulama`, `Buruh_Pabrik`, `Aktivis_Lingkungan`, `Guru`, `Startup_Founder`, `Kepala_Daerah`, `Ibu_Rumah_Tangga`, `Pengamat_Hukum`, `Diaspora`, `Pengusaha_Besar`, `Aktivis_HAM`

#### C2 — `core/metrics.py` (Metrics Formal)
Buat file baru `backend/core/metrics.py`. Pindahkan kalkulasi polarization/volatility/consensus yang sekarang tersebar di `simulation.py` dan `core/models.py` ke satu tempat:

```python
def compute_polarization(sentimen_agregat: dict) -> float: ...
def compute_volatility(sentimen_agregat: dict) -> dict: ...
def compute_consensus(sentimen_agregat: dict) -> float: ...
def compute_conflict_score(sentimen_agregat: dict) -> float: ...
```

#### C3 — `core/reporting.py` (Explainability Report)
Buat file baru `backend/core/reporting.py`. Ini yang paling penting untuk PRD karena *explainability* adalah pembeda utama VoxSwarm.

Report harus menjawab:
- Kenapa hasilnya polarisasi/konsensus/status quo? (sebab-akibat, bukan cuma angka)
- Siapa aktor paling berpengaruh dan kenapa?
- Argumen mana yang paling sering memicu perubahan stance?
- Event mana yang berdampak signifikan?
- Seberapa yakin sistem? (confidence dengan alasan)

---

## 5. Aturan Wajib — Jangan Langgar Ini

### Aturan Kode

1. **Jangan rewrite simulation.py dari nol.** Migrasi harus bertahap. Kode lama tetap jalan.

2. **Jangan tambah LLM call tanpa alasan kuat.** Setiap LLM call tambahan = lebih lambat + lebih mahal. Selalu tanya dulu: bisa dikerjakan pure Python?

3. **Backward compatible.** Semua modul baru di `core/` harus punya adapter ke format dict lama. Lihat pola di `models.py` → `agent_dict_to_profile()` dan `agent_profile_to_dict()`.

4. **Jangan ubah schema return `run_simulation()` secara breaking.** Frontend bergantung pada field-field ini. Tambahkan field baru, jangan hapus yang lama.

5. **Ikuti pola error handling yang ada.** Setiap agen punya fallback response jika error. Lihat blok `try/except` di loop per agen di `simulation.py`.

6. **Test di dua mode:** `tier="free"` (4 agen, 2 ronde, sentiment inline) dan `tier="normal"` (7 agen, 5 ronde, sentiment LLM). Perubahan tidak boleh break salah satunya.

### Aturan Produk (dari PRD)

1. **Jangan klaim prediksi akurat.** Semua output harus disertai disclaimer bahwa ini simulasi eksploratif, bukan prediksi faktual.

2. **Jangan sebut "GraphRAG" jika belum ada graph retrieval.** Saat ini hanya entity extraction — sebut "entity extraction" saja.

3. **ML layer diberi label "experimental"** sampai ada validasi dengan data nyata.

4. **Agent adalah archetype sosial, bukan representasi statistik.** Jangan klaim "ini mewakili 30% populasi Indonesia."

---

## 6. Cara Kerja Komponen Penting — Penjelasan Sederhana

### Bagaimana Agen Berpendapat

Setiap agen mendapat tiga input ke LLM:
1. **System prompt** — siapa dia, gaya bicara, posisi awal, aturan
2. **User prompt** — konteks memori ronde lalu + apa yang sudah dikatakan agen lain + topik
3. **Constraints** — max token, model yang dipakai

Output teks dari LLM lalu di-post-process:
- `filter_forbidden_opens()` — hapus kalimat yang dimulai dengan frasa terlarang
- `_batasi_kalimat()` — potong maksimal 3 kalimat
- `score_sentiment()` — beri skor -1.0 s/d 1.0

### Bagaimana Sentiment Scoring Bekerja

**Mode LLM (`SENTIMENT_MODE=llm`):**
- Panggil Groq dengan sistem prompt classifier
- Return JSON `{"label": "positif|netral|negatif", "skor": float}`
- Jika LLM gagal parse JSON → fallback ke mode inline

**Mode Inline (`SENTIMENT_MODE=inline`):**
- Hitung kata positif dan negatif di teks
- Deteksi negasi (tidak, nggak, bukan) di jendela 3 kata sebelumnya
- Threshold ±0.35 untuk label non-netral

**Kapan pakai mana:**
- Mode free/hemat → inline (0 LLM call tambahan)
- Mode normal → LLM (lebih akurat untuk kalimat kompleks)

### Bagaimana Memory Bekerja

Setiap agen punya dua lapisan memori:
1. **`agent["memori"]`** — list dict `{ronde, pendapat, label, skor}`. Format lama, masih dipakai.
2. **`agent["_memory_store"]`** — `AgentMemoryStore` dari `core/memory_store.py`. Format baru, berisi:
   - `ArgumentMemory` — lacak argumen unik, cegah repetisi
   - `RelationshipMemory` — lacak hubungan/trust antar agen

Keduanya di-update setiap kali `update_agent_memory()` dipanggil.

### Bagaimana Prediksi Bekerja

Ada **tiga layer prediksi** yang berjalan bersamaan:
1. **Heuristic** — `core/prediction.py` → rule-based dari distribusi sentimen akhir. Selalu jalan.
2. **ML (Random Forest)** — `ml_pipeline.py` → butuh minimal 5 simulasi di histori. Jika belum siap, fallback ke rule-based.
3. **LLM analisis** — `_analisis_dan_aktor()` → parse persentase dari teks analisis LLM.

Saat ini ketiga layer tidak berlabel jelas ke user. Ini yang perlu diperbaiki di Fase B3.

---

## 7. Environment Variables Penting

```env
# WAJIB
GROQ_API_KEY=gsk_...

# Model
MODEL_AGENT=llama-3.1-8b-instant        # untuk suara agen (cepat, hemat)
MODEL_ANALYSIS=llama-3.3-70b-versatile  # untuk analisis akhir (akurat)

# Performa
SENTIMENT_MODE=llm          # llm (akurat) atau inline (cepat, hemat)
AGENT_CALL_DELAY=1.0        # detik jeda antar agen (turunkan jika tidak rate limit)
ROUND_DELAY=2.0             # detik jeda antar ronde

# ML
ML_MIN_SAMPLES=5            # minimal simulasi sebelum ML aktif
ML_MAX_HISTORY=500          # cap histori

# Rate limit
RATE_LIMIT_MAX_REQUESTS=8   # per IP per window
RATE_LIMIT_WINDOW_SEC=60
```

---

## 8. Checklist Sebelum Commit

Setiap kali kamu selesai mengerjakan sesuatu, pastikan:

- [ ] Simulasi mode `free` masih jalan tanpa error
- [ ] Simulasi mode `normal` masih jalan tanpa error
- [ ] Return schema `run_simulation()` tidak ada field yang hilang
- [ ] Tidak ada LLM call baru yang tidak perlu
- [ ] Tidak ada print/log debug yang ditinggal di production code
- [ ] Kode baru di `core/` punya adapter backward compatible
- [ ] Bug yang di-fix punya test case yang bisa diverifikasi manual

---

## 9. Glossary — Istilah yang Sering Muncul

| Istilah | Artinya |
|---|---|
| `tier` | "free" (cepat, 4 agen, 2 ronde) atau "normal" (lengkap, 7 agen, 5 ronde) |
| `initial_stance` | Posisi awal agen sebelum diskusi. -1.0 = sangat menolak, +1.0 = sangat mendukung |
| `pengaruh` | Bobot pengaruh agen terhadap agen lain. 0.0–1.0 |
| `sentimen_agregat` | Dict `{nama_agen: [skor_r1, skor_r2, ...]}` — tren per agen |
| `ronde_detail` | List output tiap ronde `[{ronde: int, agen: [{nama, pendapat, sentimen}]}]` |
| `counter-agent` | Agen yang sengaja berposisi berlawanan untuk cegah echo chamber |
| `conviction_rule` | Aturan prompt yang mencegah Akademisi fence-sitting |
| `stance_lock` | Aturan prompt yang mencegah Pemerintah flip ke menolak kebijakannya sendiri |
| `_batasi_kalimat` | Fungsi post-processing yang potong output maksimal 3 kalimat |
| `filter_forbidden_opens` | Fungsi post-processing yang hapus kalimat dengan pembuka terlarang |
| `heuristic predict` | Prediksi berbasis aturan Python, tanpa LLM, tanpa ML |
| `simulation_quality` | Skor 0–1 yang menilai kualitas metodologis simulasi (bukan akurasi) |
| `topik_hash` | Hash MD5 dari topik, dipakai sebagai ID unik untuk feedback |

---

## 10. Yang Paling Penting — Filosofi Produk

VoxSwarm bukan tentang prediksi yang akurat. VoxSwarm tentang **membantu orang melihat kemungkinan dinamika** sebelum sebuah isu dilempar ke publik.

Karena itu, dua hal yang paling berharga dari VoxSwarm adalah:

1. **Explainability** — bukan cuma "polarisasi 60%", tapi "kenapa? siapa yang memicu? argumen apa yang mengubah arah?"
2. **Kejujuran** — selalu tampilkan confidence note, disclaimer, dan limitation. Jangan overclaim.

Setiap fitur baru yang kamu tambahkan harus dievaluasi dengan pertanyaan ini:
> *Apakah ini membantu user memahami dinamika opini dengan lebih baik, atau ini hanya terlihat canggih?*

Jika jawabannya yang kedua, jangan tambahkan dulu.

---

*Guide ini dibuat berdasarkan pembacaan penuh kode VoxSwarm per 29 Mei 2026.*
*Update guide ini setiap kali ada perubahan arsitektur besar.*
