# config.py
# All project constants live here. One file, one edit.
# Nothing is hardcoded in the pipeline scripts.

# --- MODELS ---
# Sonnet for analyst calls — complex reasoning, supply chain signals
# Haiku for translator calls — plain English rewrite, fast and cheap
# Fallback used by call_llm() if the primary model fails
ANALYST_MODEL = "claude-sonnet-4-5"
TRANSLATOR_MODEL = "claude-haiku-4-5-20251001"
FALLBACK_MODEL = "claude-haiku-4-5-20251001"

# --- TOKEN BUDGETS ---
# Analyst gets more tokens — structured JSON with multiple fields
# Translator gets slightly less — plain English is more concise
ANALYST_MAX_TOKENS = 1200
TRANSLATOR_MAX_TOKENS = 1000

# --- TEMPERATURE ---
# Lower = more factual and consistent. Right for financial analysis.
# Translator slightly higher — natural language benefits from variation.
ANALYST_TEMPERATURE = 0.2
TRANSLATOR_TEMPERATURE = 0.5

# --- TICKERS ---
# Dict format: ticker → instrument_type.
# instrument_type is stored in the database and tells Claude
# what kind of instrument it is reasoning about.
# instrument_type values: equity, etf, index, fx, yield
TICKERS = {
    "NVDA":    "equity",  # Demand anchor — Nvidia
    "AVGO":    "equity",  # Network gatekeeper — Broadcom
    "LITE":    "equity",  # Photonics pure-play — Lumentum
    "TSM":     "equity",  # Production floor — TSMC
    "QQQ":     "etf",     # Nasdaq-100 ETF
    "SMH":     "etf",     # Semiconductor ETF
    "G3B.SI":  "etf",     # STI ETF — local anchor
    "^VIX":    "index",   # Fear gauge — macro signal
}

# --- DATABASE ---
# SQLite database file stored in the project folder.
# All price fetches, analyst outputs, signals, and audit rows written here.
DB_PATH = "prices.db"

# --- MODEL PRICING ---
# Per-million-token pricing in USD. Read by database.compute_call_cost()
# at the moment each llm_calls row is written.
# Pricing reference: Anthropic public rates, June 2026.
# Update here when prices change or new models are added.
# Format: model_id -> {"input": $/M input tokens, "output": $/M output tokens}
MODEL_PRICING = {
    "claude-sonnet-4-5":          {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001":  {"input": 1.00, "output": 5.00},
    # Opus added in advance — wired up if/when call_llm() routes to it
    "claude-opus-4-8":            {"input": 5.00, "output": 25.00},
}