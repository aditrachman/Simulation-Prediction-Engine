---
description: Refactor halaman hasil simulasi VoxSwarm agar lebih insight-oriented untuk user awam.
---

Refactor halaman hasil simulasi VoxSwarm agar lebih insight-oriented untuk user awam.

KONTEKS:
- Stack: Next.js 15, Tailwind CSS
- Halaman: `/demo` atau halaman hasil simulasi
- Tujuan: user awam langsung paham tanpa harus baca semua data

PERUBAHAN YANG DIBUTUHKAN:

1. HERO INSIGHT (taruh paling atas, sebelum Risalah)
   - Tambah komponen `<InsightHero />`
   - Isi: 1 kalimat kesimpulan otomatis berdasarkan skenario probabilitas tertinggi
   - Contoh output: "Topik ini berpotensi memecah belah masyarakat — polarisasi 65% mendominasi."
   - Style: card dengan background subtle, font besar, mudah dibaca

2. LABEL HUMAN-FRIENDLY di Meteran Sikap
   - Ganti truncation "Pengusaha/U..." → tampilkan full name, wrap jika perlu
   - Tambah badge teks di samping angka:
     - 0–30 → "Menolak Keras" (merah)
     - 31–49 → "Cenderung Menolak" (oranye)
     - 50 → "Netral" (abu)
     - 51–70 → "Cenderung Mendukung" (hijau muda)
     - 71–100 → "Mendukung Kuat" (hijau)

3. PROBABILITAS SKENARIO
   - Tambah tooltip atau teks deskripsi di bawah setiap bar:
     - Konsensus: "Semua kelompok mencapai kesepakatan"
     - Polarisasi: "Masyarakat terbagi tajam, konflik berpotensi meningkat"
     - Status Quo: "Tidak ada perubahan signifikan dalam opini publik"
   - Highlight skenario tertinggi dengan border atau badge "Paling Mungkin"

4. RINGKASAN AKHIR
   - Tambah label "⚠️ Perlu Perhatian" sebelum section Kelompok yang Perlu Dinetralisir
   - Ganti "Skor komposit 0.85" → "Pengaruh Sangat Tinggi (0.85)"
   - Ganti "Sentimen akhir negatif (-0.80)" → "Kelompok ini menolak keras program tersebut"

5. FIX BUG
   - Summary paragraph di atas Risalah terpotong (kalimat menggantung "Keduanya memiliki")
   - Pastikan full text ditampilkan atau ada tombol "Lihat selengkapnya"

JANGAN ubah:
- Struktur data / API response
- Layout keseluruhan halaman
- Komponen Risalah Simulasi (dialog antar agen)
- Logic simulasi apapun

Fokus hanya pada presentasi dan keterbacaan output.
