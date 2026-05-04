#!/usr/bin/env python3
"""
scripts/generate_dummy_data.py
Bootstrap ML pipeline VoxSwarm dengan 60 baris data dummy realistis.

Cara pakai:
    python scripts/generate_dummy_data.py

Persyaratan:
    - Python >= 3.9
    - Tidak ada dependensi eksternal (hanya stdlib)
    - Bisa dijalankan standalone tanpa virtual environment FastAPI

Perilaku:
    - Membaca simulation_history.jsonl sebagai acuan range nilai realistis
      (jika ada). Jika tidak ada, pakai default range dari dokumentasi.
    - Generate 60 baris dummy dengan distribusi label seimbang (20 per kelas):
      Konsensus, Polarisasi, Status Quo
    - Tambahkan noise Gaussian ke tiap fitur numerik
    - APPEND ke backend/data/simulation_history.jsonl (tidak overwrite)
    - Cetak ringkasan distribusi label ke console
"""

import json
import math
import random
import hashlib
from pathlib import Path

# ── Seed untuk reproduktibilitas (tapi tetap bisa di-override) ───────────────
random.seed(42)

# ── Lokasi output ─────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
HISTORY_FILE = PROJECT_ROOT / "backend" / "data" / "simulation_history.jsonl"

# Fallback: root/data/ jika backend/data/ belum ada
if not HISTORY_FILE.parent.exists():
    ALT = PROJECT_ROOT / "data" / "simulation_history.jsonl"
    if ALT.parent.exists() or (not HISTORY_FILE.parent.exists()):
        HISTORY_FILE = ALT

HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Util: Normal noise ────────────────────────────────────────────────────────
def _gauss(mu: float, sigma: float, lo: float = -1.0, hi: float = 1.0) -> float:
    """Gaussian sample diklem ke [lo, hi]."""
    v = random.gauss(mu, sigma)
    return max(lo, min(hi, v))


def _uniform(lo: float, hi: float) -> float:
    return random.uniform(lo, hi)


# ── Generator fitur per label ─────────────────────────────────────────────────

def _gen_konsensus() -> dict:
    """
    Karakteristik: mayoritas positif, sentimen stabil, tren naik atau datar.
    pct_pos: 0.55–0.85 | mean_sent: 0.1–0.6 | pct_neg: 0.0–0.2
    std_sent: rendah (0.1–0.35) | mean_delta: -0.05 sampai +0.3
    """
    pct_pos    = _gauss(0.68, 0.10, 0.55, 0.85)
    pct_neg    = _gauss(0.10, 0.06, 0.00, 0.20)
    pct_net    = max(0.0, round(1.0 - pct_pos - pct_neg, 4))
    mean_sent  = _gauss(0.35, 0.12, 0.10, 0.60)
    std_sent   = _gauss(0.22, 0.07, 0.10, 0.35)
    min_sent   = _gauss(mean_sent - std_sent * 1.5, 0.05, -0.5, mean_sent)
    max_sent   = _gauss(mean_sent + std_sent * 1.5, 0.05, mean_sent, 1.0)
    mean_vol   = _gauss(0.12, 0.04, 0.02, 0.25)
    max_vol    = _gauss(mean_vol * 2.0, 0.05, mean_vol, 0.5)
    mean_delta = _gauss(0.12, 0.08, -0.05, 0.30)
    return dict(
        pct_pos=pct_pos, pct_neg=pct_neg, pct_net=pct_net,
        mean_sent=mean_sent, std_sent=std_sent,
        min_sent=min_sent, max_sent=max_sent,
        mean_vol=mean_vol, max_vol=max_vol, mean_delta=mean_delta,
        label="Konsensus",
    )


def _gen_polarisasi() -> dict:
    """
    Karakteristik: sentimen negatif dominan atau range lebar, volatilitas tinggi.
    pct_neg: 0.45–0.75 | std_sent: tinggi (0.5–0.8)
    mean_sent: -0.4 sampai -0.1 | mean_delta: -0.4 sampai -0.05
    """
    # Pilih sub-tipe: (a) pct_neg tinggi atau (b) std_sent tinggi
    if random.random() < 0.55:
        pct_neg = _gauss(0.58, 0.08, 0.45, 0.75)
        pct_pos = _gauss(0.18, 0.07, 0.05, 0.35)
        std_sent = _gauss(0.55, 0.10, 0.35, 0.80)
    else:
        pct_neg  = _gauss(0.38, 0.06, 0.20, 0.55)
        pct_pos  = _gauss(0.30, 0.08, 0.10, 0.50)
        std_sent = _gauss(0.65, 0.08, 0.50, 0.80)
    pct_net    = max(0.0, round(1.0 - pct_pos - pct_neg, 4))
    mean_sent  = _gauss(-0.22, 0.10, -0.40, -0.05)
    min_sent   = _gauss(-0.85, 0.07, -1.0, mean_sent)
    max_sent   = _gauss(0.75, 0.10, 0.40, 1.0)
    mean_vol   = _gauss(0.40, 0.10, 0.20, 0.65)
    max_vol    = _gauss(mean_vol * 2.0, 0.15, mean_vol, 1.5)
    mean_delta = _gauss(-0.18, 0.09, -0.40, -0.02)
    return dict(
        pct_pos=pct_pos, pct_neg=pct_neg, pct_net=pct_net,
        mean_sent=mean_sent, std_sent=std_sent,
        min_sent=min_sent, max_sent=max_sent,
        mean_vol=mean_vol, max_vol=max_vol, mean_delta=mean_delta,
        label="Polarisasi",
    )


def _gen_status_quo() -> dict:
    """
    Karakteristik: sentimen campuran tapi tidak ekstrem, tren mendekati nol.
    pct_pos: 0.15–0.45 | pct_neg: 0.15–0.45 | std_sent: sedang (0.2–0.5)
    mean_sent: -0.15 sampai +0.15 | mean_delta: -0.1 sampai +0.1
    """
    pct_pos    = _gauss(0.28, 0.08, 0.15, 0.45)
    pct_neg    = _gauss(0.28, 0.08, 0.15, 0.45)
    pct_net    = max(0.0, round(1.0 - pct_pos - pct_neg, 4))
    mean_sent  = _gauss(0.00, 0.07, -0.15, 0.15)
    std_sent   = _gauss(0.33, 0.07, 0.20, 0.50)
    min_sent   = _gauss(-0.60, 0.10, -0.85, mean_sent)
    max_sent   = _gauss(0.60, 0.10, mean_sent, 0.85)
    mean_vol   = _gauss(0.20, 0.06, 0.08, 0.35)
    max_vol    = _gauss(mean_vol * 1.8, 0.08, mean_vol, 0.7)
    mean_delta = _gauss(0.00, 0.05, -0.10, 0.10)
    return dict(
        pct_pos=pct_pos, pct_neg=pct_neg, pct_net=pct_net,
        mean_sent=mean_sent, std_sent=std_sent,
        min_sent=min_sent, max_sent=max_sent,
        mean_vol=mean_vol, max_vol=max_vol, mean_delta=mean_delta,
        label="Status Quo",
    )


# ── Fitur struktural (sama untuk semua label, dengan noise) ──────────────────

def _structural_features(ref_rows: list[dict]) -> dict:
    """
    Buat fitur struktural dengan noise realistis.
    Jika ada data referensi, pakai distribusi dari sana. Jika tidak, pakai default.
    """
    if ref_rows:
        # Sampling dari nilai unik yang pernah ada (+ noise kecil)
        sample = random.choice(ref_rows)
        n_agents     = max(3, int(sample.get("n_agents", 7)     + random.randint(-1, 2)))
        n_rounds     = max(1, min(5, int(sample.get("n_rounds", 3) + random.randint(-1, 1))))
        max_influence = _gauss(sample.get("max_influence", 0.7), 0.08, 0.3, 1.0)
        n_swing      = max(0, int(sample.get("n_swing", 2)       + random.randint(-1, 2)))
        n_berita     = max(0, int(sample.get("n_berita", 5)      + random.randint(-3, 4)))
        n_reddit     = max(0, int(sample.get("n_reddit", 0)      + random.randint(0, 3)))
        avg_relevansi  = _gauss(sample.get("avg_relevansi", 1.5), 0.4, 0.5, 3.5)
        avg_reddit_ups = _gauss(sample.get("avg_reddit_ups", 0), 20.0, 0.0, 200.0)
    else:
        n_agents      = random.choice([5, 6, 7, 7, 8])
        n_rounds      = random.choice([2, 3, 3, 4, 5])
        max_influence = _gauss(0.75, 0.12, 0.3, 1.0)
        n_swing       = random.randint(0, 3)
        n_berita      = random.randint(0, 12)
        n_reddit      = random.choice([0, 0, 0, 1, 2, 5])
        avg_relevansi = _gauss(1.5, 0.5, 0.5, 3.5)
        avg_reddit_ups = _gauss(10, 20, 0, 200)

    has_intervensi = 1 if random.random() < 0.2 else 0

    return dict(
        n_agents=n_agents,
        n_rounds=n_rounds,
        has_intervensi=has_intervensi,
        max_influence=round(max_influence, 4),
        n_swing=n_swing,
        n_berita=n_berita,
        n_reddit=n_reddit,
        avg_relevansi=round(avg_relevansi, 4),
        avg_reddit_ups=round(avg_reddit_ups, 2),
    )


# ── Buat satu baris lengkap ───────────────────────────────────────────────────

def _make_row(gen_fn, ref_rows: list[dict], seed_suffix: str) -> dict:
    feat   = gen_fn()
    struct = _structural_features(ref_rows)
    label  = feat.pop("label")

    # topik_hash unik per baris dummy
    raw = f"dummy_{label}_{seed_suffix}_{random.random()}"
    topik_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

    row = {
        # sentimen
        "mean_sent":      round(feat["mean_sent"],  4),
        "std_sent":       round(feat["std_sent"],   4),
        "min_sent":       round(feat["min_sent"],   4),
        "max_sent":       round(feat["max_sent"],   4),
        "mean_vol":       round(feat["mean_vol"],   4),
        "max_vol":        round(feat["max_vol"],    4),
        "mean_delta":     round(feat["mean_delta"], 4),
        # proporsi
        "pct_pos":        round(feat["pct_pos"], 4),
        "pct_neg":        round(feat["pct_neg"], 4),
        "pct_net":        round(max(0.0, feat["pct_net"]), 4),
        # struktural
        **struct,
        # label
        "label":          label,
        "topik_hash":     topik_hash,
        # audit trail — menandai baris ini berasal dari script dummy
        "_source":        "dummy",
    }
    return row


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Baca history sebagai referensi range nilai
    ref_rows: list[dict] = []
    if HISTORY_FILE.exists():
        try:
            ref_rows = [
                json.loads(l)
                for l in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
                if l.strip()
            ]
            print(f"[generate_dummy_data] Membaca {len(ref_rows)} baris dari {HISTORY_FILE}")
        except Exception as e:
            print(f"[generate_dummy_data] Gagal baca history: {e} — pakai default range")
    else:
        print(f"[generate_dummy_data] History tidak ditemukan, pakai default range")

    # 2. Generate 60 baris (20 per kelas)
    generators = [
        ("Konsensus",  _gen_konsensus),
        ("Polarisasi", _gen_polarisasi),
        ("Status Quo", _gen_status_quo),
    ]
    new_rows: list[dict] = []
    for label, gen_fn in generators:
        for i in range(20):
            row = _make_row(gen_fn, ref_rows, f"{label}_{i}")
            new_rows.append(row)

    # Acak urutan agar tidak berkelompok per label
    random.shuffle(new_rows)

    # 3. Append ke history (BUKAN overwrite)
    existing_lines: list[str] = []
    if HISTORY_FILE.exists():
        existing_lines = [
            l for l in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]

    new_lines = [json.dumps(r, ensure_ascii=False) for r in new_rows]
    all_lines = existing_lines + new_lines

    HISTORY_FILE.write_text(
        "\n".join(all_lines),
        encoding="utf-8",
    )

    # 4. Ringkasan
    label_counts: dict[str, int] = {}
    for r in new_rows:
        lbl = r["label"]
        label_counts[lbl] = label_counts.get(lbl, 0) + 1

    print(f"\n[generate_dummy_data] ✅ {len(new_rows)} baris dummy ditambahkan ke:")
    print(f"   {HISTORY_FILE}")
    print(f"\nDistribusi label baris dummy:")
    for lbl, cnt in sorted(label_counts.items()):
        bar = "█" * cnt
        print(f"   {lbl:<12} {bar} ({cnt})")
    print(f"\nTotal baris di history sekarang: {len(all_lines)}")
    print("\nLangkah berikutnya:")
    print("  1. Jalankan server FastAPI")
    print("  2. Panggil GET /ml-train untuk trigger training dengan data baru")
    print("  3. Cek GET /ml-debug untuk melihat distribusi dan feature importance")


if __name__ == "__main__":
    main()