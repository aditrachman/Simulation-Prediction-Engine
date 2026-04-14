# backend/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from backend.engine import run_simulation  # Tambahkan 'backend.'
from backend.agents import get_agents      # Tambahkan 'backend.'
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI() # Backend API menggunakan FastAPI [cite: 179]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Izinkan semua akses (untuk development)
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimRequest(BaseModel):
    topik: str
    kategori: str = "Umum"

@app.get("/")
def home():
    return {"message": "Mini-Social-Swarm API is Running"}

# Endpoint untuk memulai simulasi [cite: 208]
@app.post("/start-simulation")
def start_sim(request: SimRequest):
    daftar_agen = get_agents(request.kategori)
    hasil = run_simulation(request.topik, daftar_agen)
    return {"status": "success", "data": hasil}