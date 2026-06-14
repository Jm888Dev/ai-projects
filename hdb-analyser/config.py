# config.py — hdb-analyser
# All project constants live here. One file, one edit.

# ── MODELS ──
# Sonnet for analyst calls — complex buyer reasoning, MAS rules, lease flags
# Haiku for translator calls — plain English rewrite, fast and cheap
ANALYST_MODEL = "claude-sonnet-4-5"
TRANSLATOR_MODEL = "claude-haiku-4-5-20251001"

# ── TOKEN BUDGETS ──
# Analyst: per-section budget — each of 7 sections gets its own call
# Translator: per-section budget — already working this way
ANALYST_MAX_TOKENS = 1000
TRANSLATOR_MAX_TOKENS = 600
TRANSLATOR_SECTION_TOKENS = {
    "summary":             400,   # 3 sentences — tight budget intentional
    "what_its_worth":      900,   # Detailed market explanation
    "lease_explained":     900,   # Complex concept, needs analogies
    "location_and_floor":  900,   # Multi-factor explanation
    "watch_out_for":       900,   # Critical red flags — must be complete
    "grant_and_financing": 1200,  # Most complex section — financing rules
    "before_you_decide":   600,   # One question with explanation
    "next_steps":          600,   # Numbered action list — one sentence per step
}


# ── TEMPERATURE ──
ANALYST_TEMPERATURE = 0.2
TRANSLATOR_TEMPERATURE = 0.5

# ── DATA SOURCE ──
# data.gov.sg API — HDB resale transaction data
# Update here if the endpoint or resource ID ever changes
API_BASE_URL = "https://data.gov.sg/api/action/datastore_search"
HDB_RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"

# ── FETCH & SAMPLE SETTINGS ──
# FETCH_LIMIT — how many raw records to pull from the API
# SAMPLE_SIZE — how many get passed to Claude after filtering
FETCH_LIMIT = 500
SAMPLE_SIZE = 20

# ── ANALYST SECTIONS ──
# The seven concerns the analyst reasons across — one Claude call each.
# Order matters — lease and financing flags inform the final top picks.
ANALYST_SECTIONS = [
    "value_assessment",
    "lease_flag",
    "financing_assessment",
    "upfront_costs",
    "location_signal",
    "red_flags",
    "top_picks",
]

# ── TRANSLATOR SECTIONS ──
# The seven buyer-facing sections — one Claude call each.
# These map to HDB_SECTION_PROMPTS in analyst_persona.py.
TRANSLATOR_SECTIONS = [
    "summary",
    "what_its_worth",
    "lease_explained",
    "location_and_floor",
    "watch_out_for",
    "grant_and_financing",
    "before_you_decide",
    "next_steps",
]

# ── FILTERING & SAMPLING ──
# These are the default query parameters for the buyer analysis.
# On Day 21 these become conversational inputs from the buyer —
# hardcoded here as sensible defaults until the agentic layer exists.
DEFAULT_TOWN = "SENGKANG"
DEFAULT_FLAT_TYPE = "4 ROOM"
SAMPLE_SIZE = 20

# ── API SETTINGS ──
# Request timeout in seconds — prevents the pipeline hanging
# on a slow data.gov.sg response.
REQUEST_TIMEOUT = 15

# ── ANALYST SECTION DEPENDENCIES ──
# Defines which prior section results each section needs as context.
# Sections not listed receive only raw transaction data — no accumulation.
# Keeps token usage controlled — each section gets exactly what it needs,
# nothing more. Surgical context passing, not blind accumulation.
ANALYST_SECTION_DEPENDENCIES = {
    "upfront_costs": [
        "financing_assessment",           # Needs loan and downpayment figures
    ],
    "red_flags": [
        "value_assessment",               # Needs pricing picture
        "lease_flag",                     # Needs lease risk assessment
        "financing_assessment",           # Needs loan and cash constraints
        "upfront_costs",                  # Needs total cash required
        "location_signal",                # Needs liveability concerns
    ],
    "top_picks": [
        "value_assessment",               # Needs pricing context
        "lease_flag",                     # Must exclude lease-trapped units
        "financing_assessment",           # Needs affordability picture
        "upfront_costs",                  # Needs cash requirement
        "location_signal",               # Needs floor and town signals
        "red_flags",                      # Must factor in all warnings
    ],
}
