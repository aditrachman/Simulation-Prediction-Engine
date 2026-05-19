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
# LLM Client & Model Config
# ---------------------------------------------------------------------------

def _build_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set on the server environment.")
    return Groq(api_key=api_key)


client = _build_client()

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
MAX_TOKENS_AGENT     = int(os.getenv("MAX_TOKENS_AGENT",     "350"))  # 350 ≈ 250-280 kata BI = 3-4 kalimat penuh, lebih stabil di model 8B
MAX_TOKENS_RESPONSE  = int(os.getenv("MAX_TOKENS_RESPONSE",  "400"))
MAX_TOKENS_ANALYSIS  = int(os.getenv("MAX_TOKENS_ANALYSIS",  "900"))
MAX_TOKENS_SUMMARY   = int(os.getenv("MAX_TOKENS_SUMMARY",   "100"))
MAX_TOKENS_SENTIMENT = int(os.getenv("MAX_TOKENS_SENTIMENT", "80"))

# ─── RATE LIMIT CONFIG ─────────────────────────────────────────────────────
RETRY_MAX         = int(os.getenv("RETRY_MAX",         "4"))
RETRY_BASE_DELAY  = float(os.getenv("RETRY_BASE_DELAY",  "5.0"))
AGENT_CALL_DELAY  = float(os.getenv("AGENT_CALL_DELAY",  "3.0"))   # dinaikkan dari 2.0 → kompensasi token lebih besar
ROUND_DELAY       = float(os.getenv("ROUND_DELAY",       "3.0"))
SOCIAL_TICK_DELAY = float(os.getenv("SOCIAL_TICK_DELAY", "1.0"))   # jeda antar tick sosmed
SENTIMENT_MODE    = os.getenv("SENTIMENT_MODE", "llm")             # "llm" (default, akurat) atau "inline" (hemat token)
CACHE_TTL         = int(os.getenv("CACHE_TTL",           "3600"))  # detik, default 1 jam; 0 = cache selamanya
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

    last_error = ""

    for current_model in chain:
        for attempt in range(RETRY_MAX):
            try:
                resp = client.chat.completions.create(
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


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    model: str = MODEL_ANALYSIS,
) -> dict | list:
    """Panggil LLM, parse output JSON. Return {} jika gagal."""
    raw   = call_llm(system_prompt, user_prompt, max_tokens, model=model)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}|\[.*\]", clean, re.DOTALL)
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