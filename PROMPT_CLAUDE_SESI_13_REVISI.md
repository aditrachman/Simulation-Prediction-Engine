# Prompt untuk Claude — Sesi Berikutnya VoxSwarm (Sesi 13)

## Konteks Sistem

Kamu melanjutkan pengembangan **VoxSwarm** — Simulation-Prediction-Engine berbasis multi-agen LLM (Groq) + ML (scikit-learn).

Kerjakan sesi ini sebagai **hotfix output quality**, bukan refactor arsitektur besar.

Fokus utama:
- mengurangi template berulang antar agen
- membuat jawaban agen lebih pendek dan konsisten
- membuat Akademisi lebih berposisi
- membuat Pemerintah tetap align sebagai wakil pemerintah
- tidak menambah LLM call
- tidak mengubah schema API

---

## State Setelah Sesi 12

- BUG #19 selesai — format kutipan verbatim sudah diperbaiki di `memory.py`
- BUG #20 selesai — enforcement limit kalimat + role Pemerintah sudah diperketat
- ISSUE #19 selesai — kepribadian Jurnalis sudah disesuaikan
- ISSUE #20 selesai — role Oposisi Kritis sudah lebih eksplisit dan agresif

State kode saat ini:

### `simulation.py` — system prompt `_proses_satu_agen()`

```python
system_p = (
    f"Kamu {agen['nama']}. {role_singkat} "
    f"GAYA BICARA WAJIB: {gaya_str}. ..."
    "LARANGAN KERAS: "
    "JANGAN menyebut role atau jabatanmu ..."
    "JANGAN bilang kamu tidak punya opini ..."
    "JANGAN ulangi argumen agen lain ..."
    "JANGAN buka kalimat dengan 'Saya pikir' atau 'Saya rasa' ..."
    "JANGAN kutip atau ulangi kata-kata peserta lain secara verbatim ..."
    "Tulis TEPAT 2-3 kalimat pendek. Setiap kalimat HARUS diakhiri tanda titik. "
    "PELANGGARAN: Menulis lebih dari 3 kalimat adalah kesalahan fatal — potong sebelum mengirim."
)
```

### `memory.py` — `build_influence_context()`

```python
baris.append(f'- {p["nama"]}: {kutipan}')
konteks  = "Posisi peserta lain sejauh ini:\n" + "\n".join(baris) + "\n"
konteks += "Respons LANGSUNG ke salah satu — gunakan kata-katamu sendiri, jangan kutip ulang."
```

### `agents.py` — state terkini

```python
# Pemerintah
"role": "Kamu pejabat pemerintah yang berbicara formal dan diplomatis — tapi SINGKAT dan PADAT. Gunakan maksimal 2 kalimat per respons. Tidak perlu menyebutkan semua faktor — pilih satu poin terkuat dan pertahankan."

# Jurnalis
"kepribadian": {"openness": 0.85, "agreeableness": 0.2, "neuroticism": 0.65}
"role": "Kamu SELALU punya kesimpulan — bukan 'ada dua sisi', tapi 'ini yang lebih masuk akal berdasarkan data'..."

# Oposisi Kritis
"role": "Kamu politisi oposisi yang tajam dan tidak segan menyerang langsung. Setiap klaim pemerintah adalah kebohongan sampai terbukti sebaliknya..."
```

---

## Masalah yang Harus Diselesaikan

## BUG #21 — Beberapa Agen Memakai Kalimat Pembuka yang Sama

### File

- `backend/simulation.py`
- `backend/memory.py`

### Gejala

Beberapa agen membuka respons dengan pola sama seperti:

```txt
"Poin X soal Y kurang tepat karena..."
"X, angkamu dari mana?"
```

Ini membuat percakapan terasa seperti template yang diulang.

### Penyebab

Instruksi:

```txt
WAJIB: Sebut nama peserta yang kamu respons di kalimat pertama
```

ditambah konteks pengaruh yang selalu mengarah ke agen berpengaruh tertinggi, membuat banyak agen menyerang target yang sama dengan kalimat mirip.

### Yang harus dilakukan

#### 1. Tambahkan parameter `idx_agen` ke `build_influence_context()`

Ubah signature:

```python
def build_influence_context(agen: dict, semua_pendapat_ronde: list[dict]) -> str:
```

menjadi:

```python
def build_influence_context(
    agen: dict,
    semua_pendapat_ronde: list[dict],
    idx_agen: int = 0,
) -> str:
```

#### 2. Rotasi kandidat respons

Setelah kandidat di-sort berdasarkan pengaruh, ambil lebih banyak dulu, lalu rotate berdasarkan `idx_agen`.

Contoh logic:

```python
kandidat_sorted = sorted(
    [p for p in semua_pendapat_ronde if p["nama"] != agen["nama"]],
    key=lambda p: p.get("pengaruh", 0.5),
    reverse=True,
)[:5]

if kandidat_sorted:
    start = idx_agen % len(kandidat_sorted)
    kandidat = (kandidat_sorted[start:] + kandidat_sorted[:start])[:3]
else:
    kandidat = []
```

Tujuannya bukan sekadar rotasi, tapi supaya tidak semua agen diarahkan ke target yang sama.

#### 3. Ubah instruksi respons di `simulation.py`

Ganti instruksi lama:

```python
"WAJIB: Sebut nama peserta yang kamu respons di kalimat pertama "
"(contoh: 'Poin [Nama] soal X kurang tepat karena...' atau '[Nama], angkamu dari mana?')."
```

menjadi lebih fleksibel:

```python
"Respons ke salah satu peserta — boleh sebut namanya, boleh juga langsung counter argumennya "
"tanpa sebut nama. Yang penting posisimu jelas dan berbeda dari yang sudah bicara."
```

#### 4. Pass `idx_agen` dari loop simulasi

Ubah `_proses_satu_agen()` agar menerima `idx_agen`, lalu teruskan ke `build_influence_context()`.

Contoh:

```python
def _proses_satu_agen(
    agen: dict,
    ronde_ke: int,
    topik_ronde: str,
    pendapat_dalam_ronde_ini: list[dict],
    idx_agen: int = 0,
) -> dict:
```

Lalu:

```python
konteks_pengaruh = build_influence_context(
    agen,
    konteks_sumber,
    idx_agen=idx_agen,
)
```

Dan di loop:

```python
res = _proses_satu_agen(
    agen,
    ronde_ke,
    topik_ronde,
    pendapat_dalam_ronde_ini,
    idx_agen=idx,
)
```

---

## BUG #22 — Mahasiswa Masih Buka dengan "Gue rasa/Gue pikir"

### File

- `backend/simulation.py`

### Gejala

Mahasiswa masih membuka kalimat dengan:

```txt
"Gue rasa..."
"Gue pikir..."
```

Padahal sudah ada larangan untuk "Saya pikir" dan "Saya rasa".

### Yang harus dilakukan

Perluas larangan di `system_p`.

Ganti:

```python
"JANGAN buka kalimat dengan 'Saya pikir' atau 'Saya rasa' — langsung ke poin. "
```

menjadi:

```python
"JANGAN buka kalimat dengan frasa pendapat seperti 'Saya pikir', 'Saya rasa', "
"'Gue rasa', 'Gue pikir', 'Menurut saya', 'Menurut gue' — langsung ke poin atau fakta. "
```

---

## BUG #23 — Pekerja Kantoran Menulis Terlalu Panjang

### File

- `backend/agents.py`
- `backend/simulation.py`

### Gejala

Pekerja Kantoran bisa menghasilkan respons panjang seperti esai, sampai 8 kalimat.

### Penyebab

Role saat ini memakai kata "terstruktur", yang mendorong LLM menulis pembuka-isi-penutup panjang.

### Yang harus dilakukan

#### 1. Ubah role Pekerja Kantoran di `agents.py`

Ganti:

```python
"role": (
    "Kamu pekerja kantoran yang profesional dan pragmatis, fokus pada efisiensi, stabilitas karir, dan keseimbangan hidup-kerja. "
    "Menyampaikan pendapat terstruktur berbasis pengalaman kerja nyata, dengan bahasa profesional namun mudah dipahami."
),
```

menjadi:

```python
"role": (
    "Kamu pekerja kantoran yang pragmatis — bicara singkat, langsung ke dampak nyata pada pekerjaan dan penghasilan. "
    "Tidak bertele-tele. Satu poin, satu sudut pandang, selesai."
),
```

#### 2. Tambahkan post-processing maksimal 3 kalimat

Jangan hanya mengandalkan prompt. Setelah:

```python
jawaban = call_llm(...)
```

tambahkan pure Python post-processing untuk memastikan output agent maksimal 3 kalimat.

Syarat:
- tidak menambah LLM call
- tidak mengubah schema response
- jangan merusak teks terlalu agresif
- cukup potong di batas akhir kalimat

Contoh pendekatan:

```python
def _batasi_kalimat(teks: str, max_kalimat: int = 3) -> str:
    ...
```

Lalu setelah LLM call:

```python
jawaban = _batasi_kalimat(jawaban, max_kalimat=3)
```

---

## ISSUE #21 — Akademisi Netral 0 di Semua Ronde

### File

- `backend/agents.py`

### Gejala

Akademisi terlalu sering netral dan tidak menggerakkan dinamika simulasi.

### Penyebab

Role terlalu menekankan analisis seimbang, sehingga LLM menghindari posisi jelas.

### Yang harus dilakukan

Ubah Akademisi agar lebih tegas berbasis data, tapi jangan dibuat agresif membabi buta.

Ganti:

```python
"kepribadian": {"openness": 0.95, "agreeableness": 0.6, "neuroticism": 0.3},
"role": (
    "Kamu dosen dan peneliti yang menganalisis isu berdasarkan data empiris, teori ilmiah, dan studi komparatif. "
    "Menyampaikan pendapat dengan referensi mendalam namun tetap mudah dipahami orang awam."
),
```

menjadi:

```python
"kepribadian": {"openness": 0.95, "agreeableness": 0.35, "neuroticism": 0.4},
"role": (
    "Kamu dosen dan peneliti yang berani menyimpulkan berdasarkan data. "
    "Data bukan alasan untuk selalu netral — data dipakai untuk menentukan posisi yang paling kuat. "
    "Jika bukti condong ke satu arah, katakan jelas. Jika argumen peserta lain lemah secara data, koreksi langsung dengan tenang."
),
```

Catatan penting:
- Akademisi boleh netral jika data memang seimbang.
- Tapi jangan selalu bersembunyi di posisi netral.
- Akademisi harus memberi kontribusi analitis yang mengubah dinamika.

---

## ISSUE #22 — Pemerintah Mengkritik Pemerintah/Tokoh Pemerintah di Topik

### File

- `backend/simulation.py`

### Gejala

Agen Pemerintah kadang mengkritik "Prabowo" atau pemerintah seperti pihak luar, padahal dia seharusnya mewakili pemerintah.

### Diagnosis Revisi

Masalah ini bukan hanya karena agen pembuka ronde 1.

Root cause yang lebih penting adalah **stance alignment**:
Agen Pemerintah harus paham bahwa jika topik membahas pemerintah/tokoh pemerintah, ia mewakili pihak tersebut.

### Yang harus dilakukan

#### 1. Tambahkan stance rule khusus Pemerintah di `system_p`

Di `_proses_satu_agen()`, jika agen adalah Pemerintah atau role-nya mengandung "pejabat pemerintah", tambahkan instruksi khusus.

Contoh:

```python
stance_rule = ""
if "pemerintah" in agen["nama"].lower() or "pejabat pemerintah" in agen["role"].lower():
    stance_rule = (
        "Khusus posisimu: kamu mewakili pemerintah/tokoh pemerintah dalam topik ini. "
        "JANGAN menyerang pemerintah atau tokoh pemerintah yang sedang kamu wakili. "
        "Jika ada masalah, akui sebagai tantangan yang sedang ditangani, lalu jelaskan langkah, kebijakan, atau klarifikasi pemerintah. "
    )
```

Lalu masukkan `stance_rule` ke `system_p`.

#### 2. Tambahkan guard untuk agen pembuka ronde 1

Tetap tambahkan guard ini, tapi jangan anggap sebagai satu-satunya solusi.

Di `_proses_satu_agen()`:

```python
adalah_pembuka = (
    ronde_ke == 1
    and not pendapat_dalam_ronde_ini
    and not pendapat_ronde_sebelumnya
)
```

Lalu di bagian `parts`:

```python
if ada_yang_sudah_bicara and konteks_pengaruh:
    parts.append(konteks_pengaruh)
    parts.append(
        "Respons ke salah satu peserta — boleh sebut namanya, boleh juga langsung counter argumennya "
        "tanpa sebut nama. Yang penting posisimu jelas dan berbeda dari yang sudah bicara."
    )
elif adalah_pembuka:
    if briefing_real:
        parts.append(f"Info konteks: {briefing_real[:200]}")
    parts.append("Buka diskusi dengan posisimu yang paling kuat tentang topik ini.")
elif ronde_ke == 1 and briefing_real:
    parts.append(f"Info: {briefing_real[:200]}")
```

---

## File yang Boleh Diubah

Hanya file berikut:

```txt
backend/simulation.py
backend/memory.py
backend/agents.py
```

## File yang Tidak Boleh Diubah

Jangan ubah:

```txt
backend/llm.py
backend/sentiment.py
backend/graph.py
backend/ml_pipeline.py
backend/scraper.py
backend/engine.py
backend/social_engine.py
backend/feedback.py
main.py
frontend/*
```

---

## Urutan Prioritas

1. BUG #21 — variasi target respons antar agen
2. BUG #22 — larangan "Gue rasa/Gue pikir"
3. BUG #23 — Pekerja Kantoran terlalu panjang + post-processing 3 kalimat
4. ISSUE #21 — Akademisi lebih tegas berbasis data
5. ISSUE #22 — stance alignment Pemerintah + guard pembuka ronde 1

---

## Target Output Setelah Sesi Ini

Contoh kualitas output yang diinginkan:

```txt
[R1] Mahasiswa: Rupiah di 16.200 dan pemerintah masih bilang stabil — stabil versi siapa? Rakyat kecil yang bayar harga dari kebijakan kabur begini.

[R1] Pengusaha/UMKM: Biaya impor naik, bahan baku ikut naik. Buat UMKM, ini bukan debat makro — ini langsung kena margin.

[R1] Pekerja Kantoran: Gaji tetap, belanja naik. Kebijakan bagus di konferensi pers tidak banyak artinya kalau dompet makin tipis.

[R1] Pemerintah: Stabilisasi butuh waktu. Pemerintah sudah menyiapkan langkah fiskal dan moneter agar tekanan tidak makin berat ke masyarakat.

[R1] Akademisi: Data nilai tukar menunjukkan tekanan eksternal memang ada, tapi respons kebijakan domestik belum cukup kuat. Jadi masalahnya gabungan, bukan satu faktor tunggal.

[R1] Jurnalis/Media: Pemerintah bilang langkah sudah disiapkan, tapi publik butuh angka dan tenggat. Tanpa itu, klaim stabilisasi cuma terdengar seperti humas.

[R1] Oposisi Kritis: Pemerintah selalu menyalahkan faktor global saat gagal. Kalau kebijakan kuat, rakyat tidak terus jadi korban pelemahan rupiah.
```

---

## Strict Rules

1. Jangan ubah schema response API.
2. Tidak boleh menambah LLM call baru.
3. Tetap Groq free-tier aware.
4. Jangan ubah file di luar `simulation.py`, `memory.py`, dan `agents.py`.
5. Jangan sentuh `engine.py`.
6. Jangan ubah ML pipeline pada sesi ini.
7. Jangan lakukan refactor arsitektur besar.
8. Pastikan perubahan backward compatible.
9. Jika signature `build_influence_context()` berubah, pastikan semua pemanggilnya diupdate.
10. Setelah implementasi, jelaskan file apa saja yang berubah dan kenapa.

---

## Definisi Sukses

Sesi ini dianggap berhasil jika:

- Tidak ada 3 agen membuka dengan template kalimat yang sama.
- Mahasiswa tidak lagi membuka dengan "Gue rasa/Gue pikir".
- Pekerja Kantoran tidak lagi menulis esai panjang.
- Output agent maksimal 3 kalimat.
- Akademisi lebih berposisi dan tidak selalu netral.
- Pemerintah tidak menyerang pemerintah/tokoh pemerintah yang seharusnya ia wakili.
- Tidak ada LLM call tambahan.
- API response tetap kompatibel.
