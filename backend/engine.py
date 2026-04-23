# backend/engine.py
# Compatibility shim — semua kode lama yang import dari backend.engine
# (main.py, social_engine.py, dsb.) tetap berjalan tanpa perubahan.
#
# Implementasi sudah dipindahkan ke modul-modul terpisah:
#   backend/llm.py        — LLM client, config, cache, call_llm, call_llm_json
#   backend/memory.py     — memory update, summarization, context builders
#   backend/sentiment.py  — score_sentiment (inline & LLM mode)
#   backend/graph.py      — extract_entities (GraphRAG-lite)
#   backend/simulation.py — run_simulation, analyze_key_actors, helpers

# ── LLM ─────────────────────────────────────────────────────────────────────
from .llm import (
    client,
    MODEL_AGENT,
    MODEL_ANALYSIS,
    AGENT_FALLBACK_CHAIN,
    MAX_TOKENS_AGENT,
    MAX_TOKENS_RESPONSE,
    MAX_TOKENS_ANALYSIS,
    MAX_TOKENS_SUMMARY,
    MAX_TOKENS_SENTIMENT,
    RETRY_MAX,
    RETRY_BASE_DELAY,
    AGENT_CALL_DELAY,
    ROUND_DELAY,
    SENTIMENT_MODE,
    call_llm,
    call_llm_json,
)

# ── Memory ───────────────────────────────────────────────────────────────────
from .memory import (
    update_agent_memory,
    summarize_memory,
    build_memory_context,
    build_influence_context,
)

# ── Sentiment ────────────────────────────────────────────────────────────────
from .sentiment import score_sentiment

# ── Graph ────────────────────────────────────────────────────────────────────
from .graph import extract_entities

# ── Simulation ───────────────────────────────────────────────────────────────
from .simulation import (
    run_simulation,
    analyze_key_actors,
)

__all__ = [
    # llm
    "client",
    "MODEL_AGENT", "MODEL_ANALYSIS", "AGENT_FALLBACK_CHAIN",
    "MAX_TOKENS_AGENT", "MAX_TOKENS_RESPONSE", "MAX_TOKENS_ANALYSIS",
    "MAX_TOKENS_SUMMARY", "MAX_TOKENS_SENTIMENT",
    "RETRY_MAX", "RETRY_BASE_DELAY", "AGENT_CALL_DELAY", "ROUND_DELAY",
    "SENTIMENT_MODE",
    "call_llm", "call_llm_json",
    # memory
    "update_agent_memory", "summarize_memory",
    "build_memory_context", "build_influence_context",
    # sentiment
    "score_sentiment",
    # graph
    "extract_entities",
    # simulation
    "run_simulation", "analyze_key_actors",
]