"""trace_qa.py — QA reject rate: multi-topik, multi-run, breakdown per-agent."""
import sys, os, builtins

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.simulation as sim_mod
from backend.simulation import run_simulation
from backend.agents import get_agents

# ── QA Stats ──
qa_stats = {"total": 0, "invalid": 0}
agent_stats = {}  # nama_agent -> {"total": N, "invalid": N}
_current_invalid = False
_orig_print = builtins.print


def _qa_print(*args, **kwargs):
    global _current_invalid
    if args and isinstance(args[0], str) and args[0].startswith("[QA]") and "INVALID" in args[0]:
        _current_invalid = True
    return _orig_print(*args, **kwargs)


def _get_agent_name():
    """Lacak nama agent dari stack frame pemanggil."""
    try:
        frame = sys._getframe(2)
        # cari di _proses_satu_agen -> agen dict
        agen = frame.f_locals.get("agen", None)
        if agen and isinstance(agen, dict):
            return agen.get("nama", "unknown")
        # fallback: cari di level atas
        frame = sys._getframe(3)
        agen = frame.f_locals.get("agen", None)
        if agen and isinstance(agen, dict):
            return agen.get("nama", "unknown")
    except (ValueError, IndexError, KeyError):
        pass
    return "unknown"


_orig_qa_check = sim_mod._qa_check_topic


def _tracked_qa_check(topik, jawaban, system_p, user_p):
    global _current_invalid
    agent_name = _get_agent_name()
    qa_stats["total"] += 1
    agent_stats.setdefault(agent_name, {"total": 0, "invalid": 0})
    agent_stats[agent_name]["total"] += 1
    _current_invalid = False
    result = _orig_qa_check(topik, jawaban, system_p, user_p)
    if _current_invalid:
        qa_stats["invalid"] += 1
        agent_stats[agent_name]["invalid"] += 1
    return result


sim_mod._qa_check_topic = _tracked_qa_check
builtins.print = _qa_print

# ── 3 Topik ──
TOPIK_SET = [
    "Apakah program MBG sudah tepat sasaran?",
    "Apakah kenaikan PPN 12% perlu ditunda?",
    "Apakah larangan TikTok Shop di Indonesia sudah tepat?",
]

for i, topik in enumerate(TOPIK_SET, 1):
    # reset per-topik
    qa_stats = {"total": 0, "invalid": 0}
    agent_stats = {}

    agents = get_agents("Kebijakan")
    n_agent = len(agents)

    print(f"\n{'='*60}")
    print(f"  SIMULASI {i}/3: {topik}")
    print(f"  Agent: {[a['nama'] for a in agents]}")
    print(f"{'='*60}")
    print("=== MULAI ===")
    try:
        result = run_simulation(topik, agents, jumlah_ronde=2, tier="free")
    except Exception as e:
        _orig_print(f"Error: {e}")
    print("=== SELESAI ===")

    # ── Laporan per-topik ──
    print(f"\n  -- HASIL SIMULASI {i} --")
    expected = n_agent * 2
    print(f"  QA calls: {qa_stats['total']}/{expected} | INVALID: {qa_stats['invalid']} | "
          f"Rate: {(qa_stats['invalid']/qa_stats['total']*100) if qa_stats['total'] else 0:.1f}%")
    print(f"  Breakdown per-agent:")
    for agent_name, st in sorted(agent_stats.items()):
        rate = (st["invalid"] / st["total"] * 100) if st["total"] else 0
        bar = "#" * min(st["invalid"], 20)
        print(f"    {agent_name:20s}  calls={st['total']:2d}  INVALID={st['invalid']:2d}  ({rate:5.1f}%)  {bar}")
    gap = expected - qa_stats["total"]
    if gap:
        print(f"  [NOTE] {gap} calls tidak sampai QA (error/interupsi)")
