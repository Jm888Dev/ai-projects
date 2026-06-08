# config.py
# All project constants live here. One file, one edit.
# Nothing is hardcoded in the pipeline scripts.

# ── DATA MODE ──────────────────────────────────────────────
# False = read from fixtures (development, prompt tuning, testing)
# True  = fetch from live sources (real sessions, demo, production)
# Change this one line to switch modes — nothing else changes.
USE_LIVE_DATA = False

# ── SIX-AGENT MODEL ROUTING ────────────────────────────────
# Stage 1: Bull, Bear, Black Swan, Pragmatist — extreme positions,
#          small focused inputs, Haiku is fast and sufficient
# Stage 2: Contrarian — reads all four Stage 1 outputs, needs
#          Sonnet's synthesis depth
# Stage 3: Meta-Agent — deterministic decision maker, Sonnet
# Translator: plain English briefing, Haiku is fine
# Fallback: used by call_llm() if primary model fails
STAGE_1_MODEL    = "claude-haiku-4-5-20251001"
STAGE_2_MODEL    = "claude-sonnet-4-6"
STAGE_3_MODEL    = "claude-sonnet-4-6"
TRANSLATOR_MODEL = "claude-haiku-4-5-20251001"
FALLBACK_MODEL   = "claude-haiku-4-5-20251001"

# Kept for backward compatibility with existing call_llm() calls
# in stock_monitor.py — will be removed on Day 10 refactor
ANALYST_MODEL    = "claude-sonnet-4-6"

# ── TOKEN BUDGETS ──────────────────────────────────────────
# Stage 1 agents: tight — structured JSON, focused output
# Stage 2/3: more room — synthesis across multiple inputs
# Translator: concise plain English
STAGE_1_MAX_TOKENS    = 800
STAGE_2_MAX_TOKENS    = 1200
STAGE_3_MAX_TOKENS    = 1200
TRANSLATOR_MAX_TOKENS = 1000

# Kept for backward compatibility
ANALYST_MAX_TOKENS = 1200

# ── TEMPERATURE ────────────────────────────────────────────
# Stage 1 high — extreme committed positions, no hedging
# Stage 2 high — paradox hunting, creative challenge
# Stage 3 very low — deterministic, auditable decision
# Translator mid — natural language variation
STAGE_1_TEMPERATURE    = 0.6
STAGE_2_TEMPERATURE    = 0.7
STAGE_3_TEMPERATURE    = 0.1
TRANSLATOR_TEMPERATURE = 0.5

# Kept for backward compatibility
ANALYST_TEMPERATURE = 0.2

# ── TICKERS ────────────────────────────────────────────────
# Dict format: ticker → instrument_type
# instrument_type stored in DB and tells Claude what kind of
# instrument it is reasoning about
# Values: equity, etf, index, fx, yield
TICKERS = {
    "NVDA":   "equity",  # Demand anchor — Nvidia
    "AVGO":   "equity",  # Network gatekeeper — Broadcom
    "LITE":   "equity",  # Photonics pure-play — Lumentum
    "TSM":    "equity",  # Production floor — TSMC
    "QQQ":    "etf",     # Nasdaq-100 ETF
    "SMH":    "etf",     # Semiconductor ETF
    "G3B.SI": "etf",     # STI ETF — local anchor
    "^VIX":   "index",   # Fear gauge — macro signal
}

# ── DATABASE ───────────────────────────────────────────────
DB_PATH = "prices.db"

# ── MODEL PRICING ──────────────────────────────────────────
# Per-million-token pricing in USD
# Read by compute_call_cost() at insert time — stored permanently
# with each llm_calls row so historical cost data stays accurate
# even if pricing changes later
# Source: Anthropic public rates, June 2026
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
    "claude-opus-4-8":           {"input": 5.00, "output": 25.00},
}