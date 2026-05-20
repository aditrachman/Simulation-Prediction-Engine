# VoxSwarm Product Direction & PRD

## 1. Ringkasan

VoxSwarm adalah sistem simulasi opini publik Indonesia untuk membantu pengguna mengeksplorasi kemungkinan reaksi masyarakat terhadap isu, kebijakan, kampanye, narasi publik, atau peristiwa sosial.

VoxSwarm tidak diposisikan sebagai mesin ramalan yang memastikan masa depan. Produk ini diposisikan sebagai:

> Scenario rehearsal engine untuk membaca dinamika opini publik, risiko polarisasi, aktor penggerak, dan alasan di balik perubahan sikap.

Dengan kata lain, VoxSwarm membantu menjawab:

- Jika isu ini dilempar ke publik Indonesia, kelompok mana yang kemungkinan mendukung atau menolak?
- Apakah isu ini cenderung memicu polarisasi, konsensus, atau status quo?
- Argumen apa yang paling memicu konflik?
- Aktor mana yang paling memengaruhi arah diskusi?
- Bagaimana hasil berubah jika ada intervensi, framing, atau informasi baru?

## 2. Latar Belakang

Project ini terinspirasi dari sistem seperti MiroFish, yaitu workflow:

```txt
seed/context -> agent generation -> multi-agent simulation -> prediction/report
```

Namun, karena keterbatasan dana, model, infrastruktur, dan stage pengembangan, VoxSwarm tidak akan langsung mengejar skala besar seperti ribuan agent, GraphRAG penuh, knowledge graph kompleks, atau distributed simulation.

Fokus realistis VoxSwarm adalah membangun versi ringan dan spesifik:

> MiroFish-lite untuk opini publik Indonesia.

Alih-alih menjadi general-purpose prediction engine, VoxSwarm akan fokus pada domain yang lebih tajam:

```txt
Indonesian public opinion and polarization risk simulation.
```

## 3. Masalah yang Ingin Diselesaikan

Banyak keputusan publik, kampanye, atau narasi sosial gagal karena pembuat keputusan tidak cukup memahami bagaimana berbagai kelompok akan bereaksi.

Contoh:

- Kebijakan ekonomi diumumkan, tetapi UMKM dan pekerja merasa tidak didengar.
- Kampanye publik terlihat bagus secara internal, tetapi memicu backlash di media sosial.
- Isu politik menjadi polarisasi karena framing yang salah.
- Pemerintah, media, akademisi, dan masyarakat membaca isu dengan cara berbeda.

Masalah utama:

1. Sulit memetakan reaksi stakeholder sebelum isu menyebar luas.
2. Sulit memahami argumen mana yang memicu konflik.
3. Sulit membandingkan beberapa skenario komunikasi.
4. Banyak analisis opini publik mahal, lambat, atau terlalu manual.
5. LLM biasa memberi satu jawaban tunggal, bukan dinamika multi-pihak.

## 4. Target Pengguna

Target awal:

- Mahasiswa dan peneliti sosial/politik/komunikasi
- Policy analyst
- Tim komunikasi publik
- NGO/advocacy team
- Media analyst
- Campaign strategist
- Indie researcher

Target jangka panjang:

- Konsultan public affairs
- Pemerintah daerah/pusat
- Lembaga survei
- Brand/campaign team
- Think tank

## 5. Positioning Produk

### Positioning Utama

> VoxSwarm adalah engine simulasi opini publik Indonesia untuk mengeksplorasi risiko polarisasi, konsensus, dan perubahan sikap terhadap isu sosial, politik, ekonomi, dan kebijakan publik.

### Jangan Diposisikan Sebagai

- Mesin ramalan masa depan
- Pengganti survei publik
- Sistem prediksi ilmiah yang sudah tervalidasi penuh
- General multi-agent simulation framework
- GraphRAG engine skala enterprise

### Diposisikan Sebagai

- Scenario rehearsal tool
- Public reaction simulator
- Policy narrative stress-test tool
- Opinion dynamics explorer
- Explainable simulation report generator

## 6. Klaim yang Aman

### Klaim yang Aman

```txt
VoxSwarm membantu mengeksplorasi kemungkinan dinamika opini publik berdasarkan persona stakeholder dan konteks yang diberikan.
```

```txt
VoxSwarm mensimulasikan reaksi beberapa kelompok sosial terhadap isu untuk menemukan risiko polarisasi, aktor kunci, dan argumen pemicu.
```

```txt
Hasil VoxSwarm adalah sinyal eksploratif, bukan kepastian prediksi.
```

### Klaim yang Harus Dihindari

```txt
VoxSwarm memprediksi masa depan secara akurat.
```

```txt
VoxSwarm menggantikan survei publik.
```

```txt
Polarisasi 57% berarti hasil dunia nyata pasti begitu.
```

```txt
Sistem ini sudah setara MiroFish skala besar.
```

## 7. Prinsip Produk

1. Domain-first
   VoxSwarm fokus ke opini publik Indonesia, bukan simulasi multi-agent generik.

2. Explainability-first
   Angka prediksi harus selalu disertai alasan, aktor, argumen, dan jejak perubahan.

3. Low-cost by design
   Sistem harus tetap bisa berjalan dengan model murah/gratis seperti Groq free tier, Ollama, atau provider serupa.

4. LLM as voice layer, not full engine
   LLM dipakai untuk membuat suara agent dan analisis naratif, tetapi state, event, scheduler, dan scoring utama harus semakin banyak dikendalikan oleh sistem.

5. Honest uncertainty
   Produk harus jujur bahwa hasil adalah simulasi skenario, bukan kebenaran absolut.

6. Progressive sophistication
   Jangan langsung mengejar ribuan agent atau GraphRAG berat. Bangun fondasi bertahap.

## 8. Core Workflow

Workflow utama yang ditargetkan:

```txt
1. User memasukkan isu/topik
2. Sistem mengambil atau menerima konteks awal
3. Sistem memilih stakeholder agent Indonesia yang relevan
4. Agent berdiskusi dalam beberapa ronde
5. Event/intervensi bisa dimasukkan di tengah simulasi
6. Sistem menghitung sentimen, konflik, swing voter, dan aktor kunci
7. Sistem menghasilkan laporan explainable
8. User bisa memberi feedback terhadap hasil
```

Contoh input:

```txt
Rupiah semakin melemah di bawah kepemimpinan Prabowo
```

Contoh output:

- Prediksi skenario: Polarisasi / Konsensus / Status Quo
- Ringkasan dinamika
- Tren sentimen per agent
- Aktor penggerak
- Swing voter
- Argumen pemicu konflik
- Risiko komunikasi
- Rekomendasi framing
- Confidence note

## 9. Core Concepts

### Agent

Agent adalah representasi stakeholder sosial, bukan individu nyata.

Contoh:

- Mahasiswa
- Pengusaha/UMKM
- Pekerja Kantoran
- Pemerintah
- Akademisi
- Jurnalis/Media
- Masyarakat Umum
- Oposisi Kritis

Ke depan, agent harus dipisahkan menjadi:

- `AgentProfile`: data statis seperti nama, role, trait, influence
- `AgentState`: data dinamis seperti stance, trust, emotion, memory, volatility

### Memory

Memory awal boleh sederhana, tetapi arah jangka panjang:

- menyimpan pendapat sebelumnya
- menyimpan sikap akhir
- menyimpan perubahan stance
- menyimpan siapa yang dipercaya/ditolak
- menyimpan argumen yang memengaruhi agent

Memory bukan hanya ringkasan teks. Memory harus menjadi bagian dari state.

### Environment

Environment adalah konteks sosial simulasi:

- topik utama
- kategori isu
- konteks berita/data
- ronde/tick saat ini
- daftar event
- dinamika diskusi

### Event

Event adalah kejadian yang memengaruhi simulasi.

Contoh:

```json
{
  "type": "policy_intervention",
  "round": 2,
  "description": "Pemerintah mengumumkan subsidi baru",
  "impact_hint": {
    "Pemerintah": 0.2,
    "Masyarakat Umum": 0.4,
    "Pengusaha/UMKM": 0.3
  }
}
```

Intervensi tidak boleh hanya ditempel ke prompt. Ke depan, event harus menjadi object yang bisa dicatat, diproses, dan dijelaskan dampaknya.

### Simulation Loop

Loop simulasi harus berkembang dari:

```txt
agent prompt -> LLM answer -> sentiment -> report
```

menjadi:

```txt
state -> observation -> action -> validation -> state update -> metrics -> report
```

### Prediction Layer

Prediction layer harus jujur.

Ada tiga level:

1. Heuristic prediction
   Berdasarkan rule dari sentimen, volatilitas, konflik, dan distribusi agent.

2. ML experimental prediction
   Berdasarkan history dan feedback, tetapi diberi label experimental sampai validasi cukup.

3. Validated prediction
   Hanya bisa diklaim setelah dibandingkan dengan data nyata/historical cases.

### Explainability Layer

Explainability adalah pembeda utama VoxSwarm.

Setiap hasil harus menjawab:

- Kenapa hasilnya polarisasi/konsensus/status quo?
- Siapa aktor paling berpengaruh?
- Siapa swing voter?
- Argumen apa yang mengubah arah diskusi?
- Event mana yang berdampak?
- Seberapa yakin sistem terhadap hasil ini?

## 10. MVP Scope

### MVP yang Realistis

MVP VoxSwarm harus mencakup:

- 7-10 stakeholder agent Indonesia
- 3-5 ronde diskusi
- sentiment trend per agent
- prediksi skenario sederhana
- aktor kunci
- swing voter
- laporan explainable
- feedback user
- konteks berita/data ringan
- intervensi sederhana

### Tidak Wajib untuk MVP

- ribuan agent
- GraphRAG penuh
- Neo4j/Graphiti
- distributed worker
- real-time swarm visualization
- validasi ilmiah lengkap
- long-term memory kompleks
- model mahal

## 11. Non-Goals

Untuk tahap awal, VoxSwarm tidak mengejar:

- menjadi MiroFish clone skala penuh
- menjadi pengganti survei masyarakat
- menjadi sistem prediksi politik yang final
- mensimulasikan seluruh populasi Indonesia secara statistik
- mendukung semua domain dunia
- menjalankan ribuan LLM agent

## 12. Pembeda VoxSwarm

VoxSwarm harus berbeda melalui:

1. Fokus Indonesia
   Bahasa, isu, stakeholder, dan konteks lokal.

2. Public opinion workflow
   Fokus pada opini, polarisasi, dan komunikasi publik.

3. Explainable reporting
   Hasil bukan cuma angka, tetapi cerita sebab-akibat.

4. Low-cost architecture
   Bisa dijalankan oleh indie builder/mahasiswa tanpa biaya besar.

5. Scenario comparison
   Ke depan, user bisa membandingkan beberapa framing atau intervensi.

6. Feedback loop lokal
   Data feedback dari user Indonesia bisa menjadi aset unik.

## 13. Risiko Produk

### Risiko 1: Hasil dianggap prediksi pasti

Mitigasi:

- tampilkan disclaimer
- gunakan bahasa "simulasi mengarah ke", bukan "akan terjadi"
- tampilkan confidence dan limitation

### Risiko 2: Agent bias atau terlalu stereotip

Mitigasi:

- agent profile harus ditinjau
- persona tidak boleh merendahkan kelompok sosial
- gunakan archetype, bukan klaim representasi statistik

### Risiko 3: ML belajar dari label sistem sendiri

Mitigasi:

- pisahkan weak label dan feedback label
- tampilkan `prediction_source`
- jangan klaim ML akurat sebelum validasi

### Risiko 4: Overclaim GraphRAG

Mitigasi:

- jika hanya extraction, sebut "entity extraction"
- pakai istilah GraphRAG hanya jika sudah ada retrieval/graph reasoning yang nyata

### Risiko 5: Biaya LLM naik

Mitigasi:

- sentiment inline/local
- rule-based crowd agent
- batasi LLM agent
- caching
- short prompt
- model murah untuk agent voice

## 14. Arsitektur Target

Arsitektur target ringan:

```txt
backend/
  agents.py              # registry agent lama, sementara
  simulation.py          # loop lama, akan diperkecil bertahap
  memory.py              # memory lama, akan direstruktur
  sentiment.py           # scoring
  ml_pipeline.py         # experimental prediction
  graph.py               # entity extraction

  core/
    models.py            # AgentProfile, AgentState, Event, Action, SimulationState
    scheduler.py         # urutan agent dan target respons
    event_system.py      # event dan impact
    state_engine.py      # update state
    memory_store.py      # structured memory
    metrics.py           # polarization, volatility, consensus score
    reporting.py         # explainability report
```

Migrasi harus bertahap. Jangan rewrite total.

## 15. Roadmap

### Phase 0: Output Quality Hotfix

Tujuan:

- agent tidak template
- respons maksimal 3 kalimat
- Akademisi tidak selalu netral
- Pemerintah tidak menyerang pihak yang diwakili

Status:

- dikerjakan sebelum refactor besar

### Phase 1: Repositioning

Tujuan:

- update README
- ubah narasi produk
- hindari klaim "predict anything"
- fokus ke opini publik Indonesia

Deliverable:

- README baru
- tagline baru
- disclaimer
- contoh use case

### Phase 2: Domain Model

Tujuan:

- buat model formal untuk state dan event

Deliverable:

- `AgentProfile`
- `AgentState`
- `SimulationState`
- `SimulationEvent`
- `AgentAction`
- adapter dari dict lama ke model baru

### Phase 3: Event System

Tujuan:

- intervensi menjadi event object
- event punya ronde, payload, target, dan impact

Deliverable:

- event schema
- event log
- event impact scoring sederhana
- explanation: event mana berdampak ke siapa

### Phase 4: Scheduler

Tujuan:

- urutan agent dan target respons tidak hanya prompt-driven

Deliverable:

- sequential scheduler
- randomized scheduler
- influence-aware scheduler
- response target selector

### Phase 5: Structured Memory

Tujuan:

- memory tidak hanya list teks

Deliverable:

- stance memory
- argument memory
- relationship/trust memory sederhana
- memory summary tanpa LLM tambahan jika memungkinkan

### Phase 6: Prediction Cleanup

Tujuan:

- prediction lebih jujur dan explainable

Deliverable:

- heuristic prediction module
- ML experimental label
- confidence score
- clear separation between weak label and feedback label

### Phase 7: Scenario Comparison

Tujuan:

- user bisa membandingkan beberapa skenario

Deliverable:

- baseline vs intervention
- framing A vs framing B
- report comparison

### Phase 8: Swarm-lite

Tujuan:

- scale murah tanpa ribuan LLM call

Deliverable:

- 7-10 LLM stakeholder agents
- 50-200 rule-based crowd agents
- opinion cluster
- propagation graph sederhana

## 16. Success Metrics

### Product Metrics

- User bisa memahami kenapa hasil simulasi muncul
- User bisa membandingkan dua skenario
- Laporan mudah dibaca dan tidak overclaim
- Output agent terasa berbeda antar stakeholder
- Biaya per simulasi tetap rendah

### Technical Metrics

- Tidak ada LLM call tambahan untuk hal yang bisa dihitung rule-based
- Simulasi bisa dijalankan dengan 7-10 agent dalam waktu wajar
- State agent bisa diaudit
- Event log bisa ditampilkan
- Prediction source jelas: heuristic, ML, atau feedback-informed

### Trust Metrics

- Ada disclaimer
- Ada confidence note
- Ada evidence trace
- Ada limitation section
- Ada feedback mechanism

## 17. Contoh Bahasa di UI

### Aman

```txt
Simulasi ini mengarah ke polarisasi.
```

```txt
Berdasarkan dinamika agent, kelompok mahasiswa, media, dan oposisi mendorong sentimen negatif, sementara pemerintah mencoba menahan narasi melalui framing stabilisasi.
```

```txt
Confidence: medium. Konteks berita tersedia, tetapi belum ada validasi historis untuk topik ini.
```

### Tidak Aman

```txt
Isu ini pasti akan polarisasi.
```

```txt
Prediksi VoxSwarm 94% akurat.
```

```txt
Masyarakat Indonesia akan menolak kebijakan ini.
```

## 18. Final Verdict

VoxSwarm tetap bisa menjadi project yang kuat, tetapi arahnya harus realistis.

VoxSwarm tidak perlu menjadi MiroFish skala besar. VoxSwarm sebaiknya menjadi:

> MiroFish-lite yang fokus pada simulasi opini publik Indonesia, dengan explainability, biaya rendah, dan workflow yang jujur terhadap ketidakpastian.

Fokus ini membuat project lebih mungkin selesai, lebih mudah dibedakan, dan lebih bisa dipertanggungjawabkan.

Tujuan jangka pendek bukan membuktikan masa depan, tetapi membantu pengguna melihat kemungkinan dinamika sosial sebelum keputusan, narasi, atau kebijakan dilempar ke publik.

