# backend/ml_pipeline.py
# Isolated ML layer — tidak mengubah kode existing sama sekali.
#
# Alur:
#   1. build_feature_row()       → ubah sim_output + real_context → dict fitur
#   2. append_history()          → simpan ke data/simulation_history.jsonl
#   3. build_training_dataset()  → merge history + feedback (label feedback override weak label)
#   4. train_model()             → latih dari dataset merged, simpan model ke disk
#   5. predict_outcome()         → prediksi skenario dari fitur baru
#   6. load_or_predict()         → entry point utama, fallback ke rule-based jika model belum ada

import os
import json
import hashlib
import threading
import statistics
from pathlib import Path
from typing import Optional

# Lazy import scikit-learn — tidak crash jika belum install
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
    from sklearn.metrics import (
        accuracy_score, confusion_matrix,
        precision_recall_fscore_support,
    )
    import pickle
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR      = Path(__file__).parent

# DATA_DIR: cari di backend/data/ dulu (production),
# fallback ke root project/data/ (jika file diletakkan di luar folder backend)
_candidate_dirs = [
    BASE_DIR / "data",           # backend/data/  ← lokasi normal
    BASE_DIR.parent / "data",    # project_root/data/ ← fallback
]
DATA_DIR = next(
    (d for d in _candidate_dirs if (d / "simulation_history.jsonl").exists()),
    _candidate_dirs[0],  # default ke backend/data/ jika belum ada file sama sekali
)

HISTORY_FILE  = DATA_DIR / "simulation_history.jsonl"
FEEDBACK_FILE = DATA_DIR / "feedback.jsonl"
MODEL_FILE    = DATA_DIR / "outcome_model.pkl"
ENCODER_FILE  = DATA_DIR / "label_encoder.pkl"

MIN_SAMPLES   = int(os.getenv("ML_MIN_SAMPLES", "5"))    # min rows sebelum ML aktif
MAX_HISTORY   = int(os.getenv("ML_MAX_HISTORY", "500"))  # cap file agar tidak bloat

_model_lock   = threading.Lock()
_history_lock = threading.Lock()

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# STEP 4 — Feature Extraction
# ---------------------------------------------------------------------------

def build_feature_row(sim_output: dict, real_context: dict) -> dict:
    """
    Ubah output run_simulation() + real_context dari ambil_konteks_real()
    menjadi satu dict fitur numerik yang siap masuk ML.

    Tidak memanggil LLM sama sekali — pure Python.
    """
    sentimen_agregat: dict = sim_output.get("sentimen_agregat", {})
    ronde_detail: list     = sim_output.get("ronde_detail", [])
    prediksi: dict         = sim_output.get("prediksi", {})
    aktor: dict            = sim_output.get("aktor_analisis", {})

    # ── Fitur dari sentimen agen ─────────────────────────────────────────
    all_scores = [s for tren in sentimen_agregat.values() for s in tren]
    mean_sent  = statistics.mean(all_scores)       if all_scores else 0.0
    std_sent   = statistics.stdev(all_scores)      if len(all_scores) > 1 else 0.0
    min_sent   = min(all_scores)                   if all_scores else 0.0
    max_sent   = max(all_scores)                   if all_scores else 0.0

    # ── Volatilitas per agen (rerata perubahan antar ronde) ──────────────
    vol_list = []
    for tren in sentimen_agregat.values():
        if len(tren) >= 2:
            changes = [abs(tren[i] - tren[i-1]) for i in range(1, len(tren))]
            vol_list.append(statistics.mean(changes))
    mean_vol = statistics.mean(vol_list) if vol_list else 0.0
    max_vol  = max(vol_list)             if vol_list else 0.0

    # ── Tren akhir vs awal ───────────────────────────────────────────────
    tren_delta = []
    for tren in sentimen_agregat.values():
        if len(tren) >= 2:
            tren_delta.append(tren[-1] - tren[0])
    mean_delta = statistics.mean(tren_delta) if tren_delta else 0.0

    # ── Proporsi sentimen label per ronde terakhir ───────────────────────
    n_pos = n_neg = n_net = 0
    if ronde_detail:
        last_ronde = ronde_detail[-1].get("agen", [])
        for a in last_ronde:
            lbl = a.get("sentimen", {}).get("label", "netral")
            if lbl == "positif":   n_pos += 1
            elif lbl == "negatif": n_neg += 1
            else:                  n_net += 1
    total_last = n_pos + n_neg + n_net or 1
    pct_pos    = n_pos / total_last
    pct_neg    = n_neg / total_last
    pct_net    = n_net / total_last

    # ── Fitur struktural simulasi ─────────────────────────────────────────
    n_agents       = len(sentimen_agregat)
    n_rounds       = sim_output.get("jumlah_ronde", len(ronde_detail))
    has_intervensi = int(bool(sim_output.get("intervensi")))

    # ── Aktor kunci ──────────────────────────────────────────────────────
    aktor_kunci   = aktor.get("aktor_kunci", [])
    swing_voter   = aktor.get("swing_voter", [])
    max_influence = max((a.get("pengaruh_skor", 0) for a in aktor_kunci), default=0.5)
    n_swing       = len(swing_voter)

    # ── Fitur dari data real (RSS + Reddit) ──────────────────────────────
    berita = real_context.get("berita", [])
    reddit = real_context.get("reddit", [])
    n_berita       = len(berita)
    n_reddit       = len(reddit)
    avg_relevansi  = statistics.mean(
        [a.get("relevansi", 0) for a in berita + reddit]
    ) if (berita or reddit) else 0.0
    avg_reddit_ups = statistics.mean(
        [r.get("upvotes", 0) for r in reddit]
    ) if reddit else 0.0

    # ── Label ground-truth (weak label berbasis fitur sentimen, bukan max(prediksi)) ──
    # Gunakan fitur sentimen yang sudah dihitung di atas agar label lebih bermakna
    pct_pos_val = n_pos / total_last
    pct_neg_val = n_neg / total_last

    if pct_pos_val >= 0.6:
        label = "Konsensus"
    elif pct_neg_val >= 0.5 or (max_sent - min_sent) > 1.6:
        label = "Polarisasi"
    else:
        label = "Status Quo"

    # Override dengan prediksi rule-based HANYA jika ada perbedaan kuat (>= 20% selisih):
    if prediksi:
        top_pred = max(prediksi, key=prediksi.get)
        top_val  = prediksi[top_pred]
        vals     = sorted(prediksi.values(), reverse=True)
        if len(vals) >= 2 and (top_val - vals[1]) >= 20:
            label = top_pred

    # ── topik_hash — FK untuk join dengan feedback.jsonl ─────────────────
    topik_raw  = (sim_output.get("topik") or "").strip().lower()
    topik_hash = hashlib.sha256(topik_raw.encode("utf-8")).hexdigest()[:16] if topik_raw else ""

    return {
        # sentimen
        "mean_sent":      round(mean_sent, 4),
        "std_sent":       round(std_sent, 4),
        "min_sent":       round(min_sent, 4),
        "max_sent":       round(max_sent, 4),
        "mean_vol":       round(mean_vol, 4),
        "max_vol":        round(max_vol, 4),
        "mean_delta":     round(mean_delta, 4),
        # proporsi label ronde terakhir
        "pct_pos":        round(pct_pos, 4),
        "pct_neg":        round(pct_neg, 4),
        "pct_net":        round(pct_net, 4),
        # struktural
        "n_agents":       n_agents,
        "n_rounds":       n_rounds,
        "has_intervensi": has_intervensi,
        "max_influence":  round(max_influence, 4),
        "n_swing":        n_swing,
        # data real
        "n_berita":       n_berita,
        "n_reddit":       n_reddit,
        "avg_relevansi":  round(avg_relevansi, 4),
        "avg_reddit_ups": round(avg_reddit_ups, 2),
        # label (weak supervision dari rule-based — bisa di-override feedback)
        "label":          label,
        # FK untuk join dengan feedback.jsonl
        "topik_hash":     topik_hash,
    }


# ---------------------------------------------------------------------------
# STEP 4b — Append ke history
# ---------------------------------------------------------------------------

def append_history(row: dict) -> None:
    """
    Append satu baris fitur ke simulation_history.jsonl.
    Thread-safe. Cap file di MAX_HISTORY baris (trim dari awal jika penuh).
    """
    with _history_lock:
        existing = []
        if HISTORY_FILE.exists():
            try:
                existing = [
                    json.loads(l)
                    for l in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
                    if l.strip()
                ]
            except Exception:
                existing = []

        existing.append(row)

        if len(existing) > MAX_HISTORY:
            existing = existing[-MAX_HISTORY:]

        HISTORY_FILE.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in existing),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# STEP 4c — Build Training Dataset (merge history + feedback)
# ---------------------------------------------------------------------------

def _load_feedback_map() -> dict[str, str]:
    """
    Baca feedback.jsonl dan kembalikan dict {topik_hash: label_aktual}.
    Hanya label valid yang masuk (Konsensus / Polarisasi / Status Quo).
    Return {} jika file belum ada atau corrupt.
    """
    VALID = {"Konsensus", "Polarisasi", "Status Quo"}
    if not FEEDBACK_FILE.exists():
        return {}
    try:
        feedback_map: dict[str, str] = {}
        for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            fb  = json.loads(line)
            th  = fb.get("topik_hash", "")
            lbl = fb.get("label_aktual", "")
            if th and lbl in VALID:
                # Iterasi berurutan → entri terbaru (append-only) menang otomatis
                feedback_map[th] = lbl
        return feedback_map
    except Exception as exc:
        print(f"[ML] _load_feedback_map: gagal baca feedback.jsonl — {exc}")
        return {}


def build_training_dataset() -> list[dict]:
    """
    Merge simulation_history.jsonl + feedback.jsonl menjadi dataset training.

    Aturan merge:
    - Basis data adalah simulation_history.jsonl (weak label dari rule-based).
    - Jika ada entri feedback dengan topik_hash yang cocok,
      label feedback OVERRIDE weak label.
    - Baris history tanpa pasangan feedback tetap pakai weak label.
    - Baris feedback tanpa pasangan history DIABAIKAN
      (tidak ada fitur numerik untuk dilatih).

    Tidak ada LLM call. Pure Python.

    Returns:
        List of dicts siap masuk train_model() — setiap dict punya
        semua FEATURE_COLS + "label" + "label_source" (metadata audit).
    """
    history = _load_history()
    if not history:
        return []

    feedback_map = _load_feedback_map()

    dataset: list[dict] = []
    for row in history:
        th = row.get("topik_hash", "")
        if th and th in feedback_map:
            merged = dict(row)
            merged["label"]        = feedback_map[th]
            merged["label_source"] = "feedback"      # audit trail
        else:
            merged = dict(row)
            merged.setdefault("label", "Status Quo")
            merged["label_source"] = "weak"          # audit trail

        dataset.append(merged)

    return dataset


# ---------------------------------------------------------------------------
# STEP 5 — Train Model
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "mean_sent", "std_sent", "min_sent", "max_sent",
    "mean_vol",  "max_vol",  "mean_delta",
    "pct_pos",   "pct_neg",  "pct_net",
    "n_agents",  "n_rounds", "has_intervensi",
    "max_influence", "n_swing",
    "n_berita",  "n_reddit", "avg_relevansi", "avg_reddit_ups",
]


def _load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return [
            json.loads(l)
            for l in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    except Exception:
        return []


def train_model(force: bool = False) -> dict:
    """
    Latih RandomForestClassifier dari dataset merged (history + feedback).
    Simpan model + encoder ke disk.

    Dataset dibangun oleh build_training_dataset() — label feedback
    otomatis override weak label dari rule-based.

    Args:
        force: Latih ulang meskipun model sudah ada.

    Returns:
        {"ok": bool, "n_samples": int, "n_feedback": int, "accuracy": float, "message": str}
    """
    if not _SKLEARN_AVAILABLE:
        return {"ok": False, "message": "scikit-learn tidak terinstall."}

    if MODEL_FILE.exists() and not force:
        return {"ok": True, "message": "Model sudah ada. Gunakan force=True untuk re-train."}

    # Pakai dataset merged bukan raw history
    rows = build_training_dataset()
    if len(rows) < MIN_SAMPLES:
        return {
            "ok":        False,
            "n_samples": len(rows),
            "message":   f"Data kurang: {len(rows)}/{MIN_SAMPLES} sampel minimum.",
        }

    n_feedback = sum(1 for r in rows if r.get("label_source") == "feedback")

    X     = [[row.get(f, 0.0) for f in FEATURE_COLS] for row in rows]
    y_raw = [row.get("label", "Status Quo") for row in rows]

    le = LabelEncoder()
    y  = le.fit_transform(y_raw)

    from sklearn.model_selection import LeaveOneOut
    from sklearn.metrics import accuracy_score as _accuracy_score

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_leaf=2,
        random_state=42,
        class_weight="balanced",
    )

    if len(rows) >= 20:
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        clf.fit(X_tr, y_tr)
        acc = clf.score(X_te, y_te)
        eval_method = "train/test split (80/20)"
    else:
        # Leave-One-Out CV untuk evaluasi jujur saat data < 20
        clf.fit(X, y)
        loo = LeaveOneOut()
        y_pred_loo = cross_val_predict(clf, X, y, cv=loo)
        acc = _accuracy_score(y, y_pred_loo)
        eval_method = f"Leave-One-Out CV ({len(rows)} fold)"

    with _model_lock:
        MODEL_FILE.write_bytes(pickle.dumps(clf))
        ENCODER_FILE.write_bytes(pickle.dumps(le))

    n_weak = len(rows) - n_feedback
    return {
        "ok":         True,
        "n_samples":  len(rows),
        "n_feedback": n_feedback,
        "accuracy":   round(acc, 4),
        "classes":    list(le.classes_),
        "eval_method": eval_method,
        "message":    (
            f"Model dilatih dari {len(rows)} sampel "
            f"({n_feedback} feedback, {n_weak} weak label). "
            f"Akurasi: {acc:.1%} [{eval_method}]"
        ),
    }


# ---------------------------------------------------------------------------
# STEP 6 — Predict
# ---------------------------------------------------------------------------

def predict_outcome(feature_row: dict) -> Optional[dict]:
    """
    Prediksi outcome skenario dari satu baris fitur.

    Returns:
        {"Konsensus": 45, "Polarisasi": 35, "Status Quo": 20}
        atau None jika model belum ada.
    """
    if not _SKLEARN_AVAILABLE:
        return None

    if not MODEL_FILE.exists() or not ENCODER_FILE.exists():
        return None

    try:
        with _model_lock:
            clf = pickle.loads(MODEL_FILE.read_bytes())
            le  = pickle.loads(ENCODER_FILE.read_bytes())

        X     = [[feature_row.get(f, 0.0) for f in FEATURE_COLS]]
        proba = clf.predict_proba(X)[0]
        classes = [str(c) for c in le.inverse_transform(list(range(len(proba))))]

        pct_raw = {c: p for c, p in zip(classes, proba)}
        total   = sum(pct_raw.values()) or 1.0
        pct_int = {c: round(p / total * 100) for c, p in pct_raw.items()}

        diff = 100 - sum(pct_int.values())
        if diff:
            top = max(pct_int, key=pct_int.get)
            pct_int[top] += diff

        return pct_int

    except Exception as e:
        print(f"[ML] predict_outcome error: {e}")
        return None


# ---------------------------------------------------------------------------
# Entry Point — dipanggil dari main.py / simulation.py
# ---------------------------------------------------------------------------

def build_feature_row_from_social(social_output: dict, real_context: dict) -> dict:
    """
    Adapter: ubah output run_social_simulation() menjadi feature row yang kompatibel
    dengan format build_feature_row() sehingga data sosmed bisa masuk ke ML pipeline.

    Mapping sosmed → fitur ML:
    - sentimen dihitung dari semua post (skor dari field post["sentimen"]["skor"])
    - n_agents  = jumlah akun unik yang membuat post
    - n_rounds  = jumlah tick
    - volatilitas = perubahan rata-rata sentimen antar tick
    - has_intervensi = apakah ada intervensi breaking news
    - data real (n_berita, n_reddit, avg_relevansi, avg_reddit_ups) sama seperti simulasi biasa

    Label (weak): distribusi sentimen → Konsensus / Polarisasi / Status Quo
    (sama dengan rule-based _parse_prediksi, tapi berbasis sosmed signal)

    Tidak memanggil LLM sama sekali — pure Python.
    """
    import hashlib
    import statistics

    semua_post = social_output.get("semua_post", [])
    tick_detail = social_output.get("tick_detail", [])
    intervensi = social_output.get("intervensi")
    topik_raw = (social_output.get("topik") or "").strip().lower()
    topik_hash = hashlib.sha256(topik_raw.encode("utf-8")).hexdigest()[:16] if topik_raw else ""

    # ── Kumpulkan skor sentimen dari semua post (kecuali SYSTEM) ─────────────
    all_scores = [
        p["sentimen"]["skor"]
        for p in semua_post
        if p.get("akun_id") != "SYSTEM" and isinstance(p.get("sentimen"), dict)
    ]

    mean_sent = statistics.mean(all_scores)  if all_scores else 0.0
    std_sent  = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
    min_sent  = min(all_scores)              if all_scores else 0.0
    max_sent  = max(all_scores)              if all_scores else 0.0

    # ── Volatilitas per tick ──────────────────────────────────────────────────
    tick_means = []
    for tick in tick_detail:
        tick_scores = [
            p["sentimen"]["skor"]
            for p in tick.get("posts_baru", [])
            if isinstance(p.get("sentimen"), dict)
        ]
        if tick_scores:
            tick_means.append(statistics.mean(tick_scores))

    vol_list = [abs(tick_means[i] - tick_means[i-1]) for i in range(1, len(tick_means))]
    mean_vol  = statistics.mean(vol_list) if vol_list else 0.0
    max_vol   = max(vol_list)             if vol_list else 0.0
    mean_delta = (tick_means[-1] - tick_means[0]) if len(tick_means) >= 2 else 0.0

    # ── Proporsi sentimen label di tick terakhir ──────────────────────────────
    n_pos = n_neg = n_net = 0
    if tick_detail:
        for p in tick_detail[-1].get("posts_baru", []):
            lbl = p.get("sentimen", {}).get("label", "netral") if isinstance(p.get("sentimen"), dict) else "netral"
            if lbl == "positif":    n_pos += 1
            elif lbl == "negatif":  n_neg += 1
            else:                   n_net += 1
    total_last = n_pos + n_neg + n_net or 1
    pct_pos = n_pos / total_last
    pct_neg = n_neg / total_last
    pct_net = n_net / total_last

    # ── Fitur struktural ──────────────────────────────────────────────────────
    profil_agen   = social_output.get("profil_agen", [])
    n_agents      = len(profil_agen)
    n_rounds      = len(tick_detail)
    has_intervensi = int(bool(intervensi))

    # Influence: pakai engagement ratio sebagai proxy pengaruh tertinggi
    max_eng       = max((p.get("total_likes_dapat", 0) + p.get("total_reply_dapat", 0) * 2 for p in profil_agen), default=1)
    max_influence = min(1.0, max_eng / max(1, n_rounds * n_agents))
    n_swing       = sum(1 for p in profil_agen if not p.get("is_authority") and not p.get("is_counter"))

    # ── Fitur dari data real ──────────────────────────────────────────────────
    berita        = real_context.get("berita", [])
    reddit        = real_context.get("reddit", [])
    n_berita      = len(berita)
    n_reddit      = len(reddit)
    avg_relevansi = statistics.mean([a.get("relevansi", 0) for a in berita + reddit]) if (berita or reddit) else 0.0
    avg_reddit_ups = statistics.mean([r.get("upvotes", 0) for r in reddit]) if reddit else 0.0

    # ── Weak label: mirip pola _parse_prediksi ────────────────────────────────
    statistik = social_output.get("statistik", {})
    viral_count = statistik.get("viral_count", 0)
    total_post  = statistik.get("total_post", 1) or 1
    if pct_pos >= 0.6:
        label = "Konsensus"
    elif pct_neg >= 0.5 or (viral_count / total_post) > 0.3:
        label = "Polarisasi"
    else:
        label = "Status Quo"

    return {
        "mean_sent":      round(mean_sent, 4),
        "std_sent":       round(std_sent, 4),
        "min_sent":       round(min_sent, 4),
        "max_sent":       round(max_sent, 4),
        "mean_vol":       round(mean_vol, 4),
        "max_vol":        round(max_vol, 4),
        "mean_delta":     round(mean_delta, 4),
        "pct_pos":        round(pct_pos, 4),
        "pct_neg":        round(pct_neg, 4),
        "pct_net":        round(pct_net, 4),
        "n_agents":       n_agents,
        "n_rounds":       n_rounds,
        "has_intervensi": has_intervensi,
        "max_influence":  round(max_influence, 4),
        "n_swing":        n_swing,
        "n_berita":       n_berita,
        "n_reddit":       n_reddit,
        "avg_relevansi":  round(avg_relevansi, 4),
        "avg_reddit_ups": round(avg_reddit_ups, 2),
        "label":          label,
        "topik_hash":     topik_hash,
        "_source":        "sosmed",  # metadata audit — tidak masuk FEATURE_COLS
    }


def load_or_predict(sim_output: dict, real_context: dict, prebuilt: bool = False) -> dict:
    """
    Entry point utama. Dipanggil setelah run_simulation() atau run_social_simulation().

    Args:
        sim_output:  Output run_simulation() — ATAU feature row pre-built dari
                     build_feature_row_from_social() jika prebuilt=True.
        real_context: Output ambil_konteks_real().
        prebuilt:    Jika True, sim_output sudah berupa feature row (skip build).
                     Dipakai oleh /start-social via build_feature_row_from_social().

    1. Bangun feature row (skip jika prebuilt=True)
    2. Append ke history (always — sosmed data masuk pipeline yang sama)
    3. Auto-train jika model belum ada dan data sudah cukup
    4. Prediksi — jika model siap, return ML prediction;
       jika belum, fallback ke rule-based / prediksi sosmed

    Returns:
        {
            "prediksi":   {"Konsensus": x, "Polarisasi": y, "Status Quo": z},
            "source":     "ml" | "rule_based",
            "n_samples":  int,
            "topik_hash": str,
        }
    """
    row = sim_output if prebuilt else build_feature_row(sim_output, real_context)

    try:
        append_history(row)
    except Exception as e:
        print(f"[ML] append_history error: {e}")

    history = _load_history()
    n = len(history)

    # Auto-train jika: model belum ada DAN data sudah cukup
    # ATAU model sudah ada tapi data bertambah signifikan (kelipatan 5)
    should_train = (
        (not MODEL_FILE.exists() and n >= MIN_SAMPLES) or
        (MODEL_FILE.exists() and n >= MIN_SAMPLES and n % 5 == 0)
    )
    if should_train:
        try:
            result = train_model(force=not MODEL_FILE.exists())
            if result.get("ok"):
                print(f"[ML] Auto-trained: {result['message']}")
        except Exception as e:
            print(f"[ML] auto-train error: {e}")

    ml_pred = predict_outcome(row)

    if ml_pred:
        return {
            "prediksi":   ml_pred,
            "source":     "ml",
            "n_samples":  n,
            "topik_hash": row.get("topik_hash", ""),
        }

    return {
        "prediksi":   (
            sim_output.get("prediksi")
            if not prebuilt
            else {"Konsensus": 33, "Polarisasi": 34, "Status Quo": 33}
        ) or {"Konsensus": 33, "Polarisasi": 34, "Status Quo": 33},
        "source":     "rule_based",
        "n_samples":  n,
        "topik_hash": row.get("topik_hash", ""),
        "note":       f"ML belum aktif ({n}/{MIN_SAMPLES} sampel terkumpul)",
    }


# ---------------------------------------------------------------------------
# Utility — endpoint /ml-status di main.py
# ---------------------------------------------------------------------------

def force_train_if_ready() -> dict:
    """
    Paksa training jika data sudah >= MIN_SAMPLES.
    Berguna dipanggil manual jika auto-train tidak terpicu.
    Bisa di-expose via endpoint GET /ml-train di main.py.
    """
    rows = _load_history()
    n = len(rows)
    if n < MIN_SAMPLES:
        return {
            "ok": False,
            "message": f"Data belum cukup: {n}/{MIN_SAMPLES} simulasi.",
            "n_samples": n,
            "min_samples": MIN_SAMPLES,
        }
    return train_model(force=True)


def get_ml_status() -> dict:
    """Status ML pipeline untuk endpoint diagnostik."""
    rows    = _load_history()
    dataset = build_training_dataset()
    n_fb    = sum(1 for r in dataset if r.get("label_source") == "feedback")

    return {
        "sklearn_available": _SKLEARN_AVAILABLE,
        "n_samples":         len(rows),
        "n_training_rows":   len(dataset),
        "n_feedback":        n_fb,
        "min_samples":       MIN_SAMPLES,
        "model_exists":      MODEL_FILE.exists(),
        "history_file":      str(HISTORY_FILE),
        "model_file":        str(MODEL_FILE),
        "ml_active":         MODEL_FILE.exists() and len(rows) >= MIN_SAMPLES,
        "samples_needed":    max(0, MIN_SAMPLES - len(rows)),
    }


# ---------------------------------------------------------------------------
# ML Metrics — endpoint /ml-metrics di main.py
# ---------------------------------------------------------------------------

def get_ml_metrics() -> dict:
    """
    Evaluasi performa model ML: akurasi, confusion matrix, precision/recall/F1
    per kelas. Menggunakan 5-fold cross-validation jika data >= 20 baris,
    fallback ke train=test split jika data kurang.

    Tidak ada LLM call — pure scikit-learn + Python.

    Returns:
        {
            "ok": bool,
            "message": str,
            "n_samples": int,
            "n_feedback_labels": int,
            "classes": [...],
            "accuracy": float,
            "accuracy_pct": int,
            "eval_method": str,
            "confusion_matrix": [[...]],
            "per_class": {kelas: {precision, recall, f1, support}},
            "macro_avg": {precision, recall, f1},
            "weighted_avg": {precision, recall, f1},
            "model_file": str,
            "evaluated_at": str,
        }
    """
    from datetime import datetime, timezone

    if not _SKLEARN_AVAILABLE:
        return {"ok": False, "message": "scikit-learn tidak terinstall."}

    if not MODEL_FILE.exists() or not ENCODER_FILE.exists():
        n_history = len(_load_history())
        sisa = max(0, MIN_SAMPLES - n_history)
        return {
            "ok":          False,
            "message":     (
                f"Butuh {sisa} simulasi lagi untuk mengaktifkan ML."
                if sisa > 0 else
                f"Data sudah cukup ({n_history} simulasi) — model sedang disiapkan. "
                "Coba jalankan satu simulasi lagi untuk memicu training."
            ),
            "n_samples":   n_history,
            "min_samples": MIN_SAMPLES,
        }

    dataset = build_training_dataset()
    if not dataset:
        return {"ok": False, "message": "Dataset kosong — belum ada simulasi tersimpan."}

    n_feedback = sum(1 for r in dataset if r.get("label_source") == "feedback")

    X     = [[row.get(f, 0.0) for f in FEATURE_COLS] for row in dataset]
    y_raw = [row.get("label", "Status Quo") for row in dataset]

    CLASSES_ORDER = ["Konsensus", "Polarisasi", "Status Quo"]

    try:
        with _model_lock:
            clf = pickle.loads(MODEL_FILE.read_bytes())
            le  = pickle.loads(ENCODER_FILE.read_bytes())

        y = le.transform(y_raw)   # encode menggunakan LE yang sudah di-fit

        n = len(dataset)
        if n >= 20:
            cv    = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            y_pred_enc = cross_val_predict(clf, X, y, cv=cv)
            eval_method = "5-fold CV"
        else:
            # Leave-One-Out CV untuk evaluasi jujur saat data < 20
            from sklearn.model_selection import LeaveOneOut
            loo = LeaveOneOut()
            y_pred_enc = cross_val_predict(clf, X, y, cv=loo)
            eval_method = f"Leave-One-Out CV ({n} fold)"

        y_pred_labels = le.inverse_transform(y_pred_enc)
        y_true_labels = le.inverse_transform(y)

        acc     = round(accuracy_score(y_true_labels, y_pred_labels), 4)
        acc_pct = round(acc * 100)

        # Confusion matrix — urutan sesuai CLASSES_ORDER (filter kelas yang ada)
        present_classes = [c for c in CLASSES_ORDER if c in le.classes_]
        cm = confusion_matrix(y_true_labels, y_pred_labels, labels=present_classes).tolist()

        # Per-class metrics
        precision_arr, recall_arr, f1_arr, support_arr = precision_recall_fscore_support(
            y_true_labels, y_pred_labels,
            labels=present_classes,
            zero_division=0,
        )

        per_class: dict = {}
        for i, kelas in enumerate(present_classes):
            per_class[kelas] = {
                "precision": round(float(precision_arr[i]), 4),
                "recall":    round(float(recall_arr[i]),    4),
                "f1":        round(float(f1_arr[i]),        4),
                "support":   int(support_arr[i]),
            }

        # Macro & weighted averages
        macro_p, macro_r, macro_f, _     = precision_recall_fscore_support(
            y_true_labels, y_pred_labels, average="macro",    zero_division=0
        )
        weight_p, weight_r, weight_f, _  = precision_recall_fscore_support(
            y_true_labels, y_pred_labels, average="weighted", zero_division=0
        )

        return {
            "ok":                True,
            "n_samples":         n,
            "n_feedback_labels": n_feedback,
            "classes":           present_classes,
            "accuracy":          acc,
            "accuracy_pct":      acc_pct,
            "eval_method":       eval_method,
            "confusion_matrix":  cm,
            "per_class":         per_class,
            "macro_avg": {
                "precision": round(float(macro_p),  4),
                "recall":    round(float(macro_r),  4),
                "f1":        round(float(macro_f),  4),
            },
            "weighted_avg": {
                "precision": round(float(weight_p), 4),
                "recall":    round(float(weight_r), 4),
                "f1":        round(float(weight_f), 4),
            },
            "model_file":   str(MODEL_FILE),
            "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    except Exception as exc:
        return {"ok": False, "message": f"Evaluasi gagal: {exc}"}