"""Simulasi penuh dengan LLM di-mock harus menulis CaseStudy ke disk."""

import json

from backend import simulation
from backend.agents import get_agents
from backend.services import casestudy_assemble, narrator, run_store

TURN_JSON = json.dumps(
    {
        "stance": "menolak",
        "score": -0.6,
        "alasan": "Distribusi bantuan belum jelas, jadi klaim tepat sasaran belum terbukti.",
        "sesuai_topik": True,
        "berubah_karena": None,
    }
)


def test_full_simulation_writes_case_study(tmp_path, monkeypatch):
    # conftest sudah mengarahkan DATA_DIR kedua modul ke tmp_path
    run_dir = run_store.DATA_DIR
    case_dir = casestudy_assemble.DATA_DIR

    monkeypatch.setattr(simulation, "call_llm", lambda *args, **kwargs: TURN_JSON)
    monkeypatch.setattr(
        casestudy_assemble,
        "generate_narrative",
        lambda run, computed=None: {
            **narrator._fallback_narrative(computed),
            "narator_fallback": True,
            "narator_fallback_reason": "test",
        },
    )

    hasil = simulation.run_simulation(
        topik="Apakah program MBG tepat sasaran?",
        agents=get_agents("Politik")[:2],
        jumlah_ronde=1,
        tier="free",
    )

    files = list(case_dir.glob("*.json"))
    assert len(files) == 1
    assert files[0].stem == hasil["_run_id"]

    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["judul"] == hasil["topik"]
    assert list(case_dir.glob("*.tmp")) == []
