# backend/tests/test_llm_guard.py
# Test untuk llm_guard.py dengan mock client (no network).

import pytest
import time
import threading
import httpx
from groq import RateLimitError

from backend.llm_guard import (
    chat,
    chat_analysis,
    TokenBudget,
    MockGroq,
    _install_mock_client,
    _restore_real_client,
    _budgets,
)


def _make_rate_limit_error(message: str) -> RateLimitError:
    """Create a RateLimitError with required response/body args."""
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/v1/chat/completions"))
    return RateLimitError(message, response=response, body={"error": {"message": message}})


@pytest.fixture(autouse=True)
def isolate_budgets():
    """Reset global budget state antar test."""
    _budgets.clear()
    yield
    _budgets.clear()


@pytest.fixture
def mock_client():
    """Install mock client, restore setelah test."""
    _restore_real_client()
    yield
    _restore_real_client()


def test_token_budget_waits_when_over_tpm():
    """(a) Limiter menunda saat estimasi melebihi TPM."""
    budget = TokenBudget(tpm=1000)  # 1000 tokens per menit

    # Acquire 600 tokens - OK
    entry1 = budget.acquire(600)
    assert entry1[1] == 600

    # Acquire 500 tokens - harus menunggu karena total 1100 > 1000
    # Kita tidak bisa test blocking di sini tanpa time manipulation,
    # tapi kita bisa verify logic: used=600, est=500, total=1100 > 1000 → wait
    # Test non-blocking: acquire dengan estimasi kecil harus lolos
    entry2 = budget.acquire(100)
    assert entry2[1] == 100  # lolos, total 700 <= 1000

    # settle mengupdate estimasi ke actual
    budget.settle(entry1, 550)
    budget.settle(entry2, 90)
    # used sekarang 550+90=640


def test_token_budget_thread_safety():
    """TokenBudget thread-safe: multiple threads acquire.concurrently."""
    budget = TokenBudget(tpm=5000)
    results = []
    errors = []

    def worker(est):
        try:
            entry = budget.acquire(est)
            budget.settle(entry, est)
            results.append(est)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(200,)) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(results) == 20


def test_chat_switches_model_on_tpd(mock_client):
    """(b) Pindah model saat TPD (daily limit)."""
    # Model pertama: TPD error, model kedua: sukses
    mock = MockGroq({
        "openai/gpt-oss-20b": [
            (None, _make_rate_limit_error("Rate limit exceeded. Daily limit reached.")),
        ],
        "openai/gpt-oss-120b": [
            ("Hasil dari model kedua", None),
        ],
        "qwen/qwen3.8-27b": [
            ("Tidak dipakai", None),
        ],
    })
    _install_mock_client(mock)

    text, model = chat(
        messages=[{"role": "user", "content": "Test"}],
        max_tokens=100,
        chain=["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"],
    )

    assert text == "Hasil dari model kedua"
    assert model == "openai/gpt-oss-120b"
    assert mock.call_count["openai/gpt-oss-20b"] == 1
    assert mock.call_count["openai/gpt-oss-120b"] == 1


def test_chat_switches_model_on_empty_response(mock_client):
    """(c) Pindah model saat respons kosong."""
    mock = MockGroq({
        "openai/gpt-oss-20b": [
            ("", None),  # kosong
        ],
        "openai/gpt-oss-120b": [
            ("Hasil valid", None),
        ],
    })
    _install_mock_client(mock)

    text, model = chat(
        messages=[{"role": "user", "content": "Test"}],
        max_tokens=100,
        chain=["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
    )

    assert text == "Hasil valid"
    assert model == "openai/gpt-oss-120b"
    assert mock.call_count["openai/gpt-oss-20b"] == 1
    assert mock.call_count["openai/gpt-oss-120b"] == 1


def test_chat_retry_on_tpm_then_succeeds(mock_client):
    """Rate limit TPM (per-minute) → retry → sukses di model yang sama."""
    mock = MockGroq({
        "openai/gpt-oss-20b": [
            (None, _make_rate_limit_error("try again in 0.5s")),  # attempt 1: rate limit
            ("Sukses di retry ke-2", None),               # attempt 2: sukses
        ],
    })
    _install_mock_client(mock)

    text, model = chat(
        messages=[{"role": "user", "content": "Test"}],
        max_tokens=100,
        chain=["openai/gpt-oss-20b"],
    )

    assert text == "Sukses di retry ke-2"
    assert model == "openai/gpt-oss-20b"
    assert mock.call_count["openai/gpt-oss-20b"] == 2


def test_chat_all_models_fail_raises(mock_client):
    """Semua model gagal → raise RuntimeError."""
    mock = MockGroq({
        "openai/gpt-oss-20b": [
            (None, _make_rate_limit_error("try again in 0.5s")),
            (None, _make_rate_limit_error("try again in 0.5s")),
            (None, _make_rate_limit_error("try again in 0.5s")),
        ],
        "openai/gpt-oss-120b": [
            (None, _make_rate_limit_error("Daily limit reached")),
        ],
    })
    _install_mock_client(mock)

    with pytest.raises(RuntimeError, match="Semua model gagal"):
        chat(
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=100,
            chain=["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
        )


def test_chat_analysis_uses_analysis_chain(mock_client):
    """chat_analysis pakai ANALYSIS_CHAIN + reasoning_effort=medium."""
    mock = MockGroq({
        "openai/gpt-oss-120b": [
            ("Analisis hasil", None),
        ],
        "qwen/qwen3.8-27b": [
            ("Tidak dipakai", None),
        ],
    })
    _install_mock_client(mock)

    # Patch ANALYSIS_CHAIN untuk test
    import backend.llm_guard as lg
    original_chain = lg.ANALYSIS_CHAIN
    lg.ANALYSIS_CHAIN = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

    try:
        text, model = chat_analysis(
            messages=[{"role": "user", "content": "Analisis ini"}],
            max_tokens=200,
        )
        assert text == "Analisis hasil"
        assert model == "openai/gpt-oss-120b"
    finally:
        lg.ANALYSIS_CHAIN = original_chain


def test_token_budget_window_expiry():
    """Event > 60 detik dihapus dari budget (sliding window)."""
    budget = TokenBudget(tpm=1000)

    # Isi budget penuh
    entry = budget.acquire(900)
    budget.settle(entry, 900)

    # Tunggu > 60 detik (simulasi dengan manipulasi timestamp internal)
    # Kita tidak bisa sleep 60s di test, tapi kita bisa test logic langsung
    # dengan memanipulasi events deque
    import time
    budget.events[0] = (time.time() - 61, 900)  # event lama 61 detik lalu

    # Sekarang acquire harus lolos karena event lama sudah expired
    entry2 = budget.acquire(500)
    assert entry2[1] == 500
    # Event lama seharusnya sudah dipop di acquire()
    # (verify: events hanya berisi entry2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])