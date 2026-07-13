---
tags: [project/voxswarm, type/decision-intelligence]
---

# Decision Intelligence Fields — Risiko, Rekomendasi, Kelompok Kritis

Setelah simulasi selesai, VoxSwarm ngeluarin beberapa field yang membantu pengambilan keputusan. Ini yang paling penting:

## 1. `risiko_utama` — Apa Risiko Terbesar?

**Darimana asalnya:** Parse dari teks analisis LLM pake regex. LLM disuruh nulis satu paragraf "RISIKO UTAMA" di akhir analisisnya.

**Isinya:** Identifikasi 1-2 risiko terbesar kalau kebijakan/topik ini dilanjutin, berdasarkan argumen agen yang menolak. Contoh:
> "Risiko utama adalah penolakan dari sektor UMKM yang menganggap kebijakan ini akan menambah beban operasional dan berujung pada PHK massal..."

**Fallback (free tier):** Pake aturan sederhana — kalau ada agent dengan sentimen negatif kuat, risikonya adalah "resistensi publik" atau "stabilitas sosial" tergantung agent yang paling vokal menolak.

## 2. `rekomendasi_strategis` — Langkah Konkret

**Darimana asalnya:** Dari LLM (`call_llm_json`) di fungsi `_analisis_dan_aktor()` di `simulation.py`. LLM dikasih data: topik, ringkasan agent, sentimen agregat.

**Format:** Array of strings, idealnya 3 rekomendasi:

1. **Rekomendasi 1 — Siapa yang perlu didekati duluan** > Kelompok mana yang paling berpengaruh dan cara konkretnya.
2. **Rekomendasi 2 — Narasi/framing paling efektif** > Argumen apa yang paling mungkin diterima kelompok pro — itu yang harus diperkuat.
3. **Rekomendasi 3 — Cara netralisir penolak** > Kelompok penolak terkuat dan gimana pendekatannya.

**Fallback (free tier atau LLM gagal):** Pake rules-based:
- Dekati aktor dengan influence × consistency tertinggi
- Gunakan argumen berbasis data
- Pantau swing voter paling volatile

## 3. `kelompok_kritis` — Siapa yang Peruh Dinetralisir?

**Darimana asalnya:** Juga dari LLM, format JSON array:
```json
[{
  "nama": "Nama Agen",
  "alasan": "Sentimen akhir negatif -0.65 — termasuk penolak paling konsisten",
  "cara_pendekatan": "Libatkan dalam forum diskusi terbatas untuk menggali akar kekhawatiran..."
}]
```

**Ada 3 field penting per kelompok kritis:**
- **nama** — siapa kelompok/agennya
- **alasan** — kenapa dia dianggap kritis
- **cara_pendekatan** — gimana cara menghadapinya (harus konkret dan spesifik, bukan saran generik)

**Fallback (free tier):** Ambil 2 agen dengan sentimen akhir paling negatif. Cara pendekatan generik berdasarkan peran mereka.

## 4. `aktor_kunci` — Siapa yang Paling Berpengaruh?

Diitung dari **composite score**: `pengaruh × (0.7 + 0.3 × konsistensi)`

Artinya: agent dengan pengaruh tinggi DAN pendirian konsisten = aktor kunci. Bukan yang paling keras atau paling vokal.

Maksimal 3 aktor kunci. Masing-masing punya:
- `pengaruh_skor` — bobot pengaruh (0-1)
- `sikap_akhir` — skor sentimen di ronde terakhir
- `sikap_label` — Mendukung / Netral / Menolak
- `dampak_jika_berubah` — apa yang terjadi kalau mereka ganti pikiran

## 5. `swing_voter` — Siapa yang Paling Mudah Berubah?

Ini **berbeda dari aktor kunci** (BUG #6 fix). Swing voter adalah agent dengan **volatilitas tertinggi** — paling sering berubah posisi antar ronde.

Mereka penting karena:
- Bisa jadi "pemecah suara" yang nentuin arah diskusi
- Kalau bisa diyakinkan, bisa mengubah keseimbangan opini

## 6. `aktor_penggerak` — Satu Agen Paling Penting

Ini agen nomor 1 dari peringkat composite score. Dia yang paling menentukan arah simulasi. LLM atau rules bakal kasih saran spesifik buat approach agen ini.

## Hubungan Antar Field

```
Simulasi selesai
     ↓
Aktor Kunci (siapa yang penting)
Swing Voter (siapa yang labil)
     ↓
Rekomendasi Strategis (apa yang harus dilakukan)
Risiko Utama (apa yang harus diwaspadai)
     ↓
Kelompok Kritis (siapa yang jadi penghalang terbesar)
```

## Catatan Penting

- **Semua field ini bersifat eksploratif** — bukan keputusan final. VoxSwarm bilang sendiri di disclaimer.
- **Free tier** — semua pake rules/fallback (no LLM cost). Kurang detail tapi tetap berguna.
- **Normal tier** — pake LLM. Lebih tajam, rekomendasi lebih kontekstual.
- **ML prediction** — ada tapi masih experimental. Jangan diandalkan untuk keputusan penting.

## Terkait

- [[Agent System]]
- [[Sentiment ML Pipeline]]
- [[Arsitektur]]
- [[Vox Swarm]]
