import os
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agents import get_agents
from backend.engine import run_simulation

app = FastAPI()


def _parse_origins():
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "8"))
MAX_TOPIC_LENGTH = int(os.getenv("MAX_TOPIC_LENGTH", "200"))

_rate_limit_state = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request):
    ip = _client_ip(request)
    now = time.time()

    with _rate_limit_lock:
        q = _rate_limit_state[ip]
        while q and now - q[0] > RATE_LIMIT_WINDOW_SEC:
            q.popleft()

        if len(q) >= RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait and try again.",
            )
        q.append(now)


class SimRequest(BaseModel):
    topik: str = Field(
        ...,
        min_length=3,
        max_length=MAX_TOPIC_LENGTH,
        description="Simulation topic seed",
    )
    kategori: str = Field(default="Umum", max_length=50)

@app.get("/")
def home():
    return {"message": "Mini-Social-Swarm API is Running"}

# Endpoint untuk memulai simulasi [cite: 208]
@app.post("/start-simulation")
def start_sim(payload: SimRequest, request: Request):
    _enforce_rate_limit(request)

    if not payload.topik.strip():
        raise HTTPException(status_code=400, detail="Topik tidak boleh kosong.")

    blocked_patterns = ("<script", "javascript:", "onerror=", "onload=")
    lowered = payload.topik.lower()
    if any(token in lowered for token in blocked_patterns):
        raise HTTPException(status_code=400, detail="Input topik tidak valid.")

    daftar_agen = get_agents(payload.kategori)
    hasil = run_simulation(payload.topik.strip(), daftar_agen)
    return {"status": "success", "data": hasil}