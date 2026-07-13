# backend/wordcloud.py
# Word cloud data generator — ekstrak frekuensi kata dari opini agen per sentimen.
#
# Alur:
#   1. Terima hasil simulasi (ronde_detail)
#   2. Tokenize + filter stopword tiap pendapat agen
#   3. Kelompokkan per label sentimen (positif/netral/negatif)
#   4. Return {label: [{kata, frekuensi, warna}, ...]}
#
# Pure Python — tanpa dependency tambahan.

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

# ── Stopwords Bahasa Indonesia (ponytail: embedded, ga perlu ngorbanin bandwidth) ──
_STOPWORDS = {
    "dan", "di", "ke", "dari", "yang", "ini", "itu", "dengan", "untuk",
    "pada", "adalah", "akan", "telah", "sudah", "bisa", "dapat", "tidak",
    "ada", "juga", "atau", "saya", "kami", "kita", "mereka", "dia",
    "ia", "engkau", "kau", "anda", "ia", "si", "sang", "para",
    "oleh", "sebagai", "secara", "tanpa", "antara", "tentang", "seperti",
    "serta", "namun", "tetapi", "tapi", "sedangkan", "sementara", "meski",
    "meskipun", "walaupun", "walau", "sehingga", "maka", "agar", "supaya",
    "karena", "sebab", "jika", "kalau", "bila", "apabila", "setelah",
    "sebelum", "ketika", "saat", "selama", "hingga", "sampai", "sejak",
    "baru", "saja", "pun", "pernah", "belum", "sedang", "masih",
    "selalu", "sering", "jarang", "pernah", "sedikit", "banyak",
    "semua", "masing-masing", "setiap", "beberapa", "sejumlah",
    "hal", "hal-hal", "halnya", "perihal", "soal", "kasus", "masalah",
    "ini", "itu", "tersebut", "berikut", "berikutnya", "lalu",
    "dulu", "kemudian", "selanjutnya", "akhirnya", "awal", "mulai",
    "dalam", "luar", "atas", "bawah", "depan", "belakang", "samping",
    "dekat", "jauh", "sekitar", "kira-kira", "kurang", "lebih",
    "sangat", "paling", "agak", "cukup", "terlalu", "semakin",
    "begitu", "demikian", "seperti", "bagai", "laksana",
    "bukan", "tidak", "tak", "tiada", "tanpa", "jangan",
    "ya", "iya", "tentu", "pasti", "mungkin", "sepertinya",
    "kiranya", "rasanya", "nampaknya", "tampaknya", "katanya",
    "menurut", "berdasarkan", "mengenai", "terkait", "berkaitan",
    "via", "lewat", "melalui", "secara", "dengan", "pakai", "menggunakan",
    "yaitu", "yakni", "adalah", "ialah", "merupakan",
    "bahwa", "apakah", "siapa", "apa", "mengapa", "kenapa", "bagaimana",
    "berapa", "kapan", "dimana", "kemana", "darimana",
    "pun", "jua", "juga", "pula", "lagi", "hanya", "cuma",
    "per", "demi", "pun", "sih", "kok", "dong", "deh", "lah", "kah",
    "waktu", "masa", "era", "zaman", "abad", "tahun", "bulan", "minggu",
    "hari", "jam", "menit", "detik", "lama", "durasi",
    "orang", "manusia", "masyarakat", "publik", "umum", "warga",
    "negara", "pemerintah", "presiden", "menteri", "pejabat",
    "daerah", "pusat", "provinsi", "kota", "kabupaten", "desa",
    "indonesia", "jakarta", "nusantara",
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
    "ke-", "di-", "me-", "ber-", "ter-", "se-", "pe-", "per-",
    "halo", "hai", "oh", "ah", "wah", "nah", "aduh", "ya", "oh",
    "yaitu", "yakni", "ialah",
    # ── Kata percakapan informal ─────────────────────────────────
    "gue", "gw", "lu", "lo", "elo", "kita", "kami",
    "nggak", "gak", "ga", "kagak",
    "udah", "uda",
    "banget", "bgt", "bangett",
    "kayak", "kayaknya",
    "kan", "bro", "broh", "sis",
    "yah", "iy", "iyh",
    "sebenarnya", "sejujurnya", "terus", "terus terang",
    "honestly", "literally", "basically", "fair",
    "lihat", "loh", "tau", "tahu",
    "rasa", "rasanya",
    "sisi", "segi", "halnya",
    "bikin", "buat", "ngasih",
    "banyak", "sedikit",
    "langsung",
    # ── Kata data/riset generik yang noise di word cloud ──────────────
    "data", "survei", "statistik", "studi", "sample",
    "persepsi", "menunjukkan", "fakta", "faktanya",
    "riset", "penelitian", "peneliti",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize, lowercase, hapus non-alfabet, filter stopword & kata pendek."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = text.split()
    return [
        t for t in tokens
        if len(t) > 2 and t not in _STOPWORDS and not t.isdigit()
    ]


def extract_word_frequencies(ronde_detail: list[dict], top_n: int = 50) -> dict:
    """
    Ekstrak frekuensi kata dari opini agen, dikelompokkan per label sentimen.

    Args:
        ronde_detail: daftar ronde dari hasil simulasi (ronde_detail)
        top_n: jumlah kata teratas per label

    Returns:
        {
            "positif":  [{"kata": str, "frekuensi": int, "berat": float}, ...],
            "netral":   [...],
            "negatif":  [...],
            "total":    {"positif": int, "netral": int, "negatif": int, "all": int},
        }
    """
    if not ronde_detail:
        return _empty_result()

    counters: dict[str, Counter] = {
        "positif": Counter(),
        "netral":  Counter(),
        "negatif": Counter(),
    }
    total_words = {"positif": 0, "netral": 0, "negatif": 0}

    for ronde in ronde_detail:
        for agen in ronde.get("agen", []):
            label = agen.get("sentimen", {}).get("label", "netral")
            if label not in counters:
                label = "netral"
            pendapat = agen.get("pendapat", "") or ""
            tokens = _tokenize(pendapat)
            counters[label].update(tokens)
            total_words[label] += len(tokens)

    all_counters = counters

    result = {}
    for label, counter in all_counters.items():
        total = total_words[label] or 1
        # Ambil top_n, hitung frekuensi relatif (0-1) sebagai "berat"
        top_words = []
        for kata, freq in counter.most_common(top_n):
            top_words.append({
                "kata": kata,
                "frekuensi": freq,
                "berat": round(freq / total, 4),
            })
        result[label] = top_words

    grand_total = sum(total_words.values()) or 1
    result["total"] = {
        "positif": total_words["positif"],
        "netral":  total_words["netral"],
        "negatif": total_words["negatif"],
        "all":     grand_total,
    }

    return result


def extract_word_frequencies_from_texts(
    texts_by_label: dict[str, list[str]],
    top_n: int = 50,
) -> dict:
    """
    Ekstrak frekuensi kata dari teks yang sudah dikelompokkan per label.
    Alternatif jika data tidak berasal dari simulation ronde_detail.

    Args:
        texts_by_label: {"positif": ["teks1", "teks2"], "netral": [...], "negatif": [...]}
        top_n: jumlah kata teratas per label

    Returns: dict dengan format sama seperti extract_word_frequencies()
    """
    labels = ["positif", "netral", "negatif"]
    counters: dict[str, Counter] = {lbl: Counter() for lbl in labels}
    total_words: dict[str, int] = {lbl: 0 for lbl in labels}

    for label in labels:
        texts = texts_by_label.get(label, [])
        for teks in texts:
            tokens = _tokenize(teks)
            counters[label].update(tokens)
            total_words[label] += len(tokens)

    result = {}
    for label in labels:
        total = total_words[label] or 1
        top_words = []
        for kata, freq in counters[label].most_common(top_n):
            top_words.append({
                "kata": kata,
                "frekuensi": freq,
                "berat": round(freq / total, 4),
            })
        result[label] = top_words

    grand_total = sum(total_words.values()) or 1
    result["total"] = {
        "positif": total_words["positif"],
        "netral":  total_words["netral"],
        "negatif": total_words["negatif"],
        "all":     grand_total,
    }

    return result


def _empty_result() -> dict:
    return {
        "positif": [],
        "netral":  [],
        "negatif": [],
        "total":   {"positif": 0, "netral": 0, "negatif": 0, "all": 0},
    }
