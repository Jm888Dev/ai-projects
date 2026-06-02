# config.py
# All project constants live here. One file, one edit.
# Nothing is hardcoded in the piepline scripts.

# --- MODELS ---
# Sonnet for analyst calls - complex reasoning, supply chain signals
#Haiku for transaltor calls - plain English rewrite, fast and cheap
ANALYST_MODEL = "claude-sonnet-4-5"
TRANSLATOR_MODEL = "claude-haiku-4-5-20251001"

#--- TOKEN BUDGETS ---
# Analyst gets more tokens - structured JSON with multiple fields
# Transalator gets slightly less - plain Engklish is more concise
ANALYST_MAX_TOKENS = 1200
TRANSLATOR_MAX_TOKENS = 1000

#--- TEMPERATURE ---
# Lower = more factual and consistent. Right for financial analysis.
# Translator slightly higher - natural language benefits from variation.
ANALYST_TEMPERATURE = 0.2
TRANSLATOR_TEMPERATURE = 0.5

#--- TICKERS ---
# The full tracking universe. Edit this list to add or remvoe instruments.
# G3B.SI may return null outside SGX hours - handled in pipeline.
TICKERS = [
        "NVDA",     # Demand anchor - Nvidia
        "AVGO",     # Network gatekeeper - Broadcom
        "LITE",     # Photonics pure-play - Lumentum
        "TSM",      # Production floor - TSMC
        "QQQ",      # Masdaq-100 ETF
        "SMH",      # Semiconductor ETF
        "G3B.SI",   # STI ETF - local anchor
        "^VIX",     # Fear guage - macro signal
]
