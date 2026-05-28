# VoxSwarm — Next Prompt for Claude
**Tanggal:** 26 Mei 2026  
**Sesi:** Hotfix Fase 3  
**Topik Test:** Prabowo: Dunia Banyak Pertikaian, Indonesia Harus Bangun Pertahanan

---

## 📁 FILE YANG SUDAH DI-FIX (Fase 1 & 2)

- `simulation.py` — BUG-10, 11, 12, 13, 16, ERROR-1 (UnboundLocalError Akademisi)
- `sentiment.py` — BUG-07, 09, 15
- `agents.py` — BUG-14 (initial_stance semua agen)

---

## 🔴 BUG YANG MASIH ADA (dari laporan 26 Mei 2026)

### BUG-17: Jurnalis P2 Label-Skor Mismatch (BUG-15 belum fix sempurna)
```
Jurnalis P2 teks: "kami tidak setuju dengan pendapat Prabowo bahwa Indonesia 
harus membangun kekuatan pertahanan sebagai solusi konflik global."
Skor aktual: +0.35 (Mendukung) ❌
Skor expected: -0.5 (Menolak)
```
**Root cause:** Teks di awal kalimat positif ("Dokumen menunjukkan bahwa..."),
baru di kalimat terakhir ada "kami tidak setuju" — LLM scorer ambil sinyal awal,
bukan kesimpulan akhir.
**Fix:** Perkuat instruksi di `_score_llm()`: "Jika ada 'kami tidak setuju',
'saya tidak setuju', 'kami menolak' di kalimat MANAPUN → label NEGATIF,
terlepas dari isi kalimat lain."

---

### BUG-18: Oposisi Kritis P1 Skor +1.0 (Mendukung Penuh) Padahal Teks Netral
```
Oposisi Kritis P1 teks: "pertanyaan yang lebih relevan adalah apakah alokasi 
anggaran tersebut efektif dan efisien"
Skor aktual: +1.0 (Mendukung penuh) ❌
Skor expected: -0.3 sampai 0.0 (Skeptis/Netral)
```
**Root cause:** Kalimat tentang "efektivitas" dibaca sebagai dukungan oleh scorer.
Pertanyaan efisiensi dari Oposisi = kritik terselubung, bukan pujian.
**Fix:** Tambah contoh ke `_score_llm()`:
"'apakah alokasi anggaran efektif?' dari Oposisi → NEGATIF atau NETRAL, bukan positif."
**Related:** BUG-15 (pertanyaan retoris kritis)

---

### BUG-19: Akademisi Fence-Sitting 2 Ronde Berturut-turut (conviction_rule tidak efektif)
```
Akademisi P1: Netral 0 — "Studi 2023 menunjukkan sebagian besar konflik karena ketidakstabilan"
Akademisi P2: Netral 0 — "tidak sepenuhnya tidak masuk akal"
Akademisi P3: Mendukung 0.7 ✓ (baru bergerak)
```
**Root cause:** conviction_rule sudah ada tapi LLM masih bisa escape ke netral
dengan alasan "butuh data lebih". Initial_stance 0.0 untuk Akademisi
terlalu mudah di-maintain sebagai netral tanpa alasan.
**Fix:** 
1. Di `agents.py`, ubah initial_stance Akademisi dari 0.0 ke nilai yang
   mendorong LLM ambil posisi (misal: setelah P1 netral, force posisi di P2)
2. Di `simulation.py`, tambah rule: "Jika Akademisi sudah 2x netral berturut-turut,
   WAJIB ambil posisi di ronde berikutnya — jelaskan data yang condong ke mana."

---

### BUG-20: Output Masih Terlalu Panjang (BUG-16 fix belum cukup)
```
Pemerintah P1: 7 kalimat (seharusnya max 3, role sudah bilang max 2)
Pemerintah P3: 6 kalimat
Pekerja P3:    5 kalimat dengan "Namun" clause panjang
```
**Root cause:** `_batasi_kalimat()` BUG-16 fix potong di 60 kata,
tapi Pemerintah pakai kalimat panjang dengan banyak koma — tidak ada titik,
jadi split tidak bekerja. Batas 60 kata belum cukup ketat.
**Fix:**
1. Turunkan batas dari 60 kata → 40 kata untuk deteksi "kalimat tunggal panjang"
2. Tambah split di koma + "Kami juga" / "Selain itu" / "Dengan demikian" sebagai pemisah tambahan
3. Atau: enforce hard limit 45 kata total untuk semua output (bukan per kalimat)

---

### BUG-21: Pekerja Kantoran P1 Mengutip Verbatim Agen Lain
```
Pekerja P1: "Pengusaha/UMKM: Dari sisi bisnis, ini artinya Indonesia harus 
memprioritaskan pengeluaran anggaran..."
```
**Root cause:** LLM memulai output dengan mengutip langsung kata-kata agen lain
beserta nama dan tanda titik dua. Filter `_FORBIDDEN_OPENS` tidak cover pola "NamaAgen: ..."
**Fix:** Tambah pattern ke `_FORBIDDEN_OPENS` di `sentiment.py`:
```python
r"^[A-Z][a-zA-Z/]+\s*:",  # Pattern: "NamaAgen: ..."
r"^Pengusaha",
r"^Pekerja",
r"^Pemerintah",
r"^Mahasiswa",
r"^Akademisi",
r"^Jurnalis",
r"^Masyarakat",
```
Dan tambah ke system prompt: "JANGAN pernah memulai output dengan nama agen lain
diikuti titik dua ('Pengusaha: ...'). Langsung ke argumenmu sendiri."

---

## 🐌 ISSUE BARU: GENERATE LAMBAT (Performance)

### Estimasi waktu saat ini (7 agen × 3 ronde):
```
Per agen = 1 LLM call (pendapat) + 1 LLM call (sentiment) = 2 calls
Per ronde = 7 agen × 2 calls = 14 calls
3 ronde   = 42 calls agen
+ 2 calls analisis akhir
= ~44 total LLM calls
```

**Ditambah delay:**
- AGENT_CALL_DELAY × (7 agen × 3 ronde) = delay agen
- ROUND_DELAY × 3 ronde = delay ronde

### Fix Opsi 1 — CEPAT (ganti SENTIMENT_MODE):
Di `.env`:
```
SENTIMENT_MODE=inline
```
Ini eliminasi **21 LLM calls** sekaligus — waktu generate bisa turun 40-50%.
Trade-off: akurasi sentimen sedikit turun untuk kalimat kompleks.

### Fix Opsi 2 — STRUKTURAL (batch sentiment):
Daripada score_sentiment() dipanggil per agen (sequential),
kumpulkan semua output satu ronde dulu, lalu score sekaligus dalam 1 LLM call.
```python
# Bukan: score per agen (7 calls per ronde)
# Tapi: 1 call untuk semua agen sekaligus
def score_sentiment_batch(outputs: list[dict], topik: str) -> list[dict]:
    """Score semua agen dalam 1 LLM call — hemat 6 calls per ronde."""
    ...
```
Estimasi hemat: dari 44 calls → 26 calls (hemat ~40%).

### Fix Opsi 3 — DELAY TUNING:
Cek nilai AGENT_CALL_DELAY dan ROUND_DELAY di llm.py atau .env.
Jika > 1 detik, turunkan ke 0.5 detik (atau 0 jika tidak ada rate limit issue).
Ini tidak mengurangi LLM calls tapi mengurangi waktu tunggu antar call.

### Rekomendasi urutan:
1. **Segera:** Ganti SENTIMENT_MODE=inline → paling mudah, impact besar
2. **Berikutnya:** Turunkan AGENT_CALL_DELAY
3. **Jangka panjang:** Implementasi batch sentiment scoring

---

## 📋 QUICK SUMMARY TABLE

| # | Bug/Issue | Severity | File | Action |
|---|-----------|----------|------|--------|
| BUG-17 | Jurnalis P2 skor +0.35 padahal teks menolak | 🔴 HIGH | sentiment.py | Fix _score_llm: "tidak setuju" di kalimat manapun → negatif |
| BUG-18 | Oposisi Kritis P1 skor +1.0 padahal teks netral/kritis | 🔴 HIGH | sentiment.py | Tambah contoh pertanyaan efisiensi dari Oposisi → negatif |
| BUG-19 | Akademisi 2 ronde netral berturut-turut | 🟡 MED | simulation.py | Force posisi setelah 2x netral berturut-turut |
| BUG-20 | Output masih terlalu panjang (Pemerintah 6-7 kalimat) | 🟡 MED | simulation.py | Turunkan batas _batasi_kalimat, tambah pemisah koma |
| BUG-21 | Pekerja mengutip verbatim nama agen lain | 🟡 MED | sentiment.py + simulation.py | Tambah forbidden pattern "NamaAgen: ..." |
| PERF-01 | Generate lambat (~44 LLM calls per simulasi) | 🔴 HIGH | .env / simulation.py | SENTIMENT_MODE=inline ATAU batch scoring |

---

## 🚀 FIX ORDER

1. **PERF-01** — Ganti SENTIMENT_MODE=inline di .env (5 menit, no code change)
2. **BUG-17 & BUG-18** — Fix _score_llm() sentiment.py (30 menit)
3. **BUG-21** — Tambah forbidden pattern simulation.py + sentiment.py (15 menit)
4. **BUG-20** — Fix _batasi_kalimat() simulation.py (20 menit)
5. **BUG-19** — Fix conviction_rule Akademisi simulation.py (20 menit)

**Estimated total:** ~1.5 jam

---

## ✅ SUCCESS CRITERIA (laporan berikutnya harus menunjukkan)

- ✅ Generate selesai < 2 menit (dari yang sekarang mungkin 4-6 menit)
- ✅ Jurnalis: skor match isi teks (teks menolak → skor negatif)
- ✅ Oposisi Kritis: tidak pernah skor +1.0 kecuali teks benar-benar mendukung
- ✅ Akademisi: punya posisi tegas minimal di P2 (tidak boleh 2x netral berturut-turut)
- ✅ Semua agen: output max 3 kalimat, total < 50 kata
- ✅ Tidak ada output yang dimulai dengan "NamaAgen: ..."

---

**Created:** 26 Mei 2026  
**For:** Next Claude Session (Hotfix Fase 3)  
**Urgency:** 🔴 HIGH — PERF-01 blocking user experience, BUG-17/18 distorsi analisis
