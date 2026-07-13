---
tags: [project/voxswarm, type/agent-system]
---

# Agent System — Persona, Prompt Construction, Bug

Agent adalah "aktor" yang berdebat dalam simulasi VoxSwarm. Masing-masing punya kepribadian, sudut pandang, dan cara bicara sendiri.

## Daftar Agent Default

Ada **9 agent utama** di `backend/agents.py` (dalam `AGENT_REGISTRY`):

| Agent | Role | Pengaruh | Stance Awal |
|-------|------|----------|-------------|
| Mahasiswa | Kritis, peduli keadilan sosial, bahasa santai | 0.7 | -0.3 (cenderung kritis) |
| Pengusaha/UMKM | Pragmatis, fokus untung-rugi & lapangan kerja | 0.8 | 0.0 (netral) |
| Pekerja Kantoran | Pragmatis, singkat, langsung ke dampak nyata | 0.6 | 0.0 (netral) |
| Pemerintah | Formal diplomatis, singkat padat | 0.75 | +0.6 (cenderung dukung) |
| Akademisi | Data-driven, HARUS punya posisi tegas gak boleh netral | 0.75 | 0.0 (netral) |
| Jurnalis/Media | Investigatif, curiga, berani menyebut nama | 0.85 | -0.2 (sedikit skeptis) |
| Masyarakat Umum | Sederhana, langsung, ikut kondisi ekonomi | 0.65 | 0.0 (netral) |
| Oposisi Kritis (counter) | Tajam, serang langsung, curiga sama pemerintah | 0.8 | -0.5 (sangat kritis) |
| Skeptis Ekonomi (counter) | Skeptis sama optimisme berlebihan, tanya data | 0.75 | -0.4 |
| Advokat Minoritas (counter) | Bela kelompok rentan yang mungkin terabaikan | 0.7 | -0.4 |
| Pengacara Publik (counter) | Kritis sama celah hukum & regulasi | 0.72 | -0.4 |
| Etikawan Digital (counter) | Tanya dampak sosial dari inovasi digital | 0.71 | -0.35 |

### Agent Dinamis (dari `agent_factory.py`)

Selain agent di atas, sistem juga bisa inject agent tambahan kalau topik cocok dengan keyword tertentu. Contoh:
- **Perwira_TNI** — kalau topik soal militer
- **Dokter_Nakes** — kalau topik soal kesehatan
- **Petani** — kalau topik soal pertanian
- **Nelayan** — kalau topik soal kelautan
- **Pemuda_Digital** — kalau topik soal startup/digital
- **Guru_Dasar** — kalau topik soal pendidikan

### Agent Custom dari Frontend

User juga bisa kirim agent custom sendiri lewat API (maks 5). Setiap agent custom butuh: nama, role (deskripsi karakternya), pengaruh (0.1-1.0), dan kepribadian (openness, agreeableness, neuroticism).

## Prompt Construction — Gimana Agent Diajak Bicara

Tiap ronde, agent dipanggil satu per satu ke LLM (Groq). Ini cara prompt dibangun:

### 1. System Prompt (siapa agent-nya)

Dari field `role` di `AGENT_REGISTRY`. Misalnya Mahasiswa:
> "Kamu mahasiswa aktivis yang kritis terhadap kebijakan pemerintah..."

### 2. User Prompt (konteks + perintah)

Isinya campuran dari:
- **Topik diskusi** — dari input user
- **Briefing real** — ringkasan berita terkini dari `scraper.py`
- **Memori agent** — pendapat agent di ronde-ronde sebelumnya (dari `memory.py`)
- **Argumen agent lain** — di ronde 2 ke atas, agent bisa lihat apa kata agent lain
- **Event aktif** — kalau ada intervensi/skenario kejutan (dari `event_system.py`)
- **Crowd sentiment** — kalau mode crowd aktif, agent bisa lihat opini publik
- **Gaya bicara** — system bisa kasih instruksi gaya (santai/formal/panas)

### 3. Post-Processing

Output LLM diproses lagi:
- **Delta cap** — skor agent gak boleh loncat > 0.7 dalam 1 ronde (biar gak "berubah pikiran" secara dramatis)
- **Change justification** — kalau agent berubah posisi > 0.35, dia WAJIB kasih alasan. Kalau gak, diregenerate 1x.
- **Batasi kalimat** — maks 3 kalimat per agent. Biar diskusi gak kepanjangan.
- **Filter emoji** — emoji dibuang dari output.

## Bug & Masalah yang Pernah Ditemukan

VoxSwarm udah lewat beberapa iterasi perbaikan. Ini yang paling penting:

### FIX-A: Delta Cap Enforcement
- **Masalah:** Skor agent bisa loncat dari +0.8 ke -0.9 dalam satu ronde — gak realistis.
- **Solusi:** Clamp di Python. Maks perubahan 0.7 per ronde.

### FIX-B: Change Justification Hard Enforcement
- **Masalah:** Agent ganti posisi tanpa alasan. Kelihatan gak konsisten.
- **Solusi:** Kalau perubahan > 0.35 tapi gak ada penjelasan, minta LLM generate ulang dengan instruksi WAJIB kasih alasan.

### FIX-C: Single Source of Truth untuk Prediksi
- **Masalah:** Heuristic dan ML kasih angka prediksi beda, user bingung.
- **Solusi:** Heuristic = satu-satunya prediksi utama. ML = experimental, disembunyikan.

### FIX-D: Stance Oposisi
- **Masalah:** Oposisi Kritis tiba-tiba jadi mendukung tanpa alasan.
- **Solusi:** Terapin aturan yang sama: wajib ada justifikasi.

### FIX-E: Confidence Reporting
- **Masalah:** Laporan tampilin dua confidence berbeda (heuristic 0% vs ML 80%).
- **Solusi:** Satu angka confidence yang konsisten dari heuristic.

### BUG #5: Agent Fallback
- **Masalah:** Kalau LLM gagal balas JSON, seluruh simulasi bisa crash.
- **Solusi:** Fallback pure Python — hitung aktor kunci dari influence × consistency.

### BUG #14: Anchor Stance
- **Masalah:** Semua agent mulai dari netral (0.0) — jadi gak mencerminkan karakter.
- **Solusi:** Tiap agent punya `initial_stance` beda. Mahasiswa mulai kritis (-0.3), Pemerintah mulai dukung (+0.6).

## LLM Call Map per Simulasi

**Free tier:** 0 LLM calls (pake inline sentiment + fallback analysis)
**Normal tier:** sekitar 16-25 calls per simulasi (tergantung jumlah agent dan ronde)

Model utama: `llama-3.3-70b-versatile`. Cadangan: `llama-3.1-8b-instant`, `gemma2-9b-it`, `mixtral-8x7b-32768`.

## Terkait

- [[Arsitektur]]
- [[Sentiment ML Pipeline]]
- [[Decision Intelligence Fields]]
- [[Vox Swarm]]
