# backend/core/models.py
# Phase 2 Fondasi — Domain Models untuk VoxSwarm.
#
# File ini mendefinisikan model data resmi (Pydantic) untuk arsitektur target.
# PENTING: File ini adalah TAMBAHAN, bukan pengganti kode lama di agents.py.
# Kode lama tetap berjalan normal — adapter di bawah menjembatani keduanya.
#
# Referensi PRD: arsitektur target core/models.py

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AgentProfile — data statis agen (tidak berubah selama simulasi)
# ---------------------------------------------------------------------------

class AgentProfile(BaseModel):
    """
    Data statis agen — tidak berubah selama simulasi berlangsung.

    Fields:
        nama            : Nama kanonik agen (contoh: "Mahasiswa", "Pemerintah")
        role            : Deskripsi peran dan gaya bicara
        kepribadian     : Big-Five axes yang digunakan (openness, agreeableness, neuroticism)
        pengaruh        : Bobot pengaruh agen terhadap agen lain (0.0–1.0)
        volatility      : Seberapa mudah agen ganti stance. Rendah = keras kepala.
        initial_stance  : Stance awal sebelum diskusi. -1 = sangat menolak, 1 = sangat mendukung.
        voice_example   : Satu kalimat contoh gaya bicara khas agen ini.
        domain_scope    : Batasan domain agen. Contoh: "kebijakan makro nasional".
        is_counter      : True jika agen ini adalah counter-agent.
    """

    nama: str
    role: str
    kepribadian: dict = Field(default_factory=lambda: {
        "openness": 0.5,
        "agreeableness": 0.5,
        "neuroticism": 0.5,
    })
    pengaruh: float = Field(default=0.7, ge=0.0, le=1.0)
    volatility: float = Field(default=0.5, ge=0.0, le=1.0)
    initial_stance: float = Field(default=0.0, ge=-1.0, le=1.0)
    voice_example: str = ""
    domain_scope: Optional[str] = None
    is_counter: bool = False

    class Config:
        # Izinkan field tambahan dari dict lama agar adapter tidak error
        extra = "allow"


# ---------------------------------------------------------------------------
# AgentState — data dinamis agen (berubah tiap ronde)
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """
    Data dinamis agen — merepresentasikan status agen di satu titik waktu (ronde).

    Fields:
        agent_nama      : Nama agen (foreign key ke AgentProfile.nama)
        ronde           : Nomor ronde saat state ini direkam
        stance_score    : Skor stance float (-1.0 sampai 1.0)
        stance_label    : Label tekstual posisi agen
        pendapat        : Teks pendapat agen di ronde ini
        stance_history  : Riwayat skor stance dari ronde-ronde sebelumnya
        argumen_kunci   : Argumen terkuat yang sudah disampaikan (cegah repetisi)
    """

    agent_nama: str
    ronde: int
    stance_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    stance_label: Literal["mendukung", "netral", "menolak"] = "netral"
    pendapat: str = ""
    stance_history: list[float] = Field(default_factory=list)
    argumen_kunci: list[str] = Field(default_factory=list)

    @classmethod
    def from_memory_entry(cls, agent_nama: str, ronde: int, entry: dict) -> "AgentState":
        """Buat AgentState dari satu entri memori lama (format agents.py)."""
        skor = entry.get("skor", 0.0) or 0.0
        label_raw = entry.get("label", "netral")
        # Normalize label ke Literal yang valid
        if label_raw == "positif":
            label = "mendukung"
        elif label_raw == "negatif":
            label = "menolak"
        else:
            label = "netral"
        return cls(
            agent_nama=agent_nama,
            ronde=ronde,
            stance_score=skor,
            stance_label=label,
            pendapat=entry.get("pendapat", ""),
        )


# ---------------------------------------------------------------------------
# SimulationEvent — event/intervensi di tengah simulasi
# ---------------------------------------------------------------------------

class SimulationEvent(BaseModel):
    """
    Event atau intervensi yang terjadi di tengah simulasi.

    Fields:
        tipe            : Jenis event
        ronde           : Ronde saat event terjadi
        deskripsi       : Deskripsi lengkap event
        dampak_hint     : Hint perubahan stance per agen (dari user/system).
        actual_impacts  : Impact yang benar-benar diterapkan ke setiap agen.
    """

    tipe: Literal["intervensi", "berita_baru", "pernyataan_pemerintah", "protes", "eksternal"]
    ronde: int
    deskripsi: str
    dampak_hint: dict[str, float] = Field(default_factory=dict)
    actual_impacts: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# AgentAction — aksi yang diambil agent dalam satu ronde
# ---------------------------------------------------------------------------

class AgentAction(BaseModel):
    """
    Aksi yang diambil agen dalam satu ronde.

    Fields:
        agent_nama  : Nama agen yang melakukan aksi
        ronde       : Ronde saat aksi terjadi
        tipe_aksi   : Jenis aksi (berpendapat, merespons, intervensi)
        pendapat    : Teks pendapat yang dihasilkan
        sentimen    : Hasil scoring sentimen {"label", "skor"}
    """

    agent_nama: str
    ronde: int
    tipe_aksi: Literal["berpendapat", "merespons", "intervensi"] = "berpendapat"
    pendapat: str = ""
    sentimen: dict = Field(default_factory=lambda: {"label": "netral", "skor": 0.0})


# ---------------------------------------------------------------------------
# SimulationState — state keseluruhan simulasi di satu titik waktu
# ---------------------------------------------------------------------------

class SimulationState(BaseModel):
    """
    State keseluruhan simulasi pada satu titik waktu.

    Fields:
        topik               : Topik simulasi
        ronde_saat_ini      : Ronde yang sedang berjalan
        agent_states        : State semua agen di ronde ini
        events              : Daftar semua event yang sudah terjadi
        polarization_score  : Skor polarisasi (0.0 = konsensus, 1.0 = sangat terpolarisasi)
        consensus_score     : Skor konsensus (kebalikan polarisasi)
    """

    topik: str
    ronde_saat_ini: int = 1
    agent_states: list[AgentState] = Field(default_factory=list)
    events: list[SimulationEvent] = Field(default_factory=list)
    polarization_score: float = Field(default=0.0, ge=0.0, le=1.0)
    consensus_score: float = Field(default=0.0, ge=0.0, le=1.0)

    def get_agent_state(self, nama: str) -> Optional[AgentState]:
        """Ambil state agen berdasarkan nama."""
        for state in self.agent_states:
            if state.agent_nama == nama:
                return state
        return None


# ---------------------------------------------------------------------------
# Adapter — jembatan antara format dict lama dan model baru
# ---------------------------------------------------------------------------

def agent_profile_to_dict(profile: AgentProfile) -> dict:
    """
    Konversi AgentProfile kembali ke dict untuk backward compatibility.
    Menambahkan field _role_singkat dan gaya_str yang diharapkan kode lama.
    """
    return {
        "nama":        profile.nama,
        "role":        profile.role,
        "_role_singkat": profile.role[:250].rstrip(),
        "kepribadian": profile.kepribadian,
        "pengaruh":    profile.pengaruh,
        "memori":      [],
        "initial_stance": profile.initial_stance,
        "voice_example": profile.voice_example,
        "is_counter":  profile.is_counter,
    }


def agent_dict_to_profile(d: dict) -> AgentProfile:
    """
    Konversi format dict lama (agents.py) ke AgentProfile baru.

    Adapter ini memastikan kode lama di agents.py tetap jalan
    tanpa perlu diubah, tapi kita punya model resmi untuk dikembangkan.

    Args:
        d: Dict agen dari AGENT_REGISTRY atau COUNTER_AGENT_REGISTRY

    Returns:
        AgentProfile yang valid

    Example:
        from backend.agents import AGENT_REGISTRY
        from backend.core.models import agent_dict_to_profile

        profile = agent_dict_to_profile(AGENT_REGISTRY["Mahasiswa"])
        print(profile.nama)        # "Mahasiswa"
        print(profile.pengaruh)    # 0.7
    """
    kepribadian = d.get("kepribadian", {})

    # Hitung volatility dari agreeableness (rendah = keras kepala = rendah volatility)
    agreeableness = kepribadian.get("agreeableness", 0.5)
    volatility = agreeableness  # proxy sederhana; bisa dioverride nanti

    # Konversi initial_stance string ke float
    initial_stance_raw = d.get("initial_stance", 0.0)
    if isinstance(initial_stance_raw, str):
        stance_map = {
            "slight_negative": -0.25,
            "negative":        -0.5,
            "strong_negative": -0.8,
            "slight_positive":  0.25,
            "positive":         0.5,
            "strong_positive":  0.8,
            "neutral":          0.0,
        }
        initial_stance = stance_map.get(initial_stance_raw, 0.0)
    else:
        initial_stance = float(initial_stance_raw)

    return AgentProfile(
        nama=d.get("nama", "Unknown"),
        role=d.get("role", ""),
        kepribadian=kepribadian,
        pengaruh=float(d.get("pengaruh", 0.7)),
        volatility=volatility,
        initial_stance=initial_stance,
        voice_example=d.get("voice_example", ""),
        domain_scope=d.get("domain_scope"),
        is_counter=bool(d.get("is_counter", False)),
    )


def simulation_result_to_state(
    topik: str,
    ronde_ke: int,
    agents: list[dict],
    sentimen_agregat: dict,
    events: list[SimulationEvent] | None = None,
) -> SimulationState:
    """
    Konversi hasil simulasi lama ke SimulationState.

    Berguna untuk laporan, metrics, dan future reporting.py.

    Args:
        topik           : Topik simulasi
        ronde_ke        : Ronde terakhir yang selesai
        agents          : List dict agen (dengan field memori terisi)
        sentimen_agregat: {nama_agen: [skor_r1, skor_r2, ...]}
        events          : Event/intervensi yang terjadi selama simulasi

    Returns:
        SimulationState yang merepresentasikan kondisi akhir simulasi
    """
    agent_states = []
    for agen in agents:
        nama = agen["nama"]
        tren = sentimen_agregat.get(nama, [])
        skor_terakhir = tren[-1] if tren else 0.0

        if skor_terakhir > 0.2:
            label: Literal["mendukung", "netral", "menolak"] = "mendukung"
        elif skor_terakhir < -0.2:
            label = "menolak"
        else:
            label = "netral"

        pendapat_terakhir = ""
        if agen.get("memori"):
            pendapat_terakhir = agen["memori"][-1].get("pendapat", "")

        # Phase 5: populate argumen_kunci dari structured memory
        argumen_kunci: list[str] = []
        if "_memory_store" in agen:
            argumen_kunci = agen["_memory_store"].arguments.unique_arguments

        agent_states.append(AgentState(
            agent_nama=nama,
            ronde=ronde_ke,
            stance_score=skor_terakhir,
            stance_label=label,
            pendapat=pendapat_terakhir,
            stance_history=tren,
            argumen_kunci=argumen_kunci,
        ))

    # Hitung polarization_score dari variansi skor agen
    if len(tren_all := [s.stance_score for s in agent_states]) >= 2:
        mean = sum(tren_all) / len(tren_all)
        variance = sum((x - mean) ** 2 for x in tren_all) / len(tren_all)
        # Normalisasi ke 0-1 (variance max teoritis = 1.0 jika semua -1 atau +1)
        polarization = min(variance, 1.0)
        consensus = 1.0 - polarization
    else:
        polarization = 0.0
        consensus = 1.0

    return SimulationState(
        topik=topik,
        ronde_saat_ini=ronde_ke,
        agent_states=agent_states,
        events=events or [],
        polarization_score=round(polarization, 3),
        consensus_score=round(consensus, 3),
    )
