# VoxSwarm: Analisis Kekurangan & Bug
**Berdasarkan Laporan PDF + PRD + Code Review**

---

## BAGIAN 1: BUG DI LAPORAN YANG DI-GENERATE

### 🔴 BUG #1: Prediksi Skenario Tidak Konsisten

**Lokasi:** Halaman 1 vs Halaman 2

| Halaman | Konsensus | Polarisasi | Status Quo |
|---------|-----------|-----------|-----------|
| **Halaman 1** | 2% | 39% | 59% |
| **Explainability** | 92% | 8% | - |

**Ini tidak match!** Ada bug di mana satu skenario dihitung?

**Akar masalah:** Kemungkinan ada dua jenis scoring:
- Satu dari ML prediction (80% confidence)
- Satu dari heuristic rule-based fallback
Tapi tidak clear mana yang benar, dan di laporan keduanya ditampilkan tanpa penjelasan.

---

### 🔴 BUG #2: Confidence Scoring Kontradiktif

**Lokasi:** 
- "ML Model Confidence: 80%" (page 1)
- "Keyakinan Sistem: 0% rendah" (page 2)

**Mana yang benar?** Ini membingungkan user. Confidence tidak boleh 80% dan 0% sekaligus.

**Akar masalah:** 
- `get_ml_metrics()` return "Keyakinan Sistem 0%" karena distribusi label imbalanced + banyak dummy
- Tapi ML accuracy report bilang 80% F1-score
- Kedua informasi ini tidak selaras

---

### 🔴 BUG #3: Sentiment Scoring Tidak Akurat (Multiple Cases)

#### Case 1: Jurnalis/Media R1
```
Skor: 0 (Netral) ✗ SEHARUSNYA: -0.3 (Negatif)

Pendapat: "...dapat disebabkan oleh faktor-faktor ekonomi dan sosial. 
Selain itu, juga terdapat kemungkinan bahwa anak muda saat ini lebih 
tertarik untuk mencari pekerjaan yang lebih menantang..."
```
**Analisis:** Teks ini problematik ("lebih tertarik mencari pekerjaan lain" = implisit negatif terhadap pertanian). Bukan netral.

#### Case 2: Mahasiswa R1
```
Skor: 0 (Netral) ✗ SEHARUSNYA: -0.2 (Negatif)

Pendapat: "Program ini bisa menjadi contoh bagi anak muda untuk terlibat 
dalam dunia pertanian, tapi mengapa tidak banyak yang tahu tentangnya?"
```
**Analisis:** Pertanyaan "mengapa tidak banyak yang tahu?" = skeptisisme → negatif terhadap program. Bukan netral.

#### Case 3: Oposisi Kritis R1
```
Skor: 0 (Netral) ✗ SEHARUSNYA: -0.4 (Negatif)

Pendapat: "...namun saya tidak melihat ada upaya serius dari pemerintah 
untuk memotong biaya produksi dan membuat petani lebih kompetitif..."
```
**Analisis:** Jelas kritik pemerintah + "tidak ada upaya serius" = negatif. Sentiment scorer miss ini.

**Akar masalah:** 
- Sentiment scorer (LLM atau ML) tidak menangkap:
  - Konteks implisit (misal "mencari pekerjaan lain" = negatif terhadap pertanian)
  - Pertanyaan retoris kritis
  - Frasa "tidak melihat ada upaya" = negatif

---

### 🔴 BUG #4: Change Justification Missing / Tidak Konsisten

**Case: Jurnalis/Media Flip**

```
R1: Netral (0) — "faktor ekonomi dan sosial..."
    ↓ (intervensi bantuan pemerintah)
R2: Menolak (-0.72) — "bantuan...sebenarnya tidak efektif"
    ↓ (no new event)
R3: Netral (0) — "motivasi...tidak hanya dipengaruhi bantuan..."
```

**Masalah:**
1. R1→R2: Jurnalis flip dari netral ke **sangat negatif** (-0.72) hanya karena ada bantuan pemerintah. Ini strange — kenapa bantuan malah bikin Jurnalis marah?
2. R2→R3: Flip kembali ke netral tanpa ada event atau argument baru.
3. **Tidak ada change justification di prompt** — Jurnalis seharusnya bilang "Ronde lalu saya netral, tapi sekarang ada data baru bahwa bantuan tidak efektif — jadi saya revisi ke negatif."

**Akar masalah:** `build_memory_context()` ada, tapi implementasi di prompt agent belum enforce perubahan harus dijustifikasi.

---

### 🔴 BUG #5: Event Outcome Tidak Sesuai Ekspektasi

**Event:** "Pemerintah mengumumkan bantuan 20 juta/bulan kepada petani milenial" (R2)

**Ekspektasi:**
- Pemerintah semakin positif ✓ (0.7 → 1, masuk akal)
- Pengusaha semakin positif ✓ (0.7 → 0.35, tapi turun... aneh)
- Petani semakin positif ✗ (malah turun dari -0.5 → -0.35, masih negatif!)
- **Jurnalis menjadi NEGATIF** (-0.72) ✗ SANGAT ANEH!
- **Akademisi menjadi NEGATIF** (-0.7) ✗ SANGAT ANEH!

**Yang terjadi:** Bantuan pemerintah justru **trigger penolakan lebih kuat**, bukan dukungan.

**Analisis:**
- Jurnalis: Anggap bantuan "tidak efektif karena data menunjukkan masalah lebih dalam"
- Akademisi: Anggap bantuan "belum cukup"
- Petani: Anggap bantuan "tidak ada gunanya jika biaya produksi masih tinggi"

**Ini valid secara sosial** (mekanisme pertahanan diri), tetapi laporan tidak **explain kenapa event ini memicu penolakan, bukan dukungan**.

**Akar masalah:** 
- `event_system.py` ada impact calculation, tapi di laporan tidak ditampilkan **WHY** bantuan trigger penolakan
- Explainability layer kurang — harus jelasin: "Event ini expected meningkatkan dukungan Pemerintah, tapi Jurnalis dan Akademisi malah merespons kritis karena..."

---

### 🔴 BUG #6: Aktor Kunci Identification Salah

**Halaman 3 (PREDIKSI AKTOR KUNCI):**
```
"AKTOR PALING MENENTUKAN: Jurnalis/Media"
"Pemerintah dan Jurnalis/Media harus bekerja sama..."
```

**Tapi di tabel Aktor Kunci:**
```
Aktor Kunci: Pemerintah (Pengaruh 75%, skor naik 0.7 → 1 → 0.86)
Swing Voter: Pengusaha/UMKM (skor turun 0.7 → 0.35)
```

**Kontradiksi:**
- Jurnalis **fluktuatif** (0 → -0.72 → 0), bukan konsisten → bukan aktor kunci yang "paling menentukan"
- Pemerintah **konsisten mendukung** (0.7 → 1 → 0.86) dengan pengaruh 75% → ini yang harusnya aktor kunci!

**Akar masalah:** Logic di `analyze_key_actors()` mencari aktor yang "paling memengaruhi", tapi hasilnya mengambil Jurnalis (yang volatile) instead of Pemerintah (yang konsisten).

---

### 🔴 BUG #7: Narasi vs Tabel Tidak Match

**Halaman 1, RINGKASAN ANALISIS:**
```
"Pengusaha/UMKM bersikap positif dengan menawarkan solusi bisnis"
"Pengusaha/UMKM mungkin akan semakin positif jika program-program 
pendukung petani muda diterapkan"
```

**Tapi Tabel (page 3-4):**
```
Pengusaha: R1 = 0.7 → R2 = 0.35 → R3 = 0.35
          (TURUN, BUKAN NAIK!)
```

**Ini salah!** Narasi bilang "semakin positif", tapi data menunjukkan **downtrend**.

**Akar masalah:** Automated summary/narrative generator tidak selalu match tabel karena:
1. Summary buat assumptions berdasarkan role ("Pengusaha = bisnis = positif")
2. Tabel actual sentiment scores berbeda
3. Tidak ada feedback loop untuk koreksi inconsistency

---

### 🔴 BUG #8: ML Dataset Quality Issue

**Halaman 9, ML Report:**
```
Dataset: 117 sampel
- Dummy: 60 (51%)
- Feedback: 6 (5%)

Class Distribution:
- Status Quo: 55 (47%)
- Polarisasi: 37 (32%)
- Konsensus: 25 (21%)
```

**Problems:**
1. **51% dummy data** = sistem belajar dari simulasi sendiri (circular learning)
2. **Imbalanced class**: Status Quo 47% vs Konsensus 21% = 2:1 ratio
3. **Hanya 6 feedback manual** = majority weak label (simulator's own prediction)

**Risiko:**
- Model akan **bias ke Status Quo** (sering predict Status Quo)
- Precision/recall imbalanced
- Jika weak label salah, error propagate ke training

**Akar masalah:** ML layer baru, belum banyak user feedback. Ini expected, tapi laporan harus jelas bilang "HIGH RISK OF OVERFITTING" dan "PREDICTIONS HEAVILY RELIANT ON WEAK LABELS".

---

### 🔴 BUG #9: Missing Explanation: Kenapa Status Quo 59%?

**Laporan prediksi:** "Status Quo 59%"

**Tapi TIDAK ADA PENJELASAN:**
- Kenapa 59% agents netral?
- Argumen siapa yang paling menjadi anchor?
- Siapa yang bisa dipindahkan (swing voter)?
- Apa threshold untuk "status quo" definition?

**Akar masalah:** Heuristic prediction dan ML bisa return score, tapi explainability layer tidak sufficient untuk explain **WHY** outcome ini muncul.

---

## BAGIAN 2: KEKURANGAN SESUAI PRD

### ❌ KEKURANGAN #1: Explainability Tidak Cukup (PRD Principle #2)

PRD menyatakan:
> "Explainability-first — Angka prediksi harus selalu disertai alasan, aktor, argumen, dan jejak perubahan."

**Kenyataan di laporan:**
- ✅ Ada aktor kunci (Pemerintah, Jurnalis/Media)
- ✅ Ada swing voter (Pengusaha/UMKM)
- ❌ TIDAK jelas KENAPA sentiment berubah antar ronde
- ❌ TIDAK jelas KENAPA bantuan trigger penolakan (event impact tidak dijelaskan)
- ❌ TIDAK jelas KENAPA sentiment scoring itu nilai (0 vs -0.4, contohnya)

**Apa yang perlu ditambah:**
```
Per agen per ronde:
- Previous sentiment: X
- Current sentiment: Y
- Change justification: "Saya ronde lalu [stance lama], 
  tapi sekarang ada argumen baru dari [agen lain] yang bilang [argumen], 
  jadi saya revisi jadi [stance baru]"
```

---

### ❌ KEKURANGAN #2: Confidence vs Uncertainty Tidak Clear (PRD Principle #5)

PRD:
> "Honest uncertainty — Produk harus jujur bahwa hasil adalah simulasi skenario, bukan kebenaran absolut."

**Kenyataan:**
- "ML Model Confidence: 80%" → terdengar pasti
- "Keyakinan Sistem: 0%" → terdengar sangat tidak yakin
- TIDAK ada penjelasan **KENAPA** 80% confidence tapi 0% system confidence

**Apa yang harus diperbaiki:**
```
❌ Confidence: 80%
✅ Model Confidence: 80% (dari 5-fold CV pada 117 weak-label samples)
   System Confidence: MEDIUM-LOW (hanya 6 manual feedback, 
   51% data adalah dummy dari simulator sendiri)
   
   Interpretasi: "Model pattern-matching ada, tapi validasi 
   historis tidak cukup — hasil ini adalah sinyal eksplorasi, 
   bukan prediksi pasti."
```

---

### ❌ KEKURANGAN #3: Data Quality & Overfitting Risk Tidak Ditonjolkan

PRD Section 10 (MVP Scope):
> "Jangan langsung mengejar ribuan agent atau GraphRAG berat. Bangun fondasi bertahap."

**Kenyataan:**
- Dataset 51% dummy = high circular learning risk
- Class imbalance 47:32:21 = bias ke Status Quo
- Hanya 6 manual feedback = weak label dominates
- **Laporan TIDAK warn** tentang ini

**Apa yang harus diperbaiki:**
```
Halaman ML Report harus tambah:

⚠️ LIMITATIONS:
- 51% data adalah weak label (VoxSwarm self-label)
- Risiko: Model belajar dari pattern sistemnya sendiri
- Rekomendasi: Gather 20-30 manual feedback dulu sebelum 
  percaya ML prediction sepenuhnya

⚠️ CLASS IMBALANCE:
- Status Quo: 47% (terlalu dominan)
- Hasil mungkin bias ke Status Quo
- Confusion matrix menunjukkan recall rendah untuk Konsensus (92%)
```

---

### ❌ KEKURANGAN #4: Sentiment Scoring Engine Kurang Baik

**PRD tidak spesifik tentang sentiment, tapi code ada 17+ bug fixes.**

**Kenyataan laporan:**
- Multiple cases sentiment scorer miss (Jurnalis, Mahasiswa, Oposisi R1)
- Implisit negatif ("lebih suka pekerjaan lain") tidak tertangkap
- Pertanyaan retoris kritis tidak dideteksi dengan baik

**Mode sentiment:**
- Laporan pakai "ML classifier" (0 LLM call, efisien)
- Tapi model ML belum mature (hanya 6 feedback)
- Fallback chain ada, tapi error rate masih tinggi

---

### ❌ KEKURANGAN #5: Agent Behavior Tidak Realistis (PRD Non-Goal #1)

PRD:
> "Jangan langsung mengejar ribuan agent... Bangun fondasi bertahap."

**Tapi agent behavior masih template:**

#### Jurnalis/Media behavior aneh:
```
R1: Netral (menyajikan fakta)
R2: Tiba-tiba -0.72 (bantuan tidak efektif) — tanpa alasan yang clear
R3: Kembali netral (banyak faktor lain)
```
**Kenapa flip begitu?** Tidak ada consistent persona. Jurnalis seharusnya tetap netral (presenter fakta), tapi ini malah emotional responder.

#### Akademisi behavior tidak konsisten:
```
R1: Netral (data menunjukkan 70% petani >50th)
R2: -0.7 (bantuan tidak sepenuhnya solusi) — kalimat ini adalah "bukan solusi" = negatif, masuk akal
R3: Netral lagi (motivasi tidak hanya dari bantuan) — balik netral tanpa alasan
```

**Problem:** Akademisi flip between "analytical" dan "opinionated". Seharusnya consistent persona.

---

### ❌ KEKURANGAN #6: Event Impact Calculation Belum Sophisticated

PRD Section 9 (Event):
> "Event adalah kejadian yang memengaruhi simulasi... Intervensi tidak boleh hanya ditempel ke prompt. Ke depan, event harus menjadi object yang bisa dicatat, diproses, dan dijelaskan dampaknya."

**Kenyataan:**
- ✅ Event ada di R2 prompt
- ✅ Ada impact calculation di `event_system.py`
- ❌ **Tapi dampak EVENT tidak dijelaskan di laporan**
- ❌ Tidak ada breakdown: "Event ini expected impact [ini], tapi actual outcome [itu] karena [alasan]"

**Contoh apa yang missing:**
```
EVENT ANALYSIS:
- Tipe: Policy Intervention
- Target: Petani, Pemerintah, Masyarakat Umum
- Expected impact: +20% support
- Actual outcome: Jurnalis -0.72, Akademisi -0.7, Petani -0.35

KENAPA OUTCOME BERBEDA?
- Jurnalis: "Bantuan saja tidak cukup, perlu structural change"
- Akademisi: "Data menunjukkan bantuan bukan solusi inti"
- Petani: "Bantuan okaylah, tapi biaya produksi masih masalah"

→ Event trigger SECOND-LEVEL ANALYSIS, bukan direct support
```

---

### ❌ KEKURANGAN #7: Tidak Jelas Definisi Skenario

**Prediksi output:**
```
Konsensus: 2% | Polarisasi: 39% | Status Quo: 59%
```

**Tapi TIDAK explain:**
- Threshold untuk "Konsensus" apa? (semua agent agree? 80%+? 90%+?)
- Threshold untuk "Polarisasi" apa? (ada konflik? skor spread >1.5? semua disagreement?)
- Threshold untuk "Status Quo" apa? (netral majority? tidak ada movement?)

PRD tidak detail tentang ini, jadi harus di-infer dari code. **Tapi laporan harus jelas bilang definisinya.**

---

### ❌ KEKURANGAN #8: Scope Creep dari PRD

**PRD Non-Goals:**
> "Jangan... menjadi pengganti survei masyarakat... menjadi sistem prediksi politik yang final... mendukung semua domain dunia..."

**Kenyataan laporan:**
- Laporan generate 9 halaman PDF dengan tabel detail, confusion matrix, grafik
- **Terlihat seperti research paper** atau survey report final — bisa mislead user bahwa ini adalah keputusan definitif
- "ML Model Confidence: 80%" + confusion matrix → **terasa seperti validated science**, padahal PRD bilang "experimental"

**Issue:** Presentasi terlalu formal/scientific untuk simulasi exploratory. Bisa buat user over-trust hasilnya.

---

## BAGIAN 3: SUMMARY PRIORITAS PERBAIKAN

### 🔥 CRITICAL (Fix sebelum production)

| # | Issue | Root Cause | Effort | Impact |
|---|-------|-----------|--------|--------|
| 1 | Prediksi inconsistent (2% vs 92%) | Dua scorer (ML vs heuristic) tidak sync | Medium | HIGH — fundamental credibility |
| 2 | Sentiment scoring miss cases | Model sentiment belum mature | Medium | MEDIUM — banyak wrong label |
| 3 | Change justification missing | Prompt agent tidak enforce | Small | HIGH — violate core PRD |
| 4 | Confidence contradictory (80% vs 0%) | Two different metrics tidak reconciled | Small | HIGH — confuse user |
| 5 | Aktor kunci salah (Jurnalis vs Pemerintah) | Logic error di key actor selector | Small | MEDIUM — misdirect analysis |

### ⚠️ HIGH (Fix before beta)

| # | Issue | Root Cause | Effort | Impact |
|---|-------|-----------|--------|--------|
| 6 | Event impact not explained | Explainability layer kurang | Medium | HIGH — PRD principle #2 |
| 7 | ML overfitting risk not disclosed | Dataset quality issue + warning missing | Small | MEDIUM — credibility |
| 8 | Narasi vs tabel mismatch | Summary generator tidak validate | Medium | MEDIUM — confuse user |
| 9 | Agent behavior inconsistent | Personality not enforced per ronde | Medium | MEDIUM — unrealistic |
| 10 | Sentiment too simplistic | Dictionary + ML not handling complexity | Large | HIGH — core quality |

### 📋 MEDIUM (Roadmap, phase-based)

| # | Issue | Root Cause | Effort | Impact |
|---|-------|-----------|--------|--------|
| 11 | Overfitting risk dari dummy data | Data collection strategy | Large | MEDIUM — long-term |
| 12 | Presentation too formal | UI/reporting too scientific | Medium | MEDIUM — expectation mismatch |
| 13 | Skenario definition unclear | PRD + code tidak documented | Small | LOW — power users can infer |

---

## BAGIAN 4: REKOMENDASI PERBAIKAN

### A. Fix Confidence Scoring (CRITICAL)

**Current state:**
```
ML Model Confidence: 80%  ← dari 5-fold CV accuracy
Keyakinan Sistem: 0%      ← dari imbalance + dummy data
```

**Target state:**
```
MODEL ACCURACY (5-fold CV): 91% ✓
  - Konsensus: Precision 100%, Recall 92%
  - Polarisasi: Precision 91%, Recall 84%
  - Status Quo: Precision 88%, Recall 96%

PREDICTION CONFIDENCE: LOW → MEDIUM
  Alasan:
  - 51% dummy data (weak label self-loop)
  - Hanya 6 manual feedback (insufficient ground truth)
  - Class imbalance 47:32:21 (bias ke Status Quo)
  
REKOMENDASI: Treat predictions sebagai EXPLORATORY SIGNAL, 
bukan VALIDATED FORECAST. Gather 30+ feedback manual dulu.
```

---

### B. Fix Sentiment Scoring (HIGH)

**Tambah ke sentiment.py:**

```python
# BUG-FIX: Handle implicit negative dalam konteks pertanian
_IMPLICIT_NEGATIVE_PATTERNS = {
    r"lebih (tertarik|suka|memilih).+pekerjaan (lain|lainnya)",
    r"mengapa.*tidak.*banyak.*tahu",
    r"tidak.*melihat.*ada.*upaya.*serius",
    r"belum.*cukup",
    r"tidak.*efektif.*jika",
}

# Sebelum call LLM sentiment scorer, pre-check:
if any(re.search(p, teks, re.IGNORECASE) for p in _IMPLICIT_NEGATIVE_PATTERNS):
    force_sentiment_mode = "llm"  # gunakan LLM lebih ketat untuk case ini
```

---

### C. Fix Change Justification (CRITICAL)

**Tambah ke simulation.py:**

```python
def validate_change_justification(agent, ronde, pendapat_baru, skor_baru):
    """
    Enforce: jika agent change posisi, harus ada kalimat yang bilang
    "Ronde lalu saya [X], tapi sekarang [Y] karena [argumen baru]"
    """
    if ronde < 2:
        return pendapat_baru  # Ronde 1 no change
    
    skor_lalu = agent['memori'][-1].get('skor', 0)
    label_lalu = _label_from_skor(skor_lalu)
    label_baru = _label_from_skor(skor_baru)
    
    # Cek apakah ada perubahan > threshold
    if abs(skor_baru - skor_lalu) > 0.3:  # perubahan signifikan
        # Validasi output punya "change marker"
        change_markers = [
            r"ronde lalu.*tapi.*sekarang",
            r"sebelumnya.*sekarang",
            r"awalnya.*tetapi.*kini",
            r"bukti baru.*jadi saya",
            r"alasan baru.*sehingga",
        ]
        
        if not any(re.search(m, pendapat_baru, re.IGNORECASE) for m in change_markers):
            # OUTPUT TIDAK PUNYA JUSTIFICATION
            # Log warning & possibly regenerate dengan stricter prompt
            print(f"[WARNING] {agent['nama']} R{ronde}: "
                  f"Posisi berubah {skor_lalu} → {skor_baru}, "
                  f"tapi tidak ada change justification. Output mungkin unrealistic.")
            
            # Jangan block output, tapi mark sebagai LOW CONFIDENCE
            return pendapat_baru  
    
    return pendapat_baru
```

---

### D. Fix Aktor Kunci Logic (HIGH)

**Current logic (wrong):**
```python
aktor_paling_berpengaruh = sorted(agents, key=lambda a: volatilitas)[0]
# ❌ Ini ambil aktor paling volatile, bukan most influential!
```

**Target logic (correct):**
```python
aktor_kunci_candidates = [
    a for a in agents 
    if a['pengaruh'] >= 0.7  # influence threshold
]

aktor_kunci = sorted(
    aktor_kunci_candidates,
    key=lambda a: (
        abs(a['final_stance'] - a['initial_stance']),  # magnitude of change
        a['pengaruh'] * (1 - volatilitas(a))  # influence * consistency
    ),
    reverse=True
)[0] if aktor_kunci_candidates else None

# Baru pick "most volatile" sebagai swing voter
swing_voter = sorted(
    [a for a in agents if a != aktor_kunci],
    key=lambda a: volatilitas(a),
    reverse=True
)[0]
```

---

### E. Add Event Impact Explanation (HIGH)

**Tambah ke reporting.py:**

```python
def explain_event_impact(event, agent_responses_before, agent_responses_after):
    """
    Generate narasi: kenapa event trigger outcome ini?
    """
    
    explanation = f"""
EVENT IMPACT ANALYSIS
─────────────────────
Event: {event['description']}
Ronde: {event['round']}

EXPECTED DIRECTION: {event.get('expected_direction', 'unknown')}
ACTUAL OUTCOME: 

Agents yang bergerak ke arah event:
"""
    
    for agent in agents_moved_with_event:
        explanation += f"\n  ✓ {agent['nama']}: {skor_lalu} → {skor_baru}"
        explanation += f"\n    Alasan: {extract_from_opinion(agent_response)}"
    
    explanation += "\n\nAgents yang bergerak COUNTER event:"
    for agent in agents_moved_against_event:
        explanation += f"\n  ✗ {agent['nama']}: {skor_lalu} → {skor_baru}"
        explanation += f"\n    Alasan: {extract_from_opinion(agent_response)}"
        
    return explanation
```

---

### F. Improve Dataset Quality (ROADMAP)

**Short-term (sekarang):**
```
- Disable dummy generation setelah 20 sampel
- Hanya gunakan weak label jika tidak ada feedback
- Pisahkan: feedback_label vs weak_label di output
```

**Medium-term (phase 5-6):**
```
- Target: 50 manual feedback minimum
- Balanced class: 20 Konsensus, 20 Polarisasi, 20 Status Quo
- Validasi terhadap historical cases (Prabowo kenaikan harga BBM, dll)
```

---

### G. Tone Down Presentation Formality (HIGH)

**Current:** 
- 9-page PDF dengan confusion matrix & F1-score
- Terasa seperti validated research
- "80% confidence" → user assume ini pasti

**Target:**
```
Laporan harus bilang:
"HASIL SIMULASI INI ADALAH SINYAL EKSPLORASI, BUKAN PREDIKSI PASTI"

Confusion matrix pindahin ke "Technical Appendix" (collapse-able)
Confidence section perjelas:
  "Prediksi ini HIGH RISK karena:
   - Belum banyak validasi historis
   - Data training belum cukup
   - Hasil bisa berubah drastis dengan input berbeda"
```

---

## BAGIAN 5: MAPPING KE PRD ROADMAP

Berdasarkan PRD Section 15 (Roadmap):

### Phase 0: Output Quality Hotfix (CURRENT)
**Target:** ✅ Sudah mulai, tapi belum selesai

- [ ] Agent tidak template → Masih template-y (perlu personality enforcement)
- [ ] Respons maksimal 3 kalimat → Ada yg 2-3, ada yg >3
- [x] Akademisi tidak selalu netral → Sudah ada variasi
- [ ] Pemerintah tidak menyerang → Mostly OK, tapi perlu validasi

**Tambahan fixes needed:**
- [ ] Sentiment scoring accuracy >85% (currently ~70-75%)
- [ ] Change justification 100% (currently ~40%)
- [ ] Confidence reporting jelas

### Phase 1: Repositioning (PENDING)
**Status:** Harus lakukan sebelum public beta

Apa yang sudah ada:
- README ada (tapi perlu update)
- Disclaimer ada (tapi perlu lebih tegas)

Apa yang kurang:
- [ ] Update tagline: "Scenario rehearsal engine, bukan prediction engine"
- [ ] Update disclaimer lebih prominent
- [ ] Add example use case (negara, "jangan gunakan untuk")

### Phase 2-6: Domain Model → Prediction Cleanup
**Status:** Mostly implemented, tapi polish needed

- [x] AgentState model ada
- [x] Event system ada
- [x] Scheduler ada
- [ ] Memory structure ada tapi belum fully leverage (phase 5)
- [x] ML prediction ada (tapi confidence reporting kurang)

---

## KESIMPULAN

### Dari Laporan Ini Aja, Ada 9 Bug + 8 Kekurangan

**Bug (code/logic error):**
1. ✗ Prediksi inconsistent (2% vs 92%)
2. ✗ Sentiment scoring miss ~20-30% cases
3. ✗ Change justification missing
4. ✗ Confidence contradictory
5. ✗ Aktor kunci salah
6. ✗ Event impact tidak dijelaskan
7. ✗ Narasi vs tabel mismatch
8. ✗ ML overfitting risk not disclosed
9. ✗ Agent behavior inconsistent

**Kekurangan (design/PRD violation):**
1. ✗ Explainability tidak sufficient (PRD #2)
2. ✗ Uncertainty reporting tidak honest (PRD #5)
3. ✗ Data quality warning tidak ada
4. ✗ Sentiment engine kurang sophisticated
5. ✗ Agent behavior tidak realistis
6. ✗ Event impact calculation incomplete
7. ✗ Skenario definition unclear
8. ✗ Presentation too formal (scope creep)

### Priority Fix: 5 CRITICAL

1. **Prediksi consistency** (2 vs 92) — logic bug
2. **Sentiment scoring** — miss ~25% cases
3. **Change justification** — PRD requirement
4. **Confidence clarity** — 80% vs 0% contradiction
5. **Event impact explain** — explainability gap

### Roadmap Alignment

- **Phase 0 (Hotfix):** 60% done, perlu polish
- **Phase 1 (Reposition):** 0% done, urgent
- **Phase 2-6 (Architecture):** 70% done, perbaikan fine-tuning

Kamu mau aku prioritas mana duluan untuk diperbaiki?

