# backend/llm.py
# LLM client, konfigurasi model, in-memory cache, call_llm, call_llm_json.
#
# Semua fungsi yang berhubungan langsung dengan pemanggilan Groq API
# dikumpulkan di sini agar modul lain cukup import dari satu tempat.

import os
import re
import json
import time
import random
import hashlib
import threading

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


# ---------------------------------------------------------------------------
# LLM Client & Model Config — lazy initialization
# ---------------------------------------------------------------------------

_client_instance: Groq | None = None
_client_init_lock = threading.Lock()


def _get_client() -> Groq | None:
    """
    BUG #5 FIX: Lazy client initialization — server tetap jalan meski
    API key tidak valid/kosong. Endpoints akan fallback ke mode offline.
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    with _client_init_lock:
        if _client_instance is not None:
            return _client_instance
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("[LLM] GROQ_API_KEY tidak ditemukan — mode offline.")
            return None
        try:
            _client_instance = Groq(api_key=api_key)
            return _client_instance
        except Exception as exc:
            print(f"[LLM] Gagal inisialisasi Groq client: {exc}")
            return None

# ─── MODEL CONFIG ──────────────────────────────────────────────────────────
MODEL_AGENT    = os.getenv("MODEL_AGENT",    "llama-3.1-8b-instant")
MODEL_ANALYSIS = os.getenv("MODEL_ANALYSIS", "llama-3.3-70b-versatile")

# Fallback chain: jika 429 dan retry habis, coba model berikutnya
AGENT_FALLBACK_CHAIN = [
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "llama-3.2-3b-preview",
]

# ─── TOKEN BUDGET ──────────────────────────────────────────────────────────
MAX_TOKENS_AGENT     = int(os.getenv("MAX_TOKENS_AGENT",     "600"))  # 600 ≈ 400-450 kata BI = 5-6 kalimat penuh
MAX_TOKENS_RESPONSE  = int(os.getenv("MAX_TOKENS_RESPONSE",  "400"))
MAX_TOKENS_ANALYSIS  = int(os.getenv("MAX_TOKENS_ANALYSIS",  "1200"))
MAX_TOKENS_SUMMARY   = int(os.getenv("MAX_TOKENS_SUMMARY",   "100"))
MAX_TOKENS_SENTIMENT = int(os.getenv("MAX_TOKENS_SENTIMENT", "300"))

# ─── RATE LIMIT CONFIG ─────────────────────────────────────────────────────
RETRY_MAX         = int(os.getenv("RETRY_MAX",         "4"))
RETRY_BASE_DELAY  = float(os.getenv("RETRY_BASE_DELAY",  "5.0"))
AGENT_CALL_DELAY  = float(os.getenv("AGENT_CALL_DELAY",  "3.0"))   # dinaikkan dari 2.0 → kompensasi token lebih besar
ROUND_DELAY       = float(os.getenv("ROUND_DELAY",       "3.0"))
SENTIMENT_MODE    = os.getenv("SENTIMENT_MODE", "llm")             # "ml" (deterministik), "llm" (akurat), atau "inline" (hemat token)
CACHE_TTL         = int(os.getenv("CACHE_TTL",           "3600"))  # detik, default 1 jam; 0 = cache selamanya

FREE_TIER_MODE = os.getenv("FREE_TIER_MODE", "false").lower() in {"1", "true", "yes", "on"}
DISABLE_GRAPH_LLM = (
    FREE_TIER_MODE
    or os.getenv("DISABLE_GRAPH_LLM", "false").lower() in {"1", "true", "yes", "on"}
)
DISABLE_FINAL_ANALYSIS_LLM = (
    FREE_TIER_MODE
    or os.getenv("DISABLE_FINAL_ANALYSIS_LLM", "false").lower() in {"1", "true", "yes", "on"}
)
# ───────────────────────────────────────────────────────────────────────────


# ---------------------------------------------------------------------------
# In-Memory LLM Cache (dengan TTL)
# ---------------------------------------------------------------------------
# Format entry: {"value": str, "ts": float}
# Entry dianggap stale jika (now - ts) > CACHE_TTL detik (kecuali CACHE_TTL == 0).

_llm_cache: dict[str, dict] = {}
_llm_cache_lock = threading.Lock()


def _cache_key(system_prompt: str, user_prompt: str, max_tokens: int, model: str) -> str:
    """Buat cache key dari hash SHA-256 parameter request."""
    raw = f"{model}|{max_tokens}|{system_prompt}|{user_prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clear_llm_cache() -> int:
    """
    Hapus seluruh isi LLM cache.
    Return jumlah entry yang dihapus.
    Berguna untuk testing atau manual flush saat topik berulang dengan konteks baru.
    """
    with _llm_cache_lock:
        count = len(_llm_cache)
        _llm_cache.clear()
    return count


# ---------------------------------------------------------------------------
# call_llm: Retry Exponential Backoff + Model Fallback
# ---------------------------------------------------------------------------

def _parse_retry_after(err_str: str) -> float | None:
    """Parse waktu tunggu dari pesan error Groq: 'try again in 4.44s'"""
    m = re.search(r"try again in ([\d.]+)s", err_str)
    if m:
        try:
            return float(m.group(1)) + 0.5  # buffer 0.5s
        except ValueError:
            pass
    return None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = MAX_TOKENS_RESPONSE,
    model: str = MODEL_ANALYSIS,
) -> str:
    """
    Panggil LLM dengan retry otomatis saat 429.

    - Retry hingga RETRY_MAX kali, jeda eksponensial: 5s, 10s, 20s, 40s
    - Jika model ada di AGENT_FALLBACK_CHAIN dan semua retry habis,
      coba model berikutnya dalam chain
    - Jitter random +0-2s untuk hindari thundering herd
    - Hasil di-cache in-memory berdasarkan hash parameter
    """
    # ── Cache lookup (dengan TTL check) ──────────────────────────────────
    key = _cache_key(system_prompt, user_prompt, max_tokens, model)
    with _llm_cache_lock:
        entry = _llm_cache.get(key)
        if entry is not None:
            expired = CACHE_TTL > 0 and (time.time() - entry["ts"]) > CACHE_TTL
            if expired:
                del _llm_cache[key]   # hapus entry stale, lanjut ke LLM call
            else:
                return entry["value"]
    # ─────────────────────────────────────────────────────────────────────

    if model in AGENT_FALLBACK_CHAIN:
        idx   = AGENT_FALLBACK_CHAIN.index(model)
        chain = AGENT_FALLBACK_CHAIN[idx:]
    else:
        chain = [model]

    # BUG #5 FIX: Cek ketersediaan client sebelum request
    groq_client = _get_client()
    if groq_client is None:
        return "[Offline] Groq API tidak tersedia (GROQ_API_KEY tidak dikonfigurasi). Gunakan mode free_tier atau SENTIMENT_MODE=inline."

    last_error = ""

    for current_model in chain:
        for attempt in range(RETRY_MAX):
            try:
                resp = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    model=current_model,
                    temperature=0.5,
                    max_tokens=max_tokens,
                )
                result = resp.choices[0].message.content.strip()
                # Auto-complete kalimat terpotong: potong di kalimat terakhir yang lengkap
                if result and result[-1] not in ".!?\"'":
                    last_punct = max(
                        result.rfind("."), result.rfind("!"), result.rfind("?")
                    )
                    if last_punct > len(result) * 0.5:  # ada kalimat lengkap di >50% teks
                        result = result[:last_punct + 1]
                with _llm_cache_lock:
                    _llm_cache[key] = {"value": result, "ts": time.time()}
                return result

            except Exception as e:
                err_str    = str(e)
                last_error = err_str

                is_rate_limit = (
                    "429"                in err_str or
                    "rate_limit_exceeded" in err_str or
                    "Rate limit"         in err_str
                )

                if is_rate_limit:
                    wait = _parse_retry_after(err_str) or (RETRY_BASE_DELAY * (2 ** attempt))
                    wait += random.uniform(0, 2)

                    if attempt < RETRY_MAX - 1:
                        print(f"[RateLimit] {current_model} — retry {attempt+1}/{RETRY_MAX}, tunggu {wait:.1f}s...")
                        time.sleep(wait)
                    else:
                        print(f"[RateLimit] {current_model} — semua retry habis, coba fallback...")
                        break  # ke model berikutnya
                else:
                    # Bukan rate limit — langsung return error
                    return f"[Error: {err_str[:120]}]"

    return f"[RateLimit] Semua model habis. Error: {last_error[:120]}"


def _repair_truncated_json(text: str) -> str | None:
    """Coba perbaiki JSON yang terpotong di akhir (model 8B sering output incomplete)."""
    # Cari blok JSON (dengan atau tanpa kurung tutup)
    m = re.search(r"\{.*", text, re.DOTALL)  # { sampai akhir
    if not m:
        return None
    candidate = m.group()

    # Jika JSON valid, return as-is
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass

    # Tutup kurung kurawal jika lupa
    if candidate.count("{") > candidate.count("}"):
        candidate += "}"
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Perbaiki angka terpotong di akhir: "skor":-0. → "skor":-0.0
    # Cari pola ": angka.(tanpa digit setelah titik)"
    candidate_orig = candidate
    candidate = re.sub(r':\s*(-?\d+)\.\s*\}$', r':\1.0}', candidate)
    if candidate != candidate_orig:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Fallback: jika ada "label" dan "skor", ekstrak pakai regex
    label_m = re.search(r'"label"\s*:\s*"(positif|netral|negatif)"', candidate, re.IGNORECASE)
    skor_m = re.search(r'"skor"\s*:\s*(-?[\d.]+)', candidate)
    if label_m:
        label = label_m.group(1).lower()
        skor = float(skor_m.group(1)) if skor_m else 0.0
        return json.dumps({"label": label, "skor": max(-1.0, min(1.0, skor))})

    return None


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    model: str = MODEL_ANALYSIS,
) -> dict | list:
    """Panggil LLM, parse output JSON. Return {} jika gagal."""
    raw   = call_llm(system_prompt, user_prompt, max_tokens, model=model)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    # Coba parse langsung
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # Coba repair JSON truncated
    repaired = _repair_truncated_json(clean)
    if repaired is not None:
        return json.loads(repaired)
    # Fallback: regex cari {...} terakhir
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Emoji Stripper — shared utility, digunakan simulation.py & social_engine.py
# ---------------------------------------------------------------------------

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937"
    "\U00010000-\U0010ffff"
    "\u2640-\u2642"
    "\u2600-\u2B55"
    "\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(teks: str) -> str:
    """Hapus emoji/unicode non-standar dari teks analisis."""
    if not teks:
        return ""
    hasil = _EMOJI_PATTERN.sub("", teks)
    return re.sub(r"  +", " ", hasil).strip()
