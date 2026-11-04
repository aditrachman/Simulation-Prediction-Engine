# backend/llm_guard.py
# Lapis pemanggilan LLM terpusat: token budget (TPM), model chain, retry, fallback.
# Menggantikan logika retry/fallback yang tersebar di llm.py & simulation.py.

import os
import time
import threading
import random
import logging
from collections import deque
from typing import Optional

from groq import Groq, RateLimitError

logger = logging.getLogger(__name__)

# ── Konfigurasi dari env ─────────────────────────────────────────────────────
_client: Optional[Groq] = None
_client_lock = threading.Lock()

CHAIN = [m.strip() for m in os.getenv(
    "MODEL_CHAIN_AGENT",
    "openai/gpt-oss-20b,openai/gpt-oss-120b,qwen/qwen3.8-27b"
).split(",")]

ANALYSIS_CHAIN = [m.strip() for m in os.getenv(
    "MODEL_CHAIN_ANALYSIS",
    "openai/gpt-oss-120b,qwen/qwen3.8-27b"
).split(",")]

TPM_LIMIT = int(os.getenv("TPM_LIMIT", "7000"))  # margin di bawah 8K free tier

# Batas request per menit, dibagi semua panggilan di proses ini.
RPM_LIMIT = int(os.getenv("RPM_LIMIT", "30"))


def _get_client() -> Groq:
    """Lazy Groq client initialization (thread-safe)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY tidak diset")
        _client = Groq(api_key=api_key)
        return _client


# ── Token Budget per model (thread-safe) ────────────────────────────────────
class TokenBudget:
    """Sliding-window token budget per model (60 detik)."""

    def __init__(self, tpm: int):
        self.tpm = tpm
        self.events: deque[tuple[float, int]] = deque()  # (timestamp, tokens)
        self.lock = threading.Lock()
        self.waited = 0.0  # total detik menunggu budget (dibaca untuk metrik)

    def acquire(self, estimated_tokens: int) -> list:
        """Block sampai budget cukup. Return entry [ts, est] untuk di-settle nanti."""
        while True:
            with self.lock:
                now = time.time()
                # hapus event > 60 detik
                while self.events and now - self.events[0][0] > 60:
                    self.events.popleft()
                used = sum(t for _, t in self.events)
                if used + estimated_tokens <= self.tpm or not self.events:
                    entry = [now, estimated_tokens]
                    self.events.append(entry)
                    return entry
                wait = 60 - (now - self.events[0][0]) + 0.2
            tidur = max(wait, 0.5)
            time.sleep(tidur)
            with self.lock:
                self.waited += tidur

    def settle(self, entry: list, actual_tokens: int) -> None:
        """Ganti estimasi dengan actual usage."""
        with self.lock:
            entry[1] = actual_tokens


_budgets: dict[str, TokenBudget] = {}
_budgets_lock = threading.Lock()


def _budget(model: str) -> TokenBudget:
    # Lock agar dua thread tidak membuat dua budget terpisah untuk model yang sama.
    with _budgets_lock:
        return _budgets.setdefault(model, TokenBudget(TPM_LIMIT))


# ── Rate limiter RPM (jendela 60 detik, dibagi semua panggilan) ──────────────
class RateLimiter:
    """Batas jumlah request per 60 detik. Thread-safe."""

    def __init__(self, rpm: int):
        self.rpm = max(1, rpm)
        self.calls: deque[float] = deque()
        self.lock = threading.Lock()

    def acquire(self) -> float:
        """Block sampai ada slot. Return detik yang dihabiskan menunggu."""
        total = 0.0
        while True:
            with self.lock:
                now = time.time()
                while self.calls and now - self.calls[0] > 60:
                    self.calls.popleft()
                if len(self.calls) < self.rpm:
                    self.calls.append(now)
                    return total
                wait = 60 - (now - self.calls[0]) + 0.05
            tidur = max(wait, 0.05)
            time.sleep(tidur)
            total += tidur


_limiter = RateLimiter(RPM_LIMIT)


# ── Metrik per run (dibaca simulation.py sebelum/sesudah run) ────────────────
_metrics_lock = threading.Lock()
_metrics = {
    "calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "rate_limited_429": 0,
    "budget_wait": 0.0,
    "rpm_wait": 0.0,
}


def metrics() -> dict:
    """Snapshot metrik pemanggilan LLM sejak reset terakhir."""
    with _metrics_lock:
        return dict(_metrics)


def reset_metrics() -> None:
    with _metrics_lock:
        for k in _metrics:
            _metrics[k] = 0 if isinstance(_metrics[k], int) else 0.0


def _tambah(nama: str, nilai) -> None:
    with _metrics_lock:
        _metrics[nama] += nilai


# ── Fungsi utama: chat() ────────────────────────────────────────────────────
def chat(
    messages: list[dict],
    max_tokens: int,
    chain: Optional[list[str]] = None,
    reasoning_effort: str = "low",
    temperature: float = 0.8,
    response_format: Optional[dict] = None,
) -> tuple[str, str]:
    """
    Panggil LLM dengan token budget, retry, dan model chain fallback.

    Returns:
        (text, model_used)

    Raises:
        RuntimeError: jika semua model gagal (rate limit TPD, respons kosong, dsb)
    """
    chain = chain or CHAIN
    est_in = sum(len(m.get("content", "")) for m in messages) // 3  # rough char→token
    last_err: Optional[Exception] = None

    for model in chain:
        for attempt in range(3):
            tambah = _limiter.acquire()
            if tambah:
                _tambah("rpm_wait", tambah)
            budget = _budget(model)
            menunggu = budget.waited
            entry = budget.acquire(est_in + max_tokens)
            _tambah("budget_wait", budget.waited - menunggu)
            _tambah("calls", 1)
            start = time.time()
            try:
                kw = dict(
                    model=model,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    temperature=temperature,
                )
                if model.startswith("openai/gpt-oss"):
                    kw["reasoning_effort"] = reasoning_effort
                if response_format is not None:
                    kw["response_format"] = response_format

                resp = _get_client().chat.completions.create(**kw)
                actual = resp.usage.total_tokens
                _budget(model).settle(entry, actual)
                _tambah("prompt_tokens", getattr(resp.usage, "prompt_tokens", 0) or 0)
                _tambah("completion_tokens", getattr(resp.usage, "completion_tokens", 0) or 0)

                text = (resp.choices[0].message.content or "").strip()
                dur = time.time() - start

                # Logging satu baris, tanpa isi prompt
                logger.info(
                    "[LLM] model=%s tokens=%d (est=%d) duration=%.2fs",
                    model, actual, est_in + max_tokens, dur
                )

                if text:
                    return text, model

                last_err = RuntimeError(f"{model}: respons kosong")
                # respons kosong → coba model berikutnya (break inner loop)
                break

            except RateLimitError as e:
                last_err = e
                _tambah("rate_limited_429", 1)
                err_str = str(e)
                # TPD / daily limit → langsung ganti model, jangan retry
                if "per day" in err_str or "TPD" in err_str or "daily" in err_str.lower():
                    logger.warning("[LLM] %s: TPD limit, switch model", model)
                    break
                # TPM / per-minute → retry dengan backoff
                wait = min(5 * 2 ** attempt, 30) + random.random()
                logger.warning("[LLM] %s: rate limit, retry %d/3 wait %.1fs", model, attempt + 1, wait)
                time.sleep(wait)

            except Exception as e:
                last_err = e
                logger.error("[LLM] %s: error %s", model, e)
                break  # error non-rate-limit → coba model berikutnya

    raise RuntimeError(f"Semua model gagal: {last_err}")


# ── Helper untuk analisis (chain terpisah, reasoning medium) ────────────────
def chat_analysis(messages: list[dict], max_tokens: int) -> tuple[str, str]:
    """Wrapper untuk panggilan analisis: pakai ANALYSIS_CHAIN + reasoning medium."""
    return chat(messages, max_tokens, chain=ANALYSIS_CHAIN, reasoning_effort="medium", temperature=0.5)


# ── Test utilities (mock client) ────────────────────────────────────────────
# Dipakai hanya saat pytest. Import di test file, bukan di production.
class MockGroq:
    """Mock client untuk test llm_guard tanpa network.
    
    Structure mimics Groq client: client.chat.completions.create()
    """

    def __init__(self, responses: dict[str, list[tuple[str, Optional[Exception]]]]):
        """
        responses: {model: [(text_or_None, exception_or_None), ...]}
        Sequence per model. Exception = RateLimitError("try again in 1.5s") untuk test retry.
        """
        self.responses = responses
        self.call_count: dict[str, int] = {}

        # Build the nested structure: client.chat.completions.create
        self.chat = type('Chat', (), {})()
        self.chat.completions = type('Completions', (), {})()
        self.chat.completions.create = self._create_mock

    def _create_mock(self, model: str, messages: list, max_completion_tokens: int, **kwargs):
        self.call_count[model] = self.call_count.get(model, 0) + 1
        idx = self.call_count[model] - 1
        seq = self.responses.get(model, [])
        if idx >= len(seq):
            # default: success
            text = "OK"
            exc = None
        else:
            text, exc = seq[idx]
        if exc:
            raise exc

        class Resp:
            class Choice:
                class Message:
                    content = text
                message = Message()
            choices = [Choice()]

            class Usage:
                prompt_tokens = max_completion_tokens
                completion_tokens = 50
                total_tokens = max_completion_tokens + 50
            usage = Usage()

        return Resp()


def _install_mock_client(mock: MockGroq) -> None:
    """Replace global _client dengan mock (untuk test)."""
    global _client
    _client = mock  # type: ignore


def _restore_real_client() -> None:
    """Restore real Groq client (reset ke None untuk lazy init)."""
    global _client
    _client = None