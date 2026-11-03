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

_INVALID_KEY_MSG = (
    "API key Groq tidak valid atau sudah kedaluwarsa. "
    "Perbarui GROQ_API_KEY di file .env, lalu restart server."
)

# Cache hasil pengecekan koneksi — hindari ping API di setiap request.
_check_cache: dict = {"ts": 0.0, "ok": None, "msg": ""}
_check_lock = threading.Lock()
CHECK_TTL = 60  # detik


def check_llm_connection(force: bool = False) -> tuple[bool, str]:
    """
    Cek apakah Groq API bisa dipakai. Return (ok, pesan_error).

    Dipakai endpoint sebelum simulasi supaya request dengan API key invalid
    gagal cepat, bukan menghasilkan transkrip penuh teks error.
    Hasil di-cache CHECK_TTL detik agar tidak ping API tiap request.
    """
    global _check_cache

    with _check_lock:
        cache = _check_cache
        if (
            not force
            and cache["ok"] is not None
            and time.time() - cache["ts"] < CHECK_TTL
        ):
            return cache["ok"], cache["msg"]

    client = _get_client()
    if client is None:
        result = (False, "GROQ_API_KEY belum diisi. Tambahkan key Groq yang valid di .env, lalu restart server.")
    else:
        try:
            client.models.list()
            result = (True, "")
        except Exception as exc:
            err = str(exc)
            if "401" in err or "invalid_api_key" in err or "Invalid API Key" in err:
                result = (False, _INVALID_KEY_MSG)
            elif "429" in err or "rate_limit" in err.lower():
                # Key valid, cuma sedang kena limit — biarkan call_llm yang retry.
                result = (True, "")
            else:
                result = (False, f"Tidak dapat terhubung ke Groq API: {err[:160]}")

    with _check_lock:
        _check_cache = {"ts": time.time(), "ok": result[0], "msg": result[1]}
    return result


# ─── MODEL CONFIG ──────────────────────────────────────────────────────────
MODEL_AGENT    = os.getenv("MODEL_AGENT",    "llama-3.1-8b-instant")
MODEL_ANALYSIS = os.getenv("MODEL_ANALYSIS", "llama-3.3-70b-versatile")

# Fallback chain dipindahkan ke llm_guard.py (MODEL_CHAIN_AGENT, MODEL_CHAIN_ANALYSIS)

# ─── TOKEN BUDGET ──────────────────────────────────────────────────────────
MAX_TOKENS_AGENT     = int(os.getenv("MAX_TOKENS_AGENT",     "600"))  # 600 ≈ 400-450 kata BI = 5-6 kalimat penuh
MAX_TOKENS_RESPONSE  = int(os.getenv("MAX_TOKENS_RESPONSE",  "400"))
MAX_TOKENS_ANALYSIS  = int(os.getenv("MAX_TOKENS_ANALYSIS",  "1200"))
MAX_TOKENS_SUMMARY   = int(os.getenv("MAX_TOKENS_SUMMARY",   "100"))
MAX_TOKENS_SENTIMENT = int(os.getenv("MAX_TOKENS_SENTIMENT", "300"))

# ─── RATE LIMIT CONFIG ─────────────────────────────────────────────────────
# (Dipindahkan ke llm_guard.py: TPM_LIMIT, MODEL_CHAIN_AGENT, MODEL_CHAIN_ANALYSIS)
# AGENT_FALLBACK_CHAIN, RETRY_MAX, RETRY_BASE_DELAY tidak dipakai lagi.
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


def _cache_key(system_prompt: str, user_prompt: str, max_tokens: int, model: str, use_analysis_chain: bool = False) -> str:
    """Buat cache key dari hash SHA-256 parameter request."""
    raw = f"{model}|{max_tokens}|{use_analysis_chain}|{system_prompt}|{user_prompt}"
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
# call_llm: Thin wrapper ke llm_guard.chat() dengan cache in-memory
# ---------------------------------------------------------------------------

def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = MAX_TOKENS_RESPONSE,
    model: str = MODEL_ANALYSIS,
    use_analysis_chain: bool = False,
    use_cache: bool = True,
) -> str:
    """
    Panggil LLM via llm_guard (token budget, retry, model chain fallback).
    Hasil di-cache in-memory berdasarkan hash parameter.

    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        max_tokens: Max completion tokens
        model: Model preference (used for cache key; actual model from chain)
        use_analysis_chain: Jika True, pakai analysis chain (MODEL_CHAIN_ANALYSIS)
        use_cache: Jika False, skip cache (untuk opini agen agar tidak identik)
    """
    # ── Cache lookup (dengan TTL check) ──────────────────────────────────
    if use_cache:
        key = _cache_key(system_prompt, user_prompt, max_tokens, model, use_analysis_chain)
        with _llm_cache_lock:
            entry = _llm_cache.get(key)
            if entry is not None:
                expired = CACHE_TTL > 0 and (time.time() - entry["ts"]) > CACHE_TTL
                if expired:
                    del _llm_cache[key]
                else:
                    return entry["value"]
    else:
        key = None

    # ── Delegate ke llm_guard ────────────────────────────────────────────
    try:
        from .llm_guard import chat, chat_analysis

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if use_analysis_chain:
            text, used_model = chat_analysis(messages, max_tokens)
        else:
            text, used_model = chat(messages, max_tokens)

        # Auto-complete kalimat terpotong
        if text and text[-1] not in ".!?\"'":
            last_punct = max(
                text.rfind("."), text.rfind("!"), text.rfind("?")
            )
            if last_punct > len(text) * 0.5:
                text = text[:last_punct + 1]

        if use_cache and key is not None:
            with _llm_cache_lock:
                _llm_cache[key] = {"value": text, "ts": time.time()}
        return text

    except RuntimeError as e:
        err_str = str(e)
        if "401" in err_str or "invalid_api_key" in err_str:
            return f"[Error: {_INVALID_KEY_MSG}]"
        return f"[Error: {err_str[:120]}]"
    except Exception as e:
        return f"[Error: {str(e)[:120]}]"


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
    use_analysis_chain: bool = False,
) -> dict | list:
    """Panggil LLM, parse output JSON. Return {} jika gagal."""
    raw   = call_llm(system_prompt, user_prompt, max_tokens, model=model, use_analysis_chain=use_analysis_chain)
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
