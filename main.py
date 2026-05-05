# main.py
# Upgraded: endpoint baru untuk simulasi multi-ronde, God's Eye intervention,
# data graf untuk visualisasi frontend, dukungan agen custom dari frontend,
# ML Prediction Layer (v3.1), dan Feedback Loop / Ground Truth (v3.2).

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, Optional

from backend.agents import get_agents, get_all_categories
from backend.engine import run_simulation, call_llm, call_llm_json, score_sentiment, MODEL_AGENT, MODEL_ANALYSIS
from backend.scraper import ambil_konteks_real, get_cache_stats, clear_context_cache
from backend.social_engine import run_social_simulation
from backend.ml_pipeline import load_or_predict, get_ml_status, get_ml_metrics, train_model, build_feature_row_from_social
from backend.feedback import submit_feedback, submit_feedback_by_hash, get_feedback_stats, FeedbackValidationError

app = FastAPI(
    title="VoxSwarm API",
    description=(
        "Simulation-Prediction-Engine dengan multi-agen, multi-ronde, "
        "mode debat, mode sosmed, data real (RSS+Reddit), "
        "God's Eye intervention, agen custom dari frontend, "
        "ML Prediction Layer, dan Feedback Loop."
    ),
    version="3.2.0",
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def _parse_origins() -> list[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_WINDOW_SEC   = int(os.getenv("RATE_LIMIT_WINDOW_SEC",  "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "8"))
MAX_TOPIC_LENGTH        = int(os.getenv("MAX_TOPIC_LENGTH",        "300"))

_rate_limit_state: dict[str, deque] = defaultdict(deque)
_rate_limit_lock = threading.Lock()

BLOCKED_PATTERNS = ("<script", "javascript:", "onerror=", "onload=", "data:")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request):
    ip  = _client_ip(request)
    now = time.time()
    with _rate_limit_lock:
        q = _rate_limit_state[ip]
        while q and now - q[0] > RATE_LIMIT_WINDOW_SEC:
            q.popleft()
        if len(q) >= RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Terlalu banyak permintaan. Silakan tunggu sebentar.",
            )
        q.append(now)


def _validate_text(text: str, field_name: str = "Input"):
    """Validasi teks dari XSS dan input tidak valid."""
    lowered = text.lower()
    if any(token in lowered for token in BLOCKED_PATTERNS):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} mengandung karakter tidak valid.",
        )


# ---------------------------------------------------------------------------
# Model: Agen Custom (dari frontend)
# ---------------------------------------------------------------------------

class AgenCustomModel(BaseModel):
    nama:        str   = Field(..., min_length=1, max_length=80,  description="Nama peran agen")
    role:        str   = Field(..., min_length=5, max_length=500, description="Deskripsi karakter dan sudut pandang")
    pengaruh:    float = Field(default=0.7, ge=0.1, le=1.0,       description="Bobot pengaruh agen (0.1–1.0)")
    kepribadian: dict  = Field(default_factory=lambda: {"openness": 0.6, "agreeableness": 0.6, "neuroticism": 0.4})


# ---------------------------------------------------------------------------
# Model: Feedback Ground Truth
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    topik: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=500,
        description=(
            "Topik simulasi yang di-feedback. "
            "Wajib jika topik_hash tidak disertakan. "
            "Jika topik_hash tersedia (dari response /start-simulation), "
            "gunakan topik_hash saja — lebih aman dan tidak bisa mismatch."
        ),
        examples=["Kenaikan harga BBM bersubsidi"],
    )
    topik_hash: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=16,
        description=(
            "Hash topik 16-karakter dari response /start-simulation (data.topik_hash). "
            "Jika disertakan, field 'topik' diabaikan — hash langsung dipakai sebagai FK. "
            "Ini mencegah mismatch akibat typo atau perbedaan whitespace."
        ),
        examples=["a3f9c12e4b78d501"],
    )
    label_aktual: Literal["Konsensus", "Polarisasi", "Status Quo"] = Field(
        ...,
        description="Ground truth outcome yang diamati: Konsensus | Polarisasi | Status Quo",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Tingkat keyakinan operator terhadap label ini (0.0–1.0). Default 1.0.",
    )
    catatan: str = Field(
        default="",
        max_length=1000,
        description="Catatan tambahan dari operator (opsional).",
    )


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class SimRequest(BaseModel):
    topik: str = Field(
        ...,
        min_length=3,
        max_length=MAX_TOPIC_LENGTH,
        description="Topik / isu yang akan disimulasikan",
        examples=["Kenaikan harga BBM bersubsidi"],
    )
    kategori: str = Field(
        default="Umum",
        max_length=50,
        description="Kategori simulasi: Umum, Ekonomi, Politik, Sosial, Hukum, Teknologi",
    )
    jumlah_ronde: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Jumlah ronde diskusi (1–5)",
    )
    intervensi: Optional[str] = Field(
        default=None,
        max_length=200,
        description=(
            "[God's Eye] Variabel eksternal yang diinjeksikan di tengah simulasi, "
            "misal: 'Pemerintah tiba-tiba umumkan subsidi baru'."
        ),
    )
    agen_custom: Optional[list[AgenCustomModel]] = Field(
        default=None,
        max_length=5,
        description="Daftar agen tambahan yang didefinisikan pengguna (maks 5 agen custom).",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def home():
    ml = get_ml_status()
    fb = get_feedback_stats()
    return {
        "message": "VoxSwarm API v3.2 is Running",
        "fitur": [
            "Multi-agen multi-ronde",
            "Persistent agent memory",
            "GraphRAG-lite entity extraction",
            "God's Eye intervention",
            "Sentiment scoring",
            "Agen custom dari frontend",
            "ML Prediction Layer",
            "Feedback Loop & Ground Truth",
        ],
        "ml_status": {
            "active":          ml["ml_active"],
            "n_samples":       ml["n_samples"],
            "n_feedback":      ml["n_feedback"],
            "samples_needed":  ml["samples_needed"],
        },
        "feedback_status": {
            "total":           fb["total"],
            "ready_to_retrain": fb["ready_to_retrain"],
        },
    }


@app.get("/categories", tags=["Meta"])
def list_categories():
    """Kembalikan daftar kategori simulasi yang tersedia."""
    return {"kategori": get_all_categories()}


@app.post("/start-simulation", tags=["Simulation"])
def start_sim(payload: SimRequest, request: Request):
    """
    Mulai simulasi multi-agen multi-ronde.

    - **topik**: Isu utama diskusi.
    - **kategori**: Filter agen yang relevan.
    - **jumlah_ronde**: Berapa kali siklus diskusi (1–5).
    - **intervensi**: (Opsional) Skenario "bagaimana jika" yang diinjeksikan di ronde tengah.
    - **agen_custom**: (Opsional) Daftar agen tambahan yang didefinisikan oleh pengguna.

    Field tambahan di response:
    - `data.prediksi_source`: "ml" jika prediksi dari model, "rule_based" jika fallback.
    - `data.ml_info`: detail status ML (n_samples, note).
    """
    _enforce_rate_limit(request)

    topik_bersih = payload.topik.strip()
    if not topik_bersih:
        raise HTTPException(status_code=400, detail="Topik tidak boleh kosong.")
    _validate_text(topik_bersih, "Topik")

    if payload.intervensi:
        intervensi_bersih = payload.intervensi.strip() or None
        if intervensi_bersih:
            _validate_text(intervensi_bersih, "Intervensi")
    else:
        intervensi_bersih = None

    agen_custom_dict: list[dict] | None = None
    if payload.agen_custom:
        agen_custom_dict = []
        for ac in payload.agen_custom:
            nama_ac = ac.nama.strip()
            role_ac = ac.role.strip()
            _validate_text(nama_ac, "Nama agen custom")
            _validate_text(role_ac, "Role agen custom")
            agen_custom_dict.append({
                "nama":        nama_ac,
                "role":        role_ac,
                "pengaruh":    ac.pengaruh,
                "kepribadian": ac.kepribadian,
            })

    daftar_agen = get_agents(payload.kategori, agen_custom=agen_custom_dict)
    if not daftar_agen:
        raise HTTPException(
            status_code=400,
            detail=f"Kategori '{payload.kategori}' tidak dikenali. Gunakan: {get_all_categories()}",
        )

    konteks_real = ambil_konteks_real(topik_bersih)

    hasil = run_simulation(
        topik=topik_bersih,
        agents=daftar_agen,
        jumlah_ronde=payload.jumlah_ronde,
        intervensi=intervensi_bersih,
        briefing_real=konteks_real.get("briefing", ""),
    )

    # ── ML Layer: append history + prediksi (fallback otomatis ke rule-based) ──
    ml_result = load_or_predict(hasil, konteks_real)

    if ml_result["source"] == "ml":
        hasil["prediksi"] = ml_result["prediksi"]

    hasil["prediksi_source"] = ml_result["source"]
    hasil["ml_info"] = {
        "source":        ml_result["source"],
        "n_samples":     ml_result["n_samples"],
        "note":          ml_result.get("note", ""),
    }
    # ── Expose topik_hash agar frontend bisa kirim langsung ke POST /feedback ─
    # tanpa harus mengirim ulang plain-text topik (menghindari mismatch hash)
    hasil["topik_hash"] = ml_result.get("topik_hash", "")
    # ──────────────────────────────────────────────────────────────────────────

    return {
        "status": "success",
        "data":   hasil,
        "konteks_real": {
            "total_sumber": konteks_real.get("total", 0),
            "berita":       konteks_real.get("berita", [])[:5],
            "reddit":       konteks_real.get("reddit", [])[:5],
            "timestamp":    konteks_real.get("timestamp", ""),
        },
    }


# ---------------------------------------------------------------------------
# Model: Simulasi Sosmed
# ---------------------------------------------------------------------------

class SosmedRequest(BaseModel):
    topik: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="Topik / isu yang akan disimulasikan di sosmed",
    )
    kategori: str = Field(
        default="Umum",
        max_length=50,
        description="Kategori simulasi untuk pemilihan agen",
    )
    jumlah_tick: int = Field(
        default=5,
        ge=2,
        le=10,
        description="Jumlah 'momen' sosmed — seperti ronde tapi lebih cair (2–10)",
    )
    intervensi: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Breaking news / skenario yang diinjeksikan di tengah simulasi sosmed",
    )
    agen_custom: Optional[list[AgenCustomModel]] = Field(
        default=None,
        max_length=5,
        description="Agen tambahan yang didefinisikan pengguna (maks 5)",
    )


@app.post("/start-social", tags=["Simulation"])
def start_social(payload: SosmedRequest, request: Request):
    """
    Jalankan simulasi SOSIAL MEDIA multi-agen.

    Setiap agen punya akun sendiri dan bisa:
    - POST — buat konten baru
    - LIKE — like post orang lain
    - REPLY — balas langsung
    - QUOTE — quote tweet dengan komentar
    - FOLLOW — follow agen lain
    - DIAM — skip giliran

    Data real dari RSS berita + Reddit dipakai sebagai konteks.
    Agen otoritas (pemerintah) otomatis merespons konten viral.
    """
    _enforce_rate_limit(request)

    topik_bersih = payload.topik.strip()
    if not topik_bersih:
        raise HTTPException(status_code=400, detail="Topik tidak boleh kosong.")
    _validate_text(topik_bersih, "Topik")

    intervensi_bersih = None
    if payload.intervensi:
        intervensi_bersih = payload.intervensi.strip() or None
        if intervensi_bersih:
            _validate_text(intervensi_bersih, "Intervensi")

    agen_custom_dict = None
    if payload.agen_custom:
        agen_custom_dict = []
        for ac in payload.agen_custom:
            nama_ac = ac.nama.strip()
            role_ac = ac.role.strip()
            _validate_text(nama_ac, "Nama agen custom")
            _validate_text(role_ac, "Role agen custom")
            agen_custom_dict.append({
                "nama": nama_ac, "role": role_ac,
                "pengaruh": ac.pengaruh, "kepribadian": ac.kepribadian,
            })

    daftar_agen = get_agents(payload.kategori, agen_custom=agen_custom_dict)
    if not daftar_agen:
        raise HTTPException(
            status_code=400,
            detail=f"Kategori '{payload.kategori}' tidak dikenali.",
        )

    konteks_real = ambil_konteks_real(topik_bersih)

    hasil = run_social_simulation(
        topik=topik_bersih,
        agents=daftar_agen,
        konteks_real=konteks_real,
        jumlah_tick=payload.jumlah_tick,
        intervensi=intervensi_bersih,
        call_llm_fn=call_llm,
        call_llm_json_fn=call_llm_json,
        score_sentiment_fn=score_sentiment,
        model_agent=MODEL_AGENT,
        model_analysis=MODEL_ANALYSIS,
    )

    # ── ML Layer: convert sosmed output → feature row → history + prediksi ──
    social_feat = build_feature_row_from_social(hasil, konteks_real)
    ml_result   = load_or_predict(social_feat, konteks_real, prebuilt=True)
    hasil["prediksi_source"] = ml_result["source"]
    hasil["ml_info"] = {
        "source":    ml_result["source"],
        "n_samples": ml_result["n_samples"],
        "note":      ml_result.get("note", ""),
    }
    hasil["topik_hash"] = ml_result.get("topik_hash", "")
    # ─────────────────────────────────────────────────────────────────────────

    return {
        "status": "success",
        "data":   hasil,
    }


@app.get("/fetch-context", tags=["Data Real"])
def fetch_context(topik: str, request: Request):
    """
    Ambil data real (berita + Reddit) untuk topik tertentu tanpa menjalankan simulasi.
    Berguna untuk preview konteks sebelum simulasi dimulai.
    """
    _enforce_rate_limit(request)
    topik_bersih = topik.strip()[:300]
    if not topik_bersih:
        raise HTTPException(status_code=400, detail="Topik tidak boleh kosong.")
    _validate_text(topik_bersih, "Topik")

    konteks = ambil_konteks_real(topik_bersih)
    return {
        "status":    "success",
        "topik":     topik_bersih,
        "berita":    konteks["berita"],
        "reddit":    konteks["reddit"],
        "total":     konteks["total"],
        "timestamp": konteks["timestamp"],
    }


@app.post("/extract-graph", tags=["GraphRAG"])
def extract_graph(payload: SimRequest, request: Request):
    """
    Endpoint khusus untuk ekstraksi graf entitas & relasi dari topik tertentu,
    tanpa menjalankan simulasi penuh.
    """
    _enforce_rate_limit(request)

    from backend.engine import extract_entities, call_llm

    topik_bersih = payload.topik.strip()
    if not topik_bersih:
        raise HTTPException(status_code=400, detail="Topik tidak boleh kosong.")
    _validate_text(topik_bersih, "Topik")

    ringkasan = call_llm(
        "Kamu asisten analitik. Berikan gambaran singkat berbagai perspektif terhadap isu ini dalam 3-4 kalimat.",
        f"Isu: {topik_bersih}",
        max_tokens=250,
    )
    graf = extract_entities(topik_bersih, ringkasan)

    return {
        "status":    "success",
        "topik":     topik_bersih,
        "graf_data": graf,
    }


# ---------------------------------------------------------------------------
# Cache Endpoints
# ---------------------------------------------------------------------------

@app.get("/cache-status", tags=["Cache"])
def cache_status(request: Request):
    """
    Info cache konteks real: jumlah entri, valid vs expired, TTL, path file.
    """
    _enforce_rate_limit(request)
    return {"status": "success", "cache": get_cache_stats()}


@app.post("/cache-clear", tags=["Cache"])
def cache_clear(request: Request, topik: Optional[str] = None):
    """
    Hapus cache konteks real.
    - Tanpa parameter -> hapus semua entri.
    - ?topik=xxx      -> hapus hanya topik itu.
    """
    _enforce_rate_limit(request)
    n = clear_context_cache(topik)
    return {
        "status":  "success",
        "cleared": n,
        "scope":   topik if topik else "all",
    }


# ---------------------------------------------------------------------------
# ML Endpoints
# ---------------------------------------------------------------------------

@app.get("/ml-status", tags=["ML"])
def ml_status(request: Request):
    """
    Status ML pipeline: jumlah data terkumpul, apakah model sudah aktif,
    berapa sampel lagi yang dibutuhkan, dan berapa label dari feedback.
    Termasuk path HISTORY_FILE untuk debugging lokasi file.
    """
    _enforce_rate_limit(request)
    from backend.ml_pipeline import DATA_DIR, HISTORY_FILE, MODEL_FILE
    status = get_ml_status()
    status["debug_paths"] = {
        "data_dir":       str(DATA_DIR),
        "history_file":   str(HISTORY_FILE),
        "history_exists": HISTORY_FILE.exists(),
        "model_file":     str(MODEL_FILE),
        "model_exists":   MODEL_FILE.exists(),
    }
    return {"status": "success", "ml": status}


@app.post("/ml-train", tags=["ML"])
def ml_train(request: Request):
    """
    Trigger manual re-training model dari dataset merged (history + feedback).
    Gunakan setelah data cukup (>= ML_MIN_SAMPLES simulasi),
    atau untuk refresh model setelah akumulasi feedback baru yang signifikan.
    """
    _enforce_rate_limit(request)
    result = train_model(force=True)
    return {
        "status": "success" if result.get("ok") else "error",
        "result": result,
    }


# ---------------------------------------------------------------------------
# Feedback Endpoints
# ---------------------------------------------------------------------------

@app.post("/feedback", tags=["Feedback"])
def submit_feedback_endpoint(payload: FeedbackRequest, request: Request):
    """
    Kirim feedback ground truth untuk topik yang sudah disimulasikan.

    **Cara terbaik (hash-first)**: ambil `data.topik_hash` dari response
    `/start-simulation`, lalu kirim langsung sebagai `topik_hash`.
    Field `topik` bisa diabaikan — tidak akan terjadi mismatch.

    **Fallback (plain text)**: kirim `topik` sebagai plain text (sama persis
    dengan saat simulasi). Jika ada perbedaan whitespace/kapitalisasi,
    hash akan beda dan feedback tidak terhubung ke history row yang benar.

    Label feedback akan menggantikan weak label (rule-based) saat model ML
    di-train ulang. Jika total feedback sudah >= 5, auto re-train
    dipicu otomatis di background thread (non-blocking).
    """
    _enforce_rate_limit(request)

    # ── Validasi: salah satu dari topik atau topik_hash wajib ada ──────────
    if not payload.topik_hash and not payload.topik:
        raise HTTPException(
            status_code=400,
            detail="Wajib menyertakan 'topik_hash' (dari response /start-simulation) atau 'topik'.",
        )

    if payload.catatan:
        _validate_text(payload.catatan, "Catatan")

    # ── Pilih mode: hash-first atau plain-text fallback ────────────────────
    if payload.topik_hash:
        # Hash-first: tidak perlu hashing ulang, tidak bisa mismatch
        try:
            result = submit_feedback_by_hash(
                topik_hash   = payload.topik_hash,
                label_aktual = payload.label_aktual,
                confidence   = payload.confidence,
                catatan      = payload.catatan,
            )
        except FeedbackValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
        topik_display = f"[hash:{payload.topik_hash}]"
    else:
        # Plain-text fallback
        _validate_text(payload.topik, "Topik")
        try:
            result = submit_feedback(
                topik        = payload.topik,
                label_aktual = payload.label_aktual,
                confidence   = payload.confidence,
                catatan      = payload.catatan,
            )
        except FeedbackValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
        topik_display = payload.topik[:80]

    action_str = "diperbarui" if result["action"] == "updated" else "ditambahkan"
    return {
        "status":  "success",
        "message": (
            f"Feedback {action_str}: label '{result['label_aktual']}' "
            f"untuk topik '{topik_display}'."
        ),
        "data": {
            "topik_hash":        result["topik_hash"],
            "label_aktual":      result["label_aktual"],
            "confidence":        result["confidence"],
            "timestamp":         result["timestamp"],
            "action":            result["action"],
            "total_feedback":    result["total_feedback"],
            "retrain_triggered": result["retrain_triggered"],
        },
    }


@app.get("/ml-debug", tags=["ML"])
def ml_debug(request: Request):
    """
    Diagnostik lengkap ML pipeline:
    distribusi label, fitur paling berpengaruh, tanda-tanda overfitting,
    dan peringatan imbalance data. Berguna setelah generate_dummy_data.py dijalankan.
    """
    _enforce_rate_limit(request)
    from backend.ml_pipeline import (
        build_training_dataset, FEATURE_COLS,
        MODEL_FILE, _model_lock,
    )
    import pickle

    dataset = build_training_dataset()
    label_counts:  dict = {}
    source_counts: dict = {"weak": 0, "feedback": 0, "dummy": 0}
    for row in dataset:
        lbl = row.get("label", "?")
        src = "dummy" if row.get("_source") == "dummy" else row.get("label_source", "weak")
        label_counts[lbl]  = label_counts.get(lbl, 0) + 1
        source_counts[src] = source_counts.get(src, 0) + 1

    total     = len(dataset) or 1
    label_pct = {k: round(v / total * 100, 1) for k, v in label_counts.items()}
    dominant  = max(label_counts, key=label_counts.get) if label_counts else None
    imbalance_warning = (
        label_counts.get(dominant, 0) / total > 0.7 if dominant else False
    )

    feature_importance: list = []
    if MODEL_FILE.exists():
        try:
            with _model_lock:
                clf = pickle.loads(MODEL_FILE.read_bytes())
            fi = sorted(zip(FEATURE_COLS, clf.feature_importances_), key=lambda x: -x[1])
            feature_importance = [
                {"feature": f, "importance": round(float(i), 4)} for f, i in fi[:10]
            ]
        except Exception as e:
            feature_importance = [{"error": str(e)}]

    return {
        "status":              "success",
        "n_total":             len(dataset),
        "label_distribution":  label_counts,
        "label_pct":           label_pct,
        "source_distribution": source_counts,
        "dominant_label":      dominant,
        "imbalance_warning":   imbalance_warning,
        "top10_features":      feature_importance,
        "overfitting_risk":    (
            "HIGH"   if len(dataset) < 20 else
            "MEDIUM" if len(dataset) < 50 else
            "LOW"
        ),
    }


@app.get("/feedback-stats", tags=["Feedback"])
def feedback_stats_endpoint(request: Request):
    """
    Statistik ringkasan feedback ground truth yang terkumpul.

    Response mencakup:
    - **total**: jumlah feedback yang tersimpan
    - **by_label**: distribusi per label (Konsensus / Polarisasi / Status Quo)
    - **avg_confidence**: rata-rata keyakinan operator
    - **latest_timestamp**: waktu feedback terakhir masuk
    - **ready_to_retrain**: apakah sudah cukup feedback untuk trigger re-train
    """
    _enforce_rate_limit(request)
    stats = get_feedback_stats()
    return {
        "status":   "success",
        "feedback": stats,
    }


# ---------------------------------------------------------------------------
# Observability & Export Endpoints
# ---------------------------------------------------------------------------

@app.get("/feedback-export", tags=["Observability"])
def feedback_export(request: Request):
    """
    Download seluruh isi feedback.jsonl sebagai JSON array.

    Berguna untuk:
    - Audit label yang masuk dari operator
    - Fine-tuning manual di luar sistem
    - Backup sebelum re-train besar

    Tidak mengekspos data sensitif — hanya topik_hash + label + confidence + timestamp.
    """
    _enforce_rate_limit(request)
    from backend.feedback import _load_all_feedback, _feedback_lock, FEEDBACK_FILE
    with _feedback_lock:
        rows = _load_all_feedback()

    return {
        "status":         "success",
        "total":          len(rows),
        "feedback_file":  str(FEEDBACK_FILE),
        "rows":           rows,
    }


@app.get("/ml-dataset-stats", tags=["Observability"])
def ml_dataset_stats(request: Request):
    """
    Statistik lengkap dataset training ML (merged history + feedback).

    Mencakup:
    - **n_history**: jumlah baris di simulation_history.jsonl
    - **n_feedback_matched**: jumlah baris yang label-nya di-override oleh feedback
    - **label_distribution**: distribusi label di dataset merged (termasuk sumber: weak vs feedback)
    - **feature_importance**: importance score tiap fitur dari model aktif (jika sudah dilatih)
    - **drift_summary**: perbandingan prediksi rata-rata 10 simulasi pertama vs 10 terakhir
      (deteksi apakah ada pergeseran pola yang signifikan)
    """
    _enforce_rate_limit(request)
    from backend.ml_pipeline import (
        build_training_dataset, _load_history, FEATURE_COLS,
        MODEL_FILE, ENCODER_FILE, _model_lock,
    )
    import pickle

    history  = _load_history()
    dataset  = build_training_dataset()

    # ── Label distribution ──────────────────────────────────────────────────
    label_dist: dict[str, dict[str, int]] = {
        "feedback": {"Konsensus": 0, "Polarisasi": 0, "Status Quo": 0},
        "weak":     {"Konsensus": 0, "Polarisasi": 0, "Status Quo": 0},
    }
    for row in dataset:
        src = row.get("label_source", "weak")
        lbl = row.get("label", "Status Quo")
        bucket = label_dist.get(src, label_dist["weak"])
        bucket[lbl] = bucket.get(lbl, 0) + 1

    # ── Feature importance ──────────────────────────────────────────────────
    feature_importance: list[dict] = []
    if MODEL_FILE.exists() and ENCODER_FILE.exists():
        try:
            with _model_lock:
                clf = pickle.loads(MODEL_FILE.read_bytes())
            importances = clf.feature_importances_
            fi_pairs = sorted(
                zip(FEATURE_COLS, importances),
                key=lambda x: -x[1],
            )
            feature_importance = [
                {"feature": feat, "importance": round(float(imp), 5)}
                for feat, imp in fi_pairs
            ]
        except Exception as e:
            feature_importance = [{"error": str(e)}]

    # ── Drift summary: 10 awal vs 10 akhir ─────────────────────────────────
    drift_summary: dict = {}
    if len(history) >= 20:
        def _label_counts(rows: list) -> dict:
            counts: dict[str, int] = {}
            for r in rows:
                lbl = r.get("label", "Status Quo")
                counts[lbl] = counts.get(lbl, 0) + 1
            return counts

        early = history[:10]
        late  = history[-10:]
        drift_summary = {
            "early_10":      _label_counts(early),
            "late_10":       _label_counts(late),
            "mean_sent_early": round(sum(r.get("mean_sent", 0) for r in early) / 10, 4),
            "mean_sent_late":  round(sum(r.get("mean_sent", 0) for r in late)  / 10, 4),
            "note": (
                "Bandingkan distribusi early vs late untuk deteksi drift. "
                "Perbedaan besar di label dominan menandakan pergeseran pola diskusi."
            ),
        }
    else:
        drift_summary = {"note": f"Butuh minimal 20 baris history untuk drift analysis. Saat ini: {len(history)}."}

    return {
        "status":              "success",
        "n_history":           len(history),
        "n_dataset_merged":    len(dataset),
        "n_feedback_matched":  sum(1 for r in dataset if r.get("label_source") == "feedback"),
        "n_weak_label":        sum(1 for r in dataset if r.get("label_source") == "weak"),
        "label_distribution":  label_dist,
        "feature_importance":  feature_importance,
        "model_active":        MODEL_FILE.exists(),
        "drift_summary":       drift_summary,
        "feature_cols":        FEATURE_COLS,
    }


@app.get("/ml-retrain-check", tags=["ML"])
def manual_train(request: Request):
    """
    Cek dan trigger training jika data sudah >= MIN_SAMPLES.
    Berguna jika auto-train tidak terpicu atau ingin memaksa re-train.
    Gunakan POST /ml-train untuk force re-train tanpa pengecekan threshold.
    """
    _enforce_rate_limit(request)
    from backend.ml_pipeline import force_train_if_ready
    result = force_train_if_ready()
    return {"ok": result.get("ok"), "data": result, "message": result.get("message", "")}


@app.get("/ml-metrics", tags=["ML"])
def ml_metrics(request: Request):
    """
    Evaluasi performa model ML: akurasi, confusion matrix, precision/recall/F1
    per kelas. Menggunakan 5-fold cross-validation jika data cukup (>= 20 baris),
    fallback ke train=test jika data kurang.

    Response:
    - **accuracy** / **accuracy_pct**: akurasi keseluruhan
    - **confusion_matrix**: matriks 3×3 (baris = aktual, kolom = prediksi)
    - **per_class**: precision, recall, F1-score, support per kelas
    - **macro_avg** / **weighted_avg**: rata-rata lintas kelas
    - **eval_method**: metode evaluasi yang digunakan
    - **n_feedback_labels**: jumlah sampel dengan label manual dari operator
    """
    _enforce_rate_limit(request)
    metrics = get_ml_metrics()
    return {
        "status":  "success" if metrics.get("ok") else "error",
        "metrics": metrics,
    }