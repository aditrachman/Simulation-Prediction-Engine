# backend/sentiment_ml.py
# ML-based sentiment classifier for Bahasa Indonesia.
# Menggunakan TF-IDF + LogisticRegression — 0 LLM call, deterministik, cepat.
#
# Alur:
#   1. Coba load model dari disk (backend/data/sentiment_model.pkl)
#   2. Jika belum ada, coba download SmSA dataset dan train
#   3. Jika gagal, pakai embedded bootstrap dataset minimal
#   4. predict() → {"label": "positif"|"netral"|"negatif", "skor": float}
#
# Integrasi: dipanggil dari sentiment.py sebagai mode "ml"

from __future__ import annotations

import csv
import io
import json
import os
import pickle
import re
import threading
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODEL_FILE = DATA_DIR / "sentiment_model.pkl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_model_lock = threading.Lock()
_pipeline: Optional[Pipeline] = None

# ── Label mapping ─────────────────────────────────────────────────────────────
_LABEL_MAP = {
    "positif": "positif",
    "positive": "positif",
    "negatif": "negatif",
    "negative": "negatif",
    "netral": "netral",
    "neutral": "netral",
}
_VALID_LABELS = {"positif", "netral", "negatif"}

# ── Sumber dataset ────────────────────────────────────────────────────────────
# Prioritas:
#   1. HuggingFace — kornwtp/smsa-ind-classification (11.000 sampel)
#   2. Direct URL — SmSA dari GitHub IndonLU (fallback)
#   3. Built-in 60 sampel (last resort)

SMSA_CSV_URLS = [
    "https://raw.githubusercontent.com/indobenchmark/indonlu/master/data/smsa_doc/train_preprocess.txt",
    "https://raw.githubusercontent.com/indobenchmark/indonlu/master/data/smsa_doc/valid_preprocess.txt",
]
SMSA_COLUMNS = ["label", "text"]

# Label mapping dari dataset kornwtp/smsa-ind-classification
_HF_LABEL_MAP = {0: "positif", 1: "netral", 2: "negatif"}


# ---------------------------------------------------------------------------
# Dataset Loader
# ---------------------------------------------------------------------------

def _load_hf_smsa() -> list[tuple[str, str]]:
    """Load SmSA dari HuggingFace datasets."""
    try:
        from datasets import load_dataset

        ds = load_dataset("kornwtp/smsa-ind-classification", split="train")
        results: list[tuple[str, str]] = []
        for item in ds:
            label_id = item["labels"]
            text = (item.get("texts") or "").strip()
            label = _HF_LABEL_MAP.get(label_id)
            if label and text and len(text) > 5:
                results.append((label, text))
        return results
    except Exception as exc:
        print(f"[sentiment_ml] HuggingFace dataset error: {exc}")
        return []


def _download_smsa() -> list[tuple[str, str]]:
    """Download SmSA dataset dari GitHub IndonLU. Return [(label, text), ...]."""
    results: list[tuple[str, str]] = []
    for url in SMSA_CSV_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(raw), fieldnames=SMSA_COLUMNS, delimiter="\t")
            for row in reader:
                label_raw = row.get("label", "").strip().lower()
                text = row.get("text", "").strip()
                label = _LABEL_MAP.get(label_raw)
                if label and text and len(text) > 5:
                    results.append((label, text))
        except Exception as exc:
            print(f"[sentiment_ml] Gagal download {url}: {exc}")
    return results


# ---------------------------------------------------------------------------
# Policy Domain Data Generator
# Menghasilkan ~600 sampel sintetis opini kebijakan agar model tidak bias
# ke domain product review dari SmSA.
# ---------------------------------------------------------------------------

_POLICY_POSITIF_TEMPLATES = [
    "saya {predikat} kebijakan ini",
    "saya {predikat} program {topik}",
    "saya {predikat} langkah pemerintah {topik}",
    "saya {predikat} rencana {topik}",
    "saya {predikat} usulan {topik}",
    "kami {predikat} kebijakan {topik}",
    "kami {predikat} program pemerintah",
    "sangat {predikat} dengan inisiatif ini",
    "saya sangat {predikat} dengan arah {topik}",
    "saya percaya kebijakan {topik} itu {manfaat}",
    "program {topik} ini {manfaat} bagi rakyat",
    "inisiatif {topik} ini {manfaat} sekali",
    "kebijakan {topik} sudah {hasil_pos}",
    "pemerintah telah {tindakan_pos} dalam {topik}",
    "langkah {topik} sudah {hasil_pos}",
    "saya optimis {topik} akan {dampak_pos}",
    "kebijakan ini {sifat_pos} dan perlu didukung",
    "program ini {sifat_pos} untuk masa depan",
    "saya dukung penuh kebijakan {topik}",
    "kami setuju dengan roadmap {topik}",
    "kebijakan {topik} terbukti {dampak_pos}",
    "alokasi dana untuk {topik} sudah {hasil_pos}",
    "reformasi {topik} ini {manfaat} bagi semua",
    "terobosan {topik} patut didukung",
    "saya apresiasi langkah pemerintah dalam {topik}",
    "data menunjukkan {topik} berhasil {dampak_pos}",
    "masyarakat merasakan {manfaat} dari {topik}",
    "program {topik} tepat sasaran dan efisien",
    "saya rasa {topik} adalah solusi yang tepat",
    "implementasi {topik} sudah {hasil_pos}",
    "kebijakan {topik} berpihak pada rakyat kecil",
    "transparansi dalam {topik} sudah {hasil_pos}",
    "target {topik} tercapai berkat kerja keras semua",
    "saya melihat {dampak_pos} dari program {topik}",
    "investasi di {topik} sangat {sifat_pos}",
    "data menunjukkan {topik} berhasil {dampak_pos}",
    "hasil survei membuktikan {topik} {manfaat}",
    "laporan terbaru menunjukkan {topik} mencapai target",
    "fakta di lapangan {topik} menunjukkan kemajuan",
    "studi membuktikan {topik} efektif dan efisien",
    "angka statistik menunjukkan {topik} {manfaat}",
    "penelitian membuktikan {topik} berdampak positif",
    "data empiris menunjukkan {topik} berjalan baik",
]

_POLICY_NEGATIF_TEMPLATES = [
    "saya menolak kebijakan {topik} ini",
    "saya tidak setuju dengan program {topik}",
    "saya tidak setuju dengan pendapat tentang {topik} itu",
    "saya khawatir kebijakan {topik} akan {dampak_neg}",
    "program {topik} ini {masalah} bagi rakyat",
    "kebijakan {topik} gagal {tujuan}",
    "pemerintah gagal dalam {topik}",
    "alokasi dana {topik} tidak efektif",
    "kebijakan {topik} hanya {kritik_neg}",
    "saya meragukan efektivitas program {topik}",
    "tidak ada bukti bahwa {topik} berhasil",
    "program {topik} justru {dampak_neg} masyarakat",
    "saya kecewa dengan kinerja {topik}",
    "kebijakan {topik} diskriminatif dan tidak adil",
    "anggaran {topik} membuang-buang uang negara",
    "korupsi di {topik} menunjukkan kegagalan",
    "klaim pemerintah tentang {topik} tidak akurat",
    "program {topik} memberatkan rakyat kecil",
    "saya tidak melihat manfaat dari program {topik}",
    "kebijakan {topik} melanggar hak warga",
    "data tentang {topik} tidak dapat dipercaya",
    "bukannya membantu program {topik} justru {dampak_neg}",
    "pertanyaan yang relevan apakah {topik} efektif",
    "kebijakan {topik} perlu dievaluasi ulang",
    "pemerintah tidak serius menangani {topik}",
    "program {topik} hanya menguntungkan segelintir orang",
    "saya tidak percaya {topik} akan {dampak_pos}",
    "{topik} tidak sesuai dengan kebutuhan masyarakat",
    "implementasi {topik} penuh dengan masalah",
    "target {topik} tidak realistis",
    "saya melihat banyak kelemahan dalam program {topik}",
    "{topik} justru memperburuk kondisi yang ada",
    "kebijakan {topik} sarat dengan konflik kepentingan",
    "saya tidak bisa menerima argumen tentang {topik} itu",
    "data menunjukkan program {topik} belum mencapai target",
    "data menunjukkan kebijakan {topik} belum berhasil",
    "laporan menunjukkan {topik} masih jauh dari harapan",
    "fakta di lapangan {topik} belum sesuai ekspektasi",
    "hasil evaluasi {topik} menunjukkan kegagalan",
    "studi menemukan {topik} tidak efektif",
    "penelitian membuktikan {topik} gagal mencapai sasaran",
    "data terbaru menunjukkan {topik} tidak memberikan dampak",
    "survei membuktikan masyarakat kecewa dengan {topik}",
    "angka menunjukkan {topik} belum memenuhi target",
    "bukti empiris menunjukkan {topik} tidak berjalan",
    "statistik membuktikan {topik} masih bermasalah",
    "temuan di lapangan {topik} mengecewakan",
]

_POLICY_NETRAL_TEMPLATES = [
    "kebijakan {topik} memiliki sisi positif dan negatif",
    "perlu data lebih lanjut tentang {topik}",
    "ada dua sisi dari kebijakan {topik}",
    "saya menunggu bukti konkret tentang {topik}",
    "masih terlalu dini menilai {topik}",
    "kedua argumen tentang {topik} sama kuat",
    "kebijakan {topik} perlu dikaji ulang",
    "belum cukup informasi tentang {topik}",
    "baik pendukung maupun penentang {topik} valid",
    "kita perlu objektif melihat data {topik}",
    "evaluasi {topik} perlu dilakukan setelah program berjalan",
    "saya netral dulu soal {topik}",
    "isu {topik} kompleks tidak bisa satu sisi",
    "perlu pertimbangan aspek ekonomi dan sosial {topik}",
    "saya belum memutuskan posisi soal {topik}",
    "data kedua pihak tentang {topik} sama kuat",
    "kebijakan {topik} perlu disempurnakan",
    "saya menghargai upaya pemerintah tapi perlu evaluasi {topik}",
    "kita lihat dulu perkembangan {topik}",
    "saya ingin mendengar pendapat lebih banyak soal {topik}",
    "butuh kajian lebih mendalam tentang {topik}",
    "saya menahan diri belum ambil posisi soal {topik}",
    "debat tentang {topik} masih panjang",
    "saya tunggu implementasi {topik} dulu",
    "kedua belah pihak punya poin valid soal {topik}",
    "belum bisa menyimpulkan dampak {topik}",
    "saya pikir kita perlu diskusi lebih lanjut soal {topik}",
    "argumen pro dan kontra {topik} perlu dipertimbangkan",
    "saya open mind dulu soal {topik}",
    "kita harus melihat gambaran besar {topik} dulu",
]

_PREDIKAT_POSITIF = [
    "mendukung", "setuju dengan", "sepakat dengan",
    "percaya pada", "optimis dengan", "apresiasi",
]
_MANFAAT = [
    "bermanfaat", "sangat membantu", "memberikan dampak positif",
    "memperbaiki ekonomi", "meningkatkan kesejahteraan",
]
_HASIL_POS = [
    "tepat sasaran", "efektif", "berdampak positif",
    "menunjukkan hasil", "memberikan manfaat nyata",
]
_TINDAKAN_POS = [
    "melakukan langkah tepat", "bergerak cepat", "berkomitmen",
    "mengalokasikan dana", "memprioritaskan",
]
_DAMPAK_POS = [
    "meningkatkan kesejahteraan", "mendorong pertumbuhan",
    "memberi manfaat", "memperbaiki sistem",
    "menciptakan lapangan kerja", "mengurangi kesenjangan",
]
_SIFAT_POS = [
    "progresif", "inovatif", "strategis", "tepat", "efisien",
    "berkelanjutan", "inklusif",
]
_DAMPAK_NEG = [
    "merugikan", "memberatkan", "memperburuk",
    "mempersulit", "menimbulkan masalah baru",
    "mengancam kesejahteraan", "memicu konflik",
]
_MASALAH = [
    "merugikan", "memberatkan", "bermasalah",
    "tidak adil", "diskriminatif",
]
_TUJUAN = [
    "mencapai target", "memenuhi harapan",
    "memberikan solusi", "menjawab kebutuhan",
]
_KRITIK_NEG = [
    "menguntungkan elit", "menambah beban rakyat",
    "mengorbankan kepentingan publik", "menjadi ajang korupsi",
]
_TOPIK = [
    "pendidikan", "kesehatan", "ekonomi", "pertahanan",
    "infrastruktur", "pajak", "subsidi", "reformasi birokrasi",
    "digitalisasi", "lingkungan", "energi", "pangan",
    "perumahan", "transportasi", "umkm", "investasi",
    "tenaga kerja", "hukum", "korupsi", "pembangunan",
    "anggaran", "kesejahteraan sosial", "industri", "maritim",
    "pertanian", "pariwisata", "teknologi", "koperasi",
]


def _generate_policy_data(n_per_class: int = 200) -> list[tuple[str, str]]:
    """Generate synthetic policy opinion data using templates."""
    import random
    rng = random.Random(42)

    def _fill(template: str, label: str) -> str:
        kwargs = {}
        if label == "positif":
            kwargs = {
                "predikat": rng.choice(_PREDIKAT_POSITIF),
                "manfaat": rng.choice(_MANFAAT),
                "hasil_pos": rng.choice(_HASIL_POS),
                "tindakan_pos": rng.choice(_TINDAKAN_POS),
                "dampak_pos": rng.choice(_DAMPAK_POS),
                "sifat_pos": rng.choice(_SIFAT_POS),
            }
        elif label == "negatif":
            kwargs = {
                "dampak_neg": rng.choice(_DAMPAK_NEG),
                "masalah": rng.choice(_MASALAH),
                "tujuan": rng.choice(_TUJUAN),
                "kritik_neg": rng.choice(_KRITIK_NEG),
                "dampak_pos": "berhasil",
            }
        kwargs["topik"] = rng.choice(_TOPIK)
        return template.format(**kwargs)

    result: list[tuple[str, str]] = []

    for label, templates in [
        ("positif", _POLICY_POSITIF_TEMPLATES),
        ("negatif", _POLICY_NEGATIF_TEMPLATES),
        ("netral", _POLICY_NETRAL_TEMPLATES),
    ]:
        while len([l for l, _ in result if l == label]) < n_per_class:
            tpl = rng.choice(templates)
            sentence = _fill(tpl, label)
            if sentence and len(sentence) > 10:
                result.append((label, sentence))

    return result


def _load_dataset() -> list[tuple[str, str]]:
    """
    Load dataset: merge SmSA (domain umum) + policy synthetic (domain kebijakan).
    SmSA dari HF → direct URL → pure synthetic jika semua gagal.
    ~600 policy samples selalu ditambahkan untuk coverage domain opini publik.
    """
    policy_data = _generate_policy_data(n_per_class=500)

    data = _load_hf_smsa()
    if len(data) < 100:
        data = _download_smsa()
    if len(data) >= 100:
        # Repeat policy data 5x untuk mengimbangi dominasi SmSA
        policy_weighted = policy_data * 5
        print(f"[sentiment_ml] Pakai SmSA ({len(data)}) + policy {len(policy_data)}x5={len(policy_weighted)}, total {len(data) + len(policy_weighted)}")
        data.extend(policy_weighted)
        return data

    print(f"[sentiment_ml] Hanya pakai policy synthetic ({len(policy_data)} sampel)")
    return policy_data


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

_RE_CLEAN = re.compile(r"[^a-zA-Z0-9\s]")


def _preprocess(text: str) -> str:
    """Bersihkan teks: lowercase, hapus non-alfanumerik (kecuali spasi)."""
    text = text.lower()
    text = _RE_CLEAN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(force: bool = False) -> dict:
    """
    Train atau retrain sentiment classifier.
    Cek dulu apakah model sudah ada; skip jika sudah kecuali force=True.

    Returns:
        {"ok": bool, "n_samples": int, "accuracy": float, "message": str}
    """
    if not _SKLEARN_AVAILABLE:
        return {"ok": False, "message": "scikit-learn tidak terinstall.", "n_samples": 0}

    if MODEL_FILE.exists() and not force:
        return {"ok": True, "message": "Model sudah ada. Gunakan force=True untuk re-train."}

    raw = _load_dataset()
    if not raw:
        return {"ok": False, "message": "Dataset kosong.", "n_samples": 0}

    texts = [_preprocess(t) for _, t in raw]
    labels = [l for l, _ in raw]

    # Train pipeline
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
            # multi_class dihapus — deprecated sejak 1.5, default multinomial di 1.7+
        )),
    ])

    pipeline.fit(texts, labels)
    acc = pipeline.score(texts, labels)

    with _model_lock:
        global _pipeline
        _pipeline = pipeline
        MODEL_FILE.write_bytes(pickle.dumps(pipeline))

    return {
        "ok": True,
        "n_samples": len(raw),
        "accuracy": round(acc, 4),
        "message": f"Model dilatih dari {len(raw)} sampel, akurasi {acc:.1%}",
    }


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _load_model() -> Optional[Pipeline]:
    """Load model from disk if not already in memory."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if MODEL_FILE.exists():
        try:
            with _model_lock:
                _pipeline = pickle.loads(MODEL_FILE.read_bytes())
            return _pipeline
        except Exception as exc:
            print(f"[sentiment_ml] Gagal load model: {exc}")
    return None


def predict(text: str) -> Optional[dict]:
    """
    Prediksi sentimen teks.
    Returns:
        {"label": "positif"|"netral"|"negatif", "skor": float, "confidence": float}
        atau None jika model belum tersedia.
    """
    pipeline = _load_model()
    if pipeline is None:
        return None

    cleaned = _preprocess(text)
    if not cleaned:
        return {"label": "netral", "skor": 0.0, "confidence": 0.0}

    try:
        probs = pipeline.predict_proba([cleaned])[0]
        classes = pipeline.classes_
        pred_idx = probs.argmax()
        label = str(classes[pred_idx])
        confidence = float(probs[pred_idx])

        # Map label
        if label not in _VALID_LABELS:
            label = "netral"

        # Konversi confidence ke skor sentimen (-1..1)
        if label == "positif":
            skor = confidence * 0.8 + 0.2
        elif label == "negatif":
            skor = -(confidence * 0.8 + 0.2)
        else:
            skor = 0.0

        skor = max(-1.0, min(1.0, round(skor, 2)))

        return {"label": label, "skor": skor, "confidence": round(confidence, 3)}

    except Exception as exc:
        print(f"[sentiment_ml] Predict error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Explainability — word-level contribution
# ---------------------------------------------------------------------------

def explain(text: str, top_n: int = 5) -> Optional[dict]:
    """
    Analisis kontribusi kata per kata terhadap prediksi sentimen.

    Returns:
        {
            "text": str,
            "label": "positif"|"netral"|"negatif",
            "confidence": float,
            "contributions": [
                {"kata": str, "kontribusi": float, "arah": "positif"|"netral"|"negatif"},
                ...
            ],
            "top_positive": [{"kata": str, "kontribusi": float}, ...],
            "top_negative": [{"kata": str, "kontribusi": float}, ...],
        }
        atau None jika model belum tersedia.
    """
    pipeline = _load_model()
    if pipeline is None:
        return None

    cleaned = _preprocess(text)
    if not cleaned:
        return None

    try:
        vectorizer = pipeline.named_steps["tfidf"]
        clf = pipeline.named_steps["clf"]
        classes = list(clf.classes_)
        # Pastikan urutan class konsisten: positif, netral, negatif
        label_idx = {lbl: i for i, lbl in enumerate(classes)}

        # Vectorize
        vec = vectorizer.transform([cleaned])
        feature_names = vectorizer.get_feature_names_out()

        # Coefficients per class
        coefs = clf.coef_  # shape (n_classes, n_features)

        # Prediksi
        probs = pipeline.predict_proba([cleaned])[0]
        pred_idx = probs.argmax()
        label = str(classes[pred_idx])
        confidence = float(probs[pred_idx])

        # Tokens yang muncul di teks
        tokens = cleaned.split()
        contributions = []
        for token in tokens:
            # Cari feature index untuk token ini
            matches = [i for i, name in enumerate(feature_names) if name == token]
            if not matches:
                continue
            fi = matches[0]
            # Ambil koefisien untuk class yang diprediksi
            coef_val = float(coefs[pred_idx, fi])
            # TF-IDF value
            tfidf_val = float(vec[0, fi])
            kontribusi = round(coef_val * tfidf_val, 4)

            # Tentukan arah kontribusi
            if label == "positif":
                arah = "positif" if kontribusi > 0 else ("negatif" if kontribusi < 0 else "netral")
            elif label == "negatif":
                arah = "negatif" if kontribusi > 0 else ("positif" if kontribusi < 0 else "netral")
            else:
                arah = "netral"

            contributions.append({
                "kata": token,
                "kontribusi": abs(round(kontribusi, 4)),
                "arah": arah,
            })

        # Sort by absolute contribution
        contributions.sort(key=lambda x: x["kontribusi"], reverse=True)

        # Top positive/negative contributors
        top_pos = [c for c in contributions if c["arah"] == "positif"][:top_n]
        top_neg = [c for c in contributions if c["arah"] == "negatif"][:top_n]

        return {
            "text": text,
            "label": label,
            "confidence": round(confidence, 3),
            "contributions": contributions[:top_n * 2],
            "top_positive": top_pos,
            "top_negative": top_neg,
        }

    except Exception as exc:
        print(f"[sentiment_ml] Explain error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Check whether a trained model is available."""
    if not _SKLEARN_AVAILABLE:
        return False
    if _pipeline is not None:
        return True
    return MODEL_FILE.exists()


def get_status() -> dict:
    """Return status info."""
    return {
        "sklearn_available": _SKLEARN_AVAILABLE,
        "model_exists": MODEL_FILE.exists(),
        "model_loaded": _pipeline is not None,
        "dataset_source": "huggingface+policy" if _load_hf_smsa() else "policy_only",
        "model_file": str(MODEL_FILE),
        "policy_samples": 1500,
    }


# ---------------------------------------------------------------------------
# Metrics — confusion matrix & per-class evaluation
# ---------------------------------------------------------------------------

_CLASS_ORDER = ["positif", "netral", "negatif"]

def get_metrics() -> dict:
    """
    Evaluasi performa model sentimen (TF-IDF + LogisticRegression).

    Compute confusion matrix 3x3, precision/recall/F1 per kelas
    pada dataset training (SmSA + policy synthetic).

    Returns dict (sama format dengan ml_pipeline.get_ml_metrics untuk
    konsistensi frontend):
        {
            "ok": bool,
            "message": str,
            "n_samples": int,
            "classes": ["positif", "netral", "negatif"],
            "accuracy": float,
            "accuracy_pct": int,
            "confusion_matrix": [[int]],
            "per_class": {kelas: {"precision": float, "recall": float, "f1": float, "support": int}},
            "macro_avg": {"precision": float, "recall": float, "f1": float},
            "weighted_avg": {"precision": float, "recall": float, "f1": float},
            "training_accuracy": float,
            "note": str,
        }
    """
    if not _SKLEARN_AVAILABLE:
        return {"ok": False, "message": "scikit-learn tidak terinstall."}

    pipeline = _load_model()
    if pipeline is None:
        return {"ok": False, "message": "Model belum dilatih."}

    try:
        # Load dataset (sama seperti training)
        raw = _load_dataset()
        if not raw:
            return {"ok": False, "message": "Dataset kosong.", "n_samples": 0}

        texts = [_preprocess(t) for _, t in raw]
        labels_true = [l for l, _ in raw]

        # Predict
        labels_pred = pipeline.predict(texts)

        n = len(raw)
        acc = pipeline.score(texts, labels_true)

        # Confusion matrix — urut sesuai _CLASS_ORDER
        cm = confusion_matrix(labels_true, labels_pred, labels=_CLASS_ORDER).tolist()

        # Per-class metrics
        precision_arr, recall_arr, f1_arr, support_arr = precision_recall_fscore_support(
            labels_true, labels_pred,
            labels=_CLASS_ORDER,
            zero_division=0,
        )

        per_class = {}
        for i, kelas in enumerate(_CLASS_ORDER):
            per_class[kelas] = {
                "precision": round(float(precision_arr[i]), 4),
                "recall":    round(float(recall_arr[i]),    4),
                "f1":        round(float(f1_arr[i]),        4),
                "support":   int(support_arr[i]),
            }

        # Macro & weighted averages
        macro_p, macro_r, macro_f, _ = precision_recall_fscore_support(
            labels_true, labels_pred, average="macro", zero_division=0
        )
        weight_p, weight_r, weight_f, _ = precision_recall_fscore_support(
            labels_true, labels_pred, average="weighted", zero_division=0
        )

        return {
            "ok":               True,
            "message":          "Evaluasi model sentimen berhasil.",
            "n_samples":        n,
            "classes":          _CLASS_ORDER,
            "accuracy":         round(float(acc), 4),
            "accuracy_pct":     round(float(acc) * 100),
            "confusion_matrix": cm,
            "per_class":        per_class,
            "macro_avg": {
                "precision": round(float(macro_p), 4),
                "recall":    round(float(macro_r), 4),
                "f1":        round(float(macro_f), 4),
            },
            "weighted_avg": {
                "precision": round(float(weight_p), 4),
                "recall":    round(float(weight_r), 4),
                "f1":        round(float(weight_f), 4),
            },
            "training_accuracy": round(float(acc), 4),
            "note": (
                "Evaluasi pada dataset training yang sama (bukan hold-out). "
                "Angka ini optimistis — akurasi di dunia nyata mungkin lebih rendah."
            ),
        }

    except Exception as exc:
        return {"ok": False, "message": f"Evaluasi gagal: {exc}"}


# ---------------------------------------------------------------------------
# Auto-train on import (if model missing)
# ---------------------------------------------------------------------------

def _auto_init():
    if not _SKLEARN_AVAILABLE:
        return
    if is_available():
        return
    print("[sentiment_ml] Model belum ada — auto-training...")
    result = train()
    print(f"[sentiment_ml] {result['message']}")


_auto_init()
