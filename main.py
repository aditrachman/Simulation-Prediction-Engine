# main.py
# Upgraded: endpoint baru untuk simulasi multi-ronde, God's Eye intervention,
# data graf untuk visualisasi frontend, dan dukungan agen custom dari frontend.

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from backend.agents import get_agents, get_all_categories
from backend.engine import run_simulation, call_llm, call_llm_json, score_sentiment, MODEL_AGENT, MODEL_ANALYSIS
from backend.scraper import ambil_konteks_real
from backend.social_engine import run_social_simulation

app = FastAPI(
    title="VoxSwarm API",
    description=(
        "Simulation-Prediction-Engine dengan multi-agen, multi-ronde, "
        "mode debat, mode sosmed, data real (RSS+Reddit), "
        "God\'s Eye intervention, dan agen custom dari frontend."
    ),
    version="3.0.0",
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

RATE_LIMIT_WINDOW_SEC  = int(os.getenv("RATE_LIMIT_WINDOW_SEC",  "60"))
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
    # ← BARU: list agen custom dari frontend (opsional)
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
    return {
        "message": "Mini-Social-Swarm API v2.1 is Running",
        "fitur": [
            "Multi-agen multi-ronde",
            "Persistent agent memory",
            "GraphRAG-lite entity extraction",
            "God's Eye intervention (post-simulasi)",
            "Sentiment scoring",
            "Agen custom dari frontend",  # ← baru
        ],
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
    """
    _enforce_rate_limit(request)

    # Sanitasi topik
    topik_bersih = payload.topik.strip()
    if not topik_bersih:
        raise HTTPException(status_code=400, detail="Topik tidak boleh kosong.")
    _validate_text(topik_bersih, "Topik")

    # Sanitasi intervensi
    if payload.intervensi:
        intervensi_bersih = payload.intervensi.strip() or None
        if intervensi_bersih:
            _validate_text(intervensi_bersih, "Intervensi")
    else:
        intervensi_bersih = None

    # Sanitasi & konversi agen custom
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

    # Ambil daftar agen (bawaan + custom)
    daftar_agen = get_agents(payload.kategori, agen_custom=agen_custom_dict)
    if not daftar_agen:
        raise HTTPException(
            status_code=400,
            detail=f"Kategori '{payload.kategori}' tidak dikenali. Gunakan: {get_all_categories()}",
        )

    # Ambil data real (RSS + Reddit) secara paralel
    konteks_real = ambil_konteks_real(topik_bersih)

    # Jalankan simulasi debat
    hasil = run_simulation(
        topik=topik_bersih,
        agents=daftar_agen,
        jumlah_ronde=payload.jumlah_ronde,
        intervensi=intervensi_bersih,
        briefing_real=konteks_real.get("briefing", ""),
    )

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

    # Ambil data real paralel dengan persiapan agen
    konteks_real = ambil_konteks_real(topik_bersih)

    # Jalankan simulasi sosmed
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
        "status":  "success",
        "topik":   topik_bersih,
        "berita":  konteks["berita"],
        "reddit":  konteks["reddit"],
        "total":   konteks["total"],
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