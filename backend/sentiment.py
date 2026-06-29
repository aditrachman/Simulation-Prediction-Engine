# backend/sentiment.py
# Sentiment scoring — tiga mode:
#   "ml"     → TF-IDF + LogisticRegression classifier (DEFAULT)
#   "llm"    → LLM-based, akurat untuk kalimat kompleks
#   "inline" → kamus kata kunci, 0 token tambahan (fallback / free tier ketat)
#
# Set via .env: SENTIMENT_MODE=ml | llm | inline
# DEFAULT: llm — ML auto-train jika model belum ada.
# Fallback chain: ML → LLM → inline
#
# Label: "positif" | "netral" | "negatif"
#   positif = mendukung / setuju / pro terhadap isu/topik
#   negatif = menolak / khawatir / kritis terhadap isu/topik
#   netral  = skeptis terhadap klaim, berimbang, atau tidak berpihak

import re

from .llm import call_llm_json, MODEL_AGENT, MAX_TOKENS_SENTIMENT, SENTIMENT_MODE
from . import sentiment_ml


# ---------------------------------------------------------------------------
# Kamus Kata Kunci (mode inline — fallback saja)
#
# KETERBATASAN INLINE:
#   Kalimat seperti "saya tidak percaya klaim itu, tidak ada bukti kuat"
#   penuh kata negatif tapi maknanya SKEPTIS/NETRAL terhadap topik.
#   Inline scorer tidak bisa membedakan konteks ini.
#   Gunakan mode LLM untuk akurasi yang memadai.
# ---------------------------------------------------------------------------

_KATA_NEGATIF = {
    "menolak", "tolak", "kontra", "antipati", "keberatan",
    "bahaya", "berbahaya", "merugikan", "rugi", "rugikan",
    "ancaman", "mengancam", "risiko", "berisiko",
    "masalah", "bermasalah", "salah", "keliru", "cacat",
    "pelanggaran", "melanggar", "ilegal", "semena",
    "menyalahgunakan", "disalahgunakan", "penyalahgunaan", "eksploitasi",
    "khawatir", "kekhawatiran", "takut", "was-was", "resah",
    "meresahkan", "mengkhawatirkan", "memprihatinkan", "prihatin",
    "buruk", "jelek", "rusak", "merusak",
    "kecewa", "menyedihkan", "menyakitkan", "merampas",
    "mencekik", "memberatkan", "mempersulit",
    "larang", "dilarang", "hentikan", "stop", "hapus",
    "cabut", "batalkan", "cegah",
    "curiga", "curigai", "mencurigai", "skeptis",
    # BUG #2 FIX: Tambah kata kunci negatif umum yang hilang
    "kenaikan", "naik", "mahal", "kemahalan", "tinggi",
    "turun", "penurunan", "merosot", "anjlok", "jatuh",
    "beban", "membebani", "terbebani", "pajak", "pungutan",
    "korupsi", "koruptor", "nepotisme", "kolusi",
    "krisis", "darurat", "bencana", "malapetaka",
    "diskriminasi", "ketidakadilan", "timpang", "senjang",
    "pengangguran", "miskin", "kemiskinan", "kelaparan",
    "kebocoran", "pemborosan", "boros", "sia-sia",
    "gagal", "kegagalan", "kerugian",
}

_KATA_POSITIF = {
    "setuju", "mendukung", "dukung", "sokong", "sepakat", "pro",
    "manfaat", "bermanfaat", "menguntungkan", "membantu",
    "meningkatkan", "memperbaiki", "solusi",
    "bagus", "baik", "tepat", "cocok", "sesuai",
    "efisien", "efektif", "inovatif",
    "rasional", "didukung", "percaya",
    # BUG #2 FIX: Tambah kata kunci positif umum yang hilang
    "stabil", "stabilitas", "aman", "keamanan",
    "adil", "keadilan", "merata", "pemerataan",
    "sejahtera", "kesejahteraan", "makmur", "kemakmuran",
    "berhasil", "keberhasilan", "sukses", "kesuksesan",
    "tumbuh", "pertumbuhan", "berkembang", "perkembangan",
    "reformasi", "perbaikan", "pembenahan",
    "terobosan", "kemajuan", "maju", "modern",
    "terjangkau", "murah", "ringan",
    "terbuka", "transparan", "akuntabel",
    "apresiasi", "menghargai", "hormati",
}

_NEGASI = {"tidak", "nggak", "gak", "bukan", "jangan", "tanpa", "belum"}

_FRASA_KONTRAS = {
    "namun", "tetapi", "tapi", "meski", "meskipun",
    "walaupun", "walau", "akan tetapi", "sayangnya", "ironisnya",
}


# ---------------------------------------------------------------------------
# Inline Scorer — HANYA dipakai jika SENTIMENT_MODE=inline
# ---------------------------------------------------------------------------

def _score_inline(teks: str, topik: str = "") -> dict:
    teks_bersih = re.sub(r"[^\w\s]", " ", teks.lower())
    kata = teks_bersih.split()
    skor = 0.0

    for i, k in enumerate(kata):
        jendela = kata[max(0, i - 3):i]
        ada_negasi = any(n in jendela for n in _NEGASI)

        if k in _KATA_POSITIF:
            skor += -0.35 if ada_negasi else 0.35
        elif k in _KATA_NEGATIF:
            skor += 0.35 if ada_negasi else -0.35

        if k in _FRASA_KONTRAS:
            skor -= 0.1

    skor = max(-1.0, min(1.0, skor))

    # Threshold konservatif: butuh >= 0.35 agar tidak jatuh ke netral
    if skor >= 0.35:
        label = "positif"
    elif skor <= -0.35:
        label = "negatif"
    else:
        label = "netral"
        skor = 0.0

    return {"label": label, "skor": round(skor, 2)}


# ---------------------------------------------------------------------------
# BUG #2 FIX: Implicit Negative Context Detection
# Pola-pola ini sering tidak terdeteksi ML/inline scorer karena konteksnya tersirat.
# Jika pola ini ditemukan, paksa gunakan LLM scorer (tidak pakai ML/inline).
# ---------------------------------------------------------------------------

_IMPLICIT_NEGATIVE_PATTERNS = [
    # "lebih suka pekerjaan lain" dalam konteks pertanian/sektor tertentu = implisit negatif
    r"lebih\s+(tertarik|suka|memilih|prefer).{0,30}pekerjaan\s+(lain|lainnya|selain|di\s+luar)",
    # Pertanyaan retoris kritis — "mengapa tidak banyak yang tahu", "mengapa harus", dll
    r"mengapa\s+(tidak|belum|harus|perlu).{0,50}\?",
    r"kenapa\s+(tidak|belum|harus|perlu).{0,50}\?",
    # "tidak melihat ada upaya serius" — kritik tersembunyi
    r"tidak\s+melihat\s+ada\s+upaya\s+serius",
    r"tidak\s+(ada|terlihat|tampak)\s+(upaya|usaha|langkah)\s+serius",
    # "belum cukup", "tidak efektif jika", "tidak efektif"
    r"(belum|tidak)\s+cukup\s+(serius|kuat|efektif|memadai|signifikan)",
    r"tidak\s+efektif\s+(jika|kalau|bila|ketika|karena)",
    # Pertanyaan implisit skeptis: "bisa menjadi contoh tapi mengapa tidak..."
    r"bisa\s+(menjadi|jadi)\s+.{0,40}tapi\s+(mengapa|kenapa)\s+tidak",
    r"bagus\s+(tapi|tetapi|namun)\s+(mengapa|kenapa)\s+(tidak|belum)",
    # "tidak ada yang peduli", "tidak ada solusi", "tidak ada hasil"
    r"tidak\s+ada\s+(yang\s+peduli|solusi|hasil|perubahan|perkembangan)",
    # Implisit ketidakpuasan: "seharusnya", "mestinya" diikuti kritik
    r"(seharusnya|mestinya|harusnya)\s+(lebih|sudah|bisa|dapat)\s+(baik|serius|efektif|berhasil)",
    # ── BUG SENTIMEN FIX: Pola negatif implisit baru ──
    # "belum/tidak terbukti/efektif/berhasil/merata/optimal"
    r"(belum|tidak)\s+(terbukti|efektif|berhasil|merata|optimal)",
    # "perlu/harus ditinjau/dievaluasi/diperbaiki/dipertanyakan"
    r"(perlu|harus)\s+(ditinjau|dievaluasi|diperbaiki|dipertanyakan)",
    # "sulit/susah dipercaya/diterima/dibuktikan"
    r"(sulit|susah)\s+(dipercaya|diterima|dibuktikan)",
    # "masih banyak yang (belum/tidak/kekurangan/masalah)"
    r"masih\s+banyak\s+(yang\s+)?(belum|tidak|kekurangan|masalah)",
    # "meragukan", "patut dipertanyakan", "perlu dikritisi"
    r"(meragukan|patut\s+dipertanyakan|perlu\s+dikritisi)",
    # "belum tentu" → skeptis/negatif implisit
    r"belum\s+tentu",
    # "kekhawatiran" → sinyal negatif implisit
    r"kekhawatiran",
]

_IMPLICIT_NEGATIVE_COMPILED = [re.compile(p, re.IGNORECASE) for p in _IMPLICIT_NEGATIVE_PATTERNS]


def _has_implicit_negative(teks: str) -> bool:
    """Deteksi pola sentimen negatif tersirat yang sulit ditangkap ML/inline scorer."""
    for pattern in _IMPLICIT_NEGATIVE_COMPILED:
        if pattern.search(teks):
            return True
    return False


# Mampu handle: negasi ganda, kalimat skeptis, frasa ambigu, konteks topik
# ---------------------------------------------------------------------------

def _score_llm(teks: str, topik: str = "") -> dict:
    system = (
        "Klasifikasi sentimen pendapat terhadap isu Indonesia.\n"
        "  positif = MENDUKUNG / SETUJU / PRO terhadap isu\n"
        "  negatif = MENOLAK / KHAWATIR / KRITIS terhadap isu\n"
        "  netral  = berimbang atau tidak berpihak\n"
        # BUG-07 FIX: instruksi eksplisit untuk negasi kontekstual dan frasa pembalik
        "PERHATIAN KHUSUS — baca keseluruhan kalimat, bukan hanya keyword:\n"
        "  • Frasa 'bahkan sebaliknya', 'justru berlawanan', 'tidak ada bukti', "
        "'terbukti gagal', 'saya tidak melihat ada bukti' → sinyal NEGATIF "
        "meski ada kata positif di sekitarnya.\n"
        "  • Frasa 'tidak efektif', 'tidak akan berdampak', 'membebani', 'mengganggu' → NEGATIF.\n"
        "  • Ironi dan pertanyaan retoris kritis (mis. 'apakah benar-benar efektif?') → cenderung NEGATIF.\n"
        "  • Kata positif di awal kalimat yang langsung diikuti klarifikasi negatif → ikuti kesimpulan akhir.\n"
        # BUG-09 FIX: Tambahkan instruksi untuk bahasa gaul agar tidak auto-netral
        "BUG-09 FIX — BAHASA GAUL BUKAN SINYAL NETRAL:\n"
        "  • Bahasa informal/gaul seperti 'gue rasa ini salah', 'ini nggak masuk akal bro', "
        "'setuju banget', 'nggak percaya klaim itu' → TETAP baca sebagai sentimen KUAT, bukan netral hanya karena informal.\n"
        "  • Kalimat berisi POSISI JELAS (mendukung atau menolak) meski singkat atau informal "
        "HARUS diberi skor > 0.3 atau < -0.3, bukan 0.\n"
        "  • Contoh: 'Gue rasa ini nggak bener' → skor NEGATIF (-0.6+), bukan netral (0.0).\n"
        # BUG-15 FIX: Pertanyaan retoris kritis dan kalimat "gagal"
        "BUG-15 FIX — PERTANYAAN RETORIS KRITIS = NEGATIF:\n"
        "  • Pertanyaan yang meragukan kinerja pemerintah/kebijakan seperti:\n"
        "    'Apa yang dilakukan pemerintah selama ini?', 'Mengapa ini belum berubah?',\n"
        "    'Apakah pemerintah sudah melakukan cukup?' → NEGATIF (-0.4 sampai -0.6)\n"
        "  • Frasa yang mengandung kegagalan eksplisit seperti:\n"
        "    'gagal mencapai target', 'tidak terwujud', 'jauh dari harapan',\n"
        "    'masih banyak yang belum', 'belum dapat menikmati' → NEGATIF meski ada kalimat netral lain.\n"
        "  • Kalimat campuran: 'pemerintah telah mengambil langkah, NAMUN masih banyak yang belum...' → NEGATIF\n"
        "    (kata 'namun/tetapi/tapi' diikuti fakta kegagalan = kesimpulan NEGATIF)\n"
        "  • Contoh: 'Apa yang dilakukan pemerintah selama ini?' → {\"label\":\"negatif\",\"skor\":-0.5}\n"
        "  • Contoh: 'Kebijakan telah gagal mencapai target, masih banyak siswa belum dapat menikmati' → {\"label\":\"negatif\",\"skor\":-0.65}\n"
        "  • Contoh: 'Tidak terwujud, jauh dari harapan' → {\"label\":\"negatif\",\"skor\":-0.6}\n"
        "  • 'belum tentu ini langkah yang tepat' → NEGATIF (ragu-ragu terhadap langkah = bentuk kritik)\n"
        "  • 'saya rasa kebijakan ini perlu ditinjau ulang' → NEGATIF (mempertanyakan = kritis)\n"
        "  • 'ada kekhawatiran yang cukup beralasan' → NEGATIF (kekhawatiran = sinyal ketidaksetujuan)\n"
        "Contoh lain:\n"
        "  'memberatkan rakyat' → {\"label\":\"negatif\",\"skor\":-0.8}\n"
        "  'mendukung demi kebaikan bersama' → {\"label\":\"positif\",\"skor\":0.7}\n"
        "  'ada sisi positif dan negatif' → {\"label\":\"netral\",\"skor\":0.0}\n"
        "  'tidak ada bukti kuat bahwa kebijakan ini efektif, bahkan sebaliknya' → {\"label\":\"negatif\",\"skor\":-0.6}\n"
        "  'gue rasa ini nggak bener' → {\"label\":\"negatif\",\"skor\":-0.65}\n"
        # BUG-17 FIX: "tidak setuju" di kalimat manapun → negatif
        "BUG-17 FIX — 'SETUJU'/'TIDAK SETUJU' ADALAH PENENTU UTAMA:\n"
        "  • Jika teks mengandung 'kami tidak setuju', 'saya tidak setuju', 'kami menolak',\n"
        "    'saya menolak', 'kami tidak sependapat' di kalimat MANAPUN → label NEGATIF.\n"
        "    Terlepas dari isi kalimat lain. Kalimat penolakan adalah kesimpulan akhir.\n"
        "  • Contoh: 'Dokumen menunjukkan data A. Namun kami tidak setuju dengan kesimpulan itu.' → {\"label\":\"negatif\",\"skor\":-0.5}\n"
        "  • Contoh: 'Ada beberapa poin bagus, tapi kami menolak argumen utamanya.' → {\"label\":\"negatif\",\"skor\":-0.6}\n"
        "  • Jika ada 'kami tidak setuju', 'saya tidak setuju', 'kami menolak', 'saya menolak'\n"
        "    di kalimat MANAPUN — termasuk kalimat terakhir — label HARUS NEGATIF.\n"
        "    TIDAK ADA PENGECUALIAN. Kalimat penolakan = kesimpulan akhir, bukan hanya konteks.\n"
        "  • Frasa 'tidak relevan', 'tidak akurat', 'tidak tepat', 'tidak benar',\n"
        "    'tidak terlalu relevan', 'tidak sepenuhnya akurat', 'tidak sepenuhnya tepat'\n"
        "    — yang menyatakan bahwa klaim/pendapat tentang topik TIDAK BENAR → NEGATIF.\n"
        "  • Contoh: 'klaim tentang kebutuhan pertahanan tidak sepenuhnya akurat'\n"
        "    → {\"label\":\"negatif\",\"skor\":-0.5}\n"
        # BUG-18 FIX: pertanyaan efektivitas dari Oposisi bukan dukungan
        "BUG-18 FIX — PERTANYAAN EFISIENSI/EFEKTIVITAS DARI OPOSISI BUKAN DUKUNGAN:\n"
        "  • Kalimat seperti 'apakah alokasi anggaran efektif?', 'apakah kebijakan ini efisien?'\n"
        "    dari agen oposisi/kritis → NEGATIF atau NETRAL (skeptis), BUKAN positif.\n"
        "  • Pertanyaan kritis adalah KERAGUAN terselubung, bukan pujian.\n"
        "  • Contoh: 'pertanyaan yang lebih relevan adalah apakah alokasi anggaran tersebut efektif dan efisien'\n"
        "    dari Oposisi → {\"label\":\"negatif\",\"skor\":-0.3}\n"
        "  • Contoh: 'efektivitas kebijakan ini masih perlu dipertanyakan' → {\"label\":\"negatif\",\"skor\":-0.4}\n"
        "  • Pertanyaan yang mengandung kata 'apakah', 'seberapa', 'bagaimana', 'mengapa', 'kenapa'\n"
        "    yang mempertanyakan efektivitas/efisiensi/keberhasilan/kebutuhan suatu kebijakan\n"
        "    = NEGATIF atau NETRAL (skeptis), BUKAN positif — terlepas dari siapa yang bertanya.\n"
        "  • Contoh: 'mengapa pemerintah harus membelanjakan dana untuk ini?' → NEGATIF.\n"
        'Balas HANYA JSON: {"label":"positif|netral|negatif","skor":<-1.0..1.0>}'
    )
    user = f'Isu: "{topik[:60]}"\nPendapat: "{teks[:200]}"'

    result = call_llm_json(system, user, max_tokens=MAX_TOKENS_SENTIMENT, model=MODEL_AGENT)

    # Jika LLM gagal hasilkan JSON valid (model 8B sering gagal) → fallback inline
    if not result or not isinstance(result, dict):
        return _score_inline(teks, topik)

    label = result.get("label", "")
    skor  = result.get("skor", None)

    # Fallback inline jika label tidak valid atau skor tidak ada
    if label not in ("positif", "netral", "negatif") or skor is None:
        return _score_inline(teks, topik)

    try:
        skor = max(-1.0, min(1.0, float(skor)))
    except Exception:
        return _score_inline(teks, topik)

    # Koreksi konsistensi label ↔ skor
    if label == "positif":
        skor = abs(skor) if skor != 0.0 else 0.5
    elif label == "negatif":
        skor = -abs(skor) if skor != 0.0 else -0.5
    else:
        # netral tapi skor kuat → koreksi label
        if skor >= 0.35:
            label = "positif"
        elif skor <= -0.35:
            label = "negatif"
        else:
            skor = 0.0

    return {"label": label, "skor": round(skor, 2)}


# ---------------------------------------------------------------------------
# Sesi 15 — BUG #26: Post-processing filter untuk forbidden opening patterns
# ---------------------------------------------------------------------------

_FORBIDDEN_OPENS = [
    # Cuma yang BENAR-BENAR robotik — buang sisanya biar agent bisa bicara natural
    r"^Data menunjukkan bahwa\b",
    r"^Berdasarkan data\b",
    r"^Studi menunjukkan bahwa\b",
    r"^Penelitian menunjukkan\b",
    # Penolakan yang terlalu formal
    r"^Saya tidak bisa menerima\b",
    r"^Saya tidak cocok\b",
    # Agent name prefixes — paling bikin kaku
    r"^[A-Z][a-zA-Z/]+(?:\s+[A-Z][a-zA-Z/]+)*\s*:",
    r"^Pengusaha\b",
    r"^Pekerja\b",
    r"^Pemerintah\b",
    r"^Mahasiswa\b",
    r"^Akademisi\b",
    r"^Jurnalis\b",
    r"^Masyarakat\b",
]

_FALLBACK_FORBIDDEN = (
    "Data dan dampak langsungnya perlu dilihat lebih jernih sebelum menyimpulkan."
)


def filter_forbidden_opens(jawaban: str) -> str:
    """
    BUG-13 FIX — Stabilization PR:
    Hapus kalimat jika menggunakan frasa terlarang, baik di awal output maupun di tengah-tengah.
    Jika setelah dihapus hasilnya kosong, gunakan fallback pendek.
    Dipanggil dua kali di simulation.py (sebelum & sesudah _batasi_kalimat).
    Pure Python — tidak menambah LLM call.
    """
    if not jawaban:
        return jawaban
    teks = jawaban.strip()
    
    # ─── CEGAH 1: Frasa terlarang di awal output ───
    for pattern in _FORBIDDEN_OPENS:
        if re.match(pattern, teks, re.IGNORECASE):
            kalimat = re.split(r'(?<=[.!?])\s+', teks)
            kalimat = [k for k in kalimat if k.strip()]
            if len(kalimat) > 1:
                return " ".join(kalimat[1:]).strip()
            # Satu kalimat terlarang → ganti fallback
            return _FALLBACK_FORBIDDEN
    
    # ─── BUG-13 CEGAH 2: Frasa terlarang di TENGAH output (di kalimat non-pertama) ───
    kalimat_list = re.split(r'(?<=[.!?])\s+', teks)
    kalimat_list = [k for k in kalimat_list if k.strip()]
    hasil = []
    
    for i, kalimat in enumerate(kalimat_list):
        kena = False
        # Cek apakah kalimat ini dimulai dengan frasa terlarang
        for pattern in _FORBIDDEN_OPENS:
            if re.match(pattern, kalimat.strip(), re.IGNORECASE):
                kena = True
                break
        
        # Jika kalimat tidak terlarang, masukkan ke hasil
        if not kena:
            hasil.append(kalimat)
    
    if not hasil:
        return _FALLBACK_FORBIDDEN
    
    return " ".join(hasil)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_sentiment(teks: str, topik: str = "", sentiment_mode: str | None = None) -> dict:
    """
    Nilai sentimen pendapat terhadap topik.

    Args:
        sentiment_mode: "ml", "inline", atau "llm". Jika None, pakai SENTIMENT_MODE dari env.

    Fallback chain:
        ML → LLM → inline
      (jika mode ML gagal, turun ke LLM; jika LLM gagal, turun ke inline)

    Label:
      positif = mendukung / pro terhadap topik
      negatif = menolak / khawatir / kritis terhadap topik
      netral  = skeptis terhadap klaim, berimbang, atau tidak berpihak
    """
    mode = sentiment_mode or SENTIMENT_MODE

    # ── BUG #2 FIX: Implicit Negative Context Detection ──────────────────────
    # Jika teks mengandung pola negatif tersirat (pertanyaan retoris kritis,
    # preferensi implisit, dll.), bypass ML dan paksa gunakan LLM.
    # BUG #9 FIX: Mode "inline" TIDAK boleh memanggil LLM — fallback ke inline saja.
    if mode == "inline":
        pass  # inline mode konsisten: tidak ada LLM call
    elif mode in ("ml",) and _has_implicit_negative(teks):
        print(f"[sentiment] Implicit negative pattern detected → force LLM")
        return _score_llm(teks, topik)


    # ML dipakai seluas mungkin — hanya fallback LLM jika benar-benar perlu.
    # Alasan:
    #   - TF-IDF ngram(1,3) sudah handle kontras, bigram/trigram masuk fitur training
    #   - Opini kebijakan Indonesia rata-rata 30-50 kata, threshold 25 terlalu ketat
    #   - Confidence threshold 0.6 terlalu tinggi untuk 3-class (random = 33%)
    # Fallback LLM hanya jika: confidence sangat rendah (<0.45) DAN kalimat panjang (>60 kata)
    if mode == "ml":
        if sentiment_ml.is_available():
            result = sentiment_ml.predict(teks)
            if result is not None:
                kata_count = len(teks.split())
                confidence = result.get("confidence", 0)
                # Kontras (namun/tapi/tetapi) tidak lagi trigger fallback —
                # ngram(1,3) sudah cover pola kontras dalam training data
                needs_llm = confidence < 0.55 or kata_count > 40
                if not needs_llm:
                    return {"label": result["label"], "skor": result["skor"]}
                print(f"[sentiment] ML fallback LLM (conf={confidence:.2f}, kata={kata_count})")
        else:
            print(f"[sentiment] ML model belum siap -> fallback LLM")
        return _score_llm(teks, topik)

    if mode == "inline":
        return _score_inline(teks, topik)

    return _score_llm(teks, topik)