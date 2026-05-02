# backend/feedback.py
# Feedback Loop & Ground Truth Collection untuk VoxSwarm ML Pipeline.
#
# Bertanggung jawab atas:
#   - Menerima dan memvalidasi label ground truth dari pengguna / operator
#   - Menyimpan ke backend/data/feedback.jsonl (thread-safe)
#   - Menyediakan statistik feedback terkumpul
#   - Memicu auto re-train jika feedback >= MIN_FEEDBACK_TO_RETRAIN
#
# CONSTRAINT:
#   - TIDAK ADA LLM call di modul ini — pure Python
#   - Validasi ketat: label harus salah satu dari VALID_LABELS
#   - Thread-safe file write (mirror pola _history_lock di ml_pipeline.py)

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR      = Path(__file__).parent
DATA_DIR      = BASE_DIR / "data"
FEEDBACK_FILE = DATA_DIR / "feedback.jsonl"

VALID_LABELS            = {"Konsensus", "Polarisasi", "Status Quo"}
MAX_FEEDBACK            = 2000   # cap file agar tidak bloat
MIN_FEEDBACK_TO_RETRAIN = 3      # trigger auto re-train setelah n feedback masuk

DATA_DIR.mkdir(parents=True, exist_ok=True)

_feedback_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_topik_hash(topik: str) -> str:
    """
    Buat topik_hash deterministik (16 char SHA-256) dari string topik.
    Case-insensitive, strip whitespace.
    Digunakan sebagai FK untuk join dengan simulation_history.jsonl.
    """
    normalized = topik.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class FeedbackValidationError(ValueError):
    """Dilempar saat validasi field feedback gagal."""
    pass


def validate_feedback(
    topik: str,
    label_aktual: str,
    confidence: float,
    catatan: str,
) -> None:
    """
    Validasi ketat semua field feedback sebelum disimpan.

    Raises:
        FeedbackValidationError: jika ada field tidak valid.
    """
    if not topik or not topik.strip():
        raise FeedbackValidationError("Field 'topik' tidak boleh kosong.")

    if len(topik) > 500:
        raise FeedbackValidationError("Field 'topik' maksimal 500 karakter.")

    if label_aktual not in VALID_LABELS:
        valid_str = ", ".join(sorted(VALID_LABELS))
        raise FeedbackValidationError(
            f"Label '{label_aktual}' tidak valid. Pilih salah satu: {valid_str}."
        )

    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        raise FeedbackValidationError(
            f"Field 'confidence' harus antara 0.0 dan 1.0, diterima: {confidence}."
        )

    if len(catatan) > 1000:
        raise FeedbackValidationError("Field 'catatan' maksimal 1000 karakter.")


# ---------------------------------------------------------------------------
# Storage — internal
# ---------------------------------------------------------------------------

def _load_all_feedback() -> list[dict]:
    """Baca semua baris feedback.jsonl. Return [] jika file belum ada atau corrupt."""
    if not FEEDBACK_FILE.exists():
        return []
    try:
        return [
            json.loads(line)
            for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception:
        return []


def _write_all_feedback(rows: list[dict]) -> None:
    """Tulis ulang seluruh feedback.jsonl. Harus dipanggil dalam _feedback_lock."""
    FEEDBACK_FILE.write_text(
        "\n".join(json.dumps(fb, ensure_ascii=False) for fb in rows),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public: save
# ---------------------------------------------------------------------------

def save_feedback(
    topik: str,
    label_aktual: str,
    confidence: float = 1.0,
    catatan: str = "",
) -> dict:
    """
    Validasi dan simpan satu entri feedback ke feedback.jsonl.

    - Thread-safe menggunakan _feedback_lock.
    - Update-if-exists: jika topik_hash sudah ada, entry lama diganti
      (operator bisa koreksi feedback yang salah).
    - File di-cap di MAX_FEEDBACK baris (trim dari awal jika penuh).

    Returns:
        Dict entri yang disimpan + field "action": "created" | "updated".

    Raises:
        FeedbackValidationError: jika validasi gagal.
    """
    validate_feedback(topik, label_aktual, confidence, catatan)

    topik_hash = make_topik_hash(topik)
    entry = {
        "topik_hash":   topik_hash,
        "topik":        topik.strip(),
        "label_aktual": label_aktual,
        "confidence":   round(float(confidence), 4),
        "catatan":      catatan.strip(),
        "timestamp":    _current_timestamp(),
    }

    with _feedback_lock:
        existing = _load_all_feedback()

        action  = "created"
        updated = False
        for i, fb in enumerate(existing):
            if fb.get("topik_hash") == topik_hash:
                existing[i] = entry
                action  = "updated"
                updated = True
                break

        if not updated:
            existing.append(entry)

        if len(existing) > MAX_FEEDBACK:
            existing = existing[-MAX_FEEDBACK:]

        _write_all_feedback(existing)

    return {**entry, "action": action}


# ---------------------------------------------------------------------------
# Public: statistics
# ---------------------------------------------------------------------------

def get_feedback_stats() -> dict:
    """
    Kembalikan statistik ringkasan semua feedback yang terkumpul.

    Returns:
        {
            "total":            int,
            "by_label":         {"Konsensus": int, "Polarisasi": int, "Status Quo": int},
            "avg_confidence":   float,
            "latest_timestamp": str | None,
            "feedback_file":    str,
            "min_to_retrain":   int,
            "ready_to_retrain": bool,
        }
    """
    with _feedback_lock:
        rows = _load_all_feedback()

    by_label: dict[str, int] = {lbl: 0 for lbl in VALID_LABELS}
    confidences: list[float] = []
    latest_ts: Optional[str] = None

    for fb in rows:
        lbl = fb.get("label_aktual", "")
        if lbl in by_label:
            by_label[lbl] += 1

        conf = fb.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))

        ts = fb.get("timestamp")
        if ts and (latest_ts is None or ts > latest_ts):
            latest_ts = ts

    avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    return {
        "total":            len(rows),
        "by_label":         by_label,
        "avg_confidence":   avg_conf,
        "latest_timestamp": latest_ts,
        "feedback_file":    str(FEEDBACK_FILE),
        "min_to_retrain":   MIN_FEEDBACK_TO_RETRAIN,
        "ready_to_retrain": len(rows) >= MIN_FEEDBACK_TO_RETRAIN,
    }


# ---------------------------------------------------------------------------
# Background re-train trigger
# ---------------------------------------------------------------------------

def _trigger_retrain_background(n_feedback: int) -> None:
    """
    Dipanggil di daemon thread setelah save_feedback() berhasil.
    Lazy import untuk hindari circular import antar modul backend.
    """
    if n_feedback < MIN_FEEDBACK_TO_RETRAIN:
        return
    try:
        from backend.ml_pipeline import train_model  # noqa: PLC0415
        result = train_model(force=True)
        if result.get("ok"):
            print(f"[Feedback] Auto re-train selesai: {result.get('message', '')}")
        else:
            print(f"[Feedback] Auto re-train gagal: {result.get('message', '')}")
    except Exception as exc:
        print(f"[Feedback] Auto re-train error: {exc}")


# ---------------------------------------------------------------------------
# Public: entry point utama — dipanggil dari main.py
# ---------------------------------------------------------------------------

def submit_feedback(
    topik: str,
    label_aktual: str,
    confidence: float = 1.0,
    catatan: str = "",
) -> dict:
    """
    Entry point utama yang dipanggil dari endpoint POST /feedback di main.py.

    Alur:
    1. Simpan feedback via save_feedback()
    2. Hitung total feedback terkini
    3. Jika total >= MIN_FEEDBACK_TO_RETRAIN, kick daemon thread untuk re-train

    Returns:
        Dict save_feedback() ditambah:
            "retrain_triggered": bool — apakah background re-train dikick
            "total_feedback":    int  — total feedback setelah save ini
    """
    result  = save_feedback(topik, label_aktual, confidence, catatan)
    stats   = get_feedback_stats()
    n_total = stats["total"]
    retrain_triggered = n_total >= MIN_FEEDBACK_TO_RETRAIN

    if retrain_triggered:
        t = threading.Thread(
            target=_trigger_retrain_background,
            args=(n_total,),
            daemon=True,
            name="feedback-retrain",
        )
        t.start()

    result["retrain_triggered"] = retrain_triggered
    result["total_feedback"]    = n_total
    return result


def submit_feedback_by_hash(
    topik_hash: str,
    label_aktual: str,
    confidence: float = 1.0,
    catatan: str = "",
) -> dict:
    """
    Versi hash-first dari submit_feedback().

    Menerima topik_hash 16-karakter langsung (dari response /start-simulation)
    alih-alih plain-text topik. Menghilangkan risiko mismatch akibat typo
    atau perbedaan whitespace saat operator mengetik ulang topik.

    Aturan merge dengan simulation_history.jsonl tetap sama:
    jika topik_hash cocok, label feedback override weak label.

    Args:
        topik_hash:   Hash 16-karakter dari build_feature_row() / load_or_predict().
        label_aktual: Ground truth: "Konsensus" | "Polarisasi" | "Status Quo".
        confidence:   Keyakinan operator (0.0–1.0).
        catatan:      Catatan opsional.

    Returns:
        Dict sama seperti submit_feedback() + "retrain_triggered" + "total_feedback".

    Raises:
        FeedbackValidationError: jika topik_hash kosong/salah format atau label tidak valid.
    """
    # Validasi hash
    topik_hash = (topik_hash or "").strip()
    if len(topik_hash) != 16 or not all(c in "0123456789abcdef" for c in topik_hash):
        raise FeedbackValidationError(
            f"topik_hash harus berupa hex string 16 karakter. "
            f"Diterima: '{topik_hash}'. "
            f"Gunakan nilai dari field 'data.topik_hash' di response /start-simulation."
        )

    if label_aktual not in VALID_LABELS:
        valid_str = ", ".join(sorted(VALID_LABELS))
        raise FeedbackValidationError(
            f"Label '{label_aktual}' tidak valid. Pilih salah satu: {valid_str}."
        )
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        raise FeedbackValidationError(
            f"Field 'confidence' harus antara 0.0 dan 1.0, diterima: {confidence}."
        )
    if len(catatan) > 1000:
        raise FeedbackValidationError("Field 'catatan' maksimal 1000 karakter.")

    entry = {
        "topik_hash":   topik_hash,
        "topik":        f"[hash-only:{topik_hash}]",  # placeholder — tidak perlu plain text
        "label_aktual": label_aktual,
        "confidence":   round(float(confidence), 4),
        "catatan":      catatan.strip(),
        "timestamp":    _current_timestamp(),
    }

    with _feedback_lock:
        existing = _load_all_feedback()

        action  = "created"
        for i, fb in enumerate(existing):
            if fb.get("topik_hash") == topik_hash:
                existing[i] = entry
                action = "updated"
                break
        else:
            existing.append(entry)

        if len(existing) > MAX_FEEDBACK:
            existing = existing[-MAX_FEEDBACK:]

        _write_all_feedback(existing)

    stats   = get_feedback_stats()
    n_total = stats["total"]
    retrain_triggered = n_total >= MIN_FEEDBACK_TO_RETRAIN

    if retrain_triggered:
        t = threading.Thread(
            target=_trigger_retrain_background,
            args=(n_total,),
            daemon=True,
            name="feedback-retrain-hash",
        )
        t.start()

    return {**entry, "action": action, "retrain_triggered": retrain_triggered, "total_feedback": n_total}