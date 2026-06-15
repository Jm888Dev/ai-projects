# config.py
# All project constants live here. One file, one edit.
# Nothing is hardcoded in the pipeline scripts.

# Standard library imports — needed for thesis override loading
import json        # reads thesis_overrides.json at startup
import os          # builds file path relative to config.py location
from pathlib import Path  # builds fixture and env paths for shared/utils.py wrappers

# ── DATA AND AGENT MODE ────────────────────────────────────
#
# QUICK REFERENCE — MODE COMBINATIONS
#
# LIVE_DATA  LIVE_AGENTS  DEV_MODE  SCENARIO                            COST
# ─────────────────────────────────────────────────────────────────────────────
# False      False        True      Full fixture — build/test schema     $0.00
# True       False        True      Live prices + fixture agents          $0.00
# False      True         True      Fixture prices + live Haiku agents   ~$0.05
# False      True         False     Fixture prices + live Sonnet agents  ~$0.30
# True       True         True      Full live run — Haiku               ~$0.05
# True       True         False     Full live run — Sonnet, demo        ~$0.30
#
# CAPTURE FLAGS (only apply when corresponding LIVE flag is True)
# CAPTURE_LIVE_DATA_FOR_FIXTURES    — True = overwrite normal_day.json
# CAPTURE_LIVE_AGENTS_FOR_FIXTURES  — True = overwrite fixtures/agents/
# Set both False during prompt tuning to freeze your baseline.
#
# ─────────────────────────────────────────────────────────────────────────────
# USE_LIVE_DATA controls whether prices come from yfinance or
# from fixtures/normal_day.json.
# False = fixture prices — zero cost, instant, no network needed
# True  = live yfinance fetch — real prices, real session
USE_LIVE_DATA = False

# USE_LIVE_AGENTS controls whether agents call the Claude API
# or load pre-captured outputs from fixtures/agents/.
# False = fixture agents — zero API cost, instant, deterministic
# True  = live Claude API calls — real reasoning, real cost
USE_LIVE_AGENTS = False

# CAPTURE_LIVE_DATA_FOR_FIXTURES controls whether a live price
# fetch overwrites fixtures/normal_day.json.
# True  = fixtures stay fresh after every live run — default
# False = fixtures frozen — use during prompt tuning so your
#         price baseline does not shift between runs
CAPTURE_LIVE_DATA_FOR_FIXTURES = True

# CAPTURE_LIVE_AGENTS_FOR_FIXTURES controls whether live agent
# outputs overwrite fixtures/agents/ after each call.
# True  = agent fixtures stay fresh after every live run — default
# False = agent fixtures frozen — use during prompt tuning so
#         you can isolate prompt changes from output changes
CAPTURE_LIVE_AGENTS_FOR_FIXTURES = True

# ── DEV MODE ───────────────────────────────────────────────
# True  = all agents run on Haiku — fast, cheap, for building
#         and prompt development. Roughly $0.05-0.08 per run.
# False = full production routing — Haiku Stage 1, Sonnet Stage 2+3
#         Full reasoning quality. Roughly $0.50+ per run.
#
# Switch to False when:
#   - Running on live data for real sessions
#   - Tuning prompts against full-quality output
#   - Day 30 demo
# Switch to True when:
#   - Building new pipeline features
#   - Testing schema changes
#   - Iterating on agent prompts
#   - Any fixture run where output quality is not the focus
DEV_MODE = True

# ── SIX-AGENT MODEL ROUTING ────────────────────────────────
# Model constants — do not change these
_HAIKU  = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"
_OPUS   = "claude-opus-4-8"

# Stage routing — respects DEV_MODE
# Stage 1: Bull, Bear, Black Swan, Pragmatist
#   Always Haiku — extreme positions on focused inputs,
#   Haiku is sufficient regardless of mode
# Stage 2: Contrarian
#   Sonnet in production — synthesis across four inputs needs depth
#   Haiku in dev — acceptable for building and prompt iteration
# Stage 3: Meta-Agent
#   Sonnet in production — final portfolio decision, must be auditable
#   Haiku in dev — acceptable for building and schema testing
# Translator: always Haiku — plain English rewrite, no depth needed
# Fallback: always Haiku — fast recovery on primary failure
STAGE_1_MODEL    = _HAIKU # Stage 1 (Analyst)
STAGE_2_MODEL    = _HAIKU if DEV_MODE else _SONNET # Stage 2 (Contrarian) 
STAGE_3_MODEL    = _HAIKU if DEV_MODE else _SONNET # Stage 3 (Meta-Agent)
TRANSLATOR_MODEL = _HAIKU
FALLBACK_MODEL   = _HAIKU

# Kept for backward compatibility — removed on next refactor pass
ANALYST_MODEL = _SONNET

# ── TOKEN BUDGETS ──────────────────────────────────────────
# Raised after Day 10 first run — Black Swan, Pragmatist, and
# Contrarian were consistently hitting the ceiling and triggering
# retries. Higher budgets eliminate retries and reduce runtime.
STAGE_1_MAX_TOKENS    = 1200   # was 800 — Black Swan and Pragmatist need room
STAGE_2_MAX_TOKENS    = 2000   # was 1200 — Contrarian reads four inputs
STAGE_3_MAX_TOKENS    = 4000   # was 1500 — Meta-Agent covers eight tickers
TRANSLATOR_MAX_TOKENS = 2500   # was 1200 — needs room for 7-ticker briefing

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

# ── TICKER THESIS ──────────────────────────────────────────
# Static thesis context per ticker. Injected into every Stage 1
# agent's data package as Layer 2. Never changes run to run.
# Tells each agent the structural role of the ticker in the
# supply chain — not just what it is, but why it is in the
# portfolio and how it connects to everything else.
# Update here when your investment thesis changes.
TICKER_THESIS = {
    "NVDA": """
Role: Demand anchor of the AI semiconductor supply chain.

Thesis: Hyperscaler CapEx commitments drive GPU allocation cycles.
NVDA's revenue and guidance signal whether AI infrastructure
spending is accelerating or contracting. Blackwell architecture
cycle is the current primary catalyst. Sovereign AI demand from
non-US governments adds a new demand layer beyond hyperscalers.

Chain position: Upstream. NVDA demand pulls TSM production,
AVGO networking, and LITE photonics behind it. A sustained NVDA
revenue miss is a thesis-level event for the whole chain.

Concentration note: NVDA is a significant SMH component (~20%).
NVDA weakness propagates to SMH directly — these are not
independent positions.

Sizing: Thematic growth. Informed conviction. Not core stability.

Watch: Data centre revenue guidance, Blackwell allocation
announcements, export control exposure, AMD custom silicon gains,
hyperscaler capex revision signals.
""",

    "AVGO": """
Role: Network gatekeeper and custom silicon parallel path.

Thesis: As hyperscalers build custom AI chips to reduce NVDA
dependence, AVGO wins the custom chip design layer and the
networking infrastructure connecting AI clusters. AVGO's custom
ASIC pipeline with Google, Meta, and Apple is the decoupling
thesis — AVGO can strengthen while NVDA faces pressure.

Chain position: Parallel to NVDA, not downstream. AVGO and NVDA
serve different parts of the hyperscaler stack. AVGO networking
(Ethernet switching) is infrastructure that every AI cluster
needs regardless of GPU vendor.

Decoupling signal: AVGO rising while NVDA falls = hyperscaler
rotation toward custom silicon. This is a thesis confirmation
signal, not a contradiction.

Sizing: Thematic growth. Informed conviction.

Watch: Custom chip design win announcements, hyperscaler contract
renewals, Ethernet vs InfiniBand competitive signals, AVGO vs
NVDA divergence as a rotation indicator.
""",

    "LITE": """
Role: Photonics pure-play. The copper-to-light transition inside
data centres.

Thesis: As AI clusters scale beyond the bandwidth limits of copper
interconnects, optical interconnects become mandatory
infrastructure. LITE is the primary beneficiary of this
transition. The thesis only activates if NVDA demand and TSMC
production are both healthy upstream — LITE is a downstream bet
on the thesis holding.

Chain position: Downstream. Dependent on upstream chain health.
A sustained NVDA drawdown or TSMC capacity reduction is a
thesis-integrity threat for LITE before it is a price signal.

Sizing: Frontier bet. Small position. Higher volatility tolerance
than core or thematic holdings. Wrong sizing would be treating
this as a thematic growth position.

Watch: Data centre optical interconnect adoption signals, laser
optics order flow, NVDA cluster architecture announcements
(particularly Blackwell NVLink density), LITE earnings guidance
on hyperscaler customer concentration.
""",

    "TSM": """
Role: Production floor. Every advanced chip in the chain is
fabbed here.

Thesis: TSMC capacity constraints are the physical ceiling on AI
hardware scaling. CoWoS advanced packaging bookings are the
leading indicator of AI chip production volume. No TSMC, no
Blackwell. No Blackwell, no AI infrastructure. This is the
most operationally critical position in the chain.

Chain position: Midstream. Depends on NVDA and AVGO design wins
upstream. LITE photonics integration is the downstream signal.
TSMC is the chokepoint — capacity expansion timelines matter more
than quarterly earnings.

Geopolitical note: Taiwan Strait risk is a permanent structural
tail risk on this position. A Black Swan agent should weight
this structurally and consistently, not only when headlines are
active. The risk does not disappear when the news cycle moves on.

Currency note: TSM trades in USD as an ADR. SGD/USD rate affects
effective cost basis for a Singapore-based investor.

Sizing: Thematic growth. Core to the supply chain thesis.

Watch: CoWoS capacity utilisation and expansion timelines,
N2/A16 node ramp, geopolitical headlines, TSMC guidance on
AI vs smartphone vs HPC revenue mix.
""",

    "QQQ": """
Role: Nasdaq-100 exposure. Broad tech participation.

Thesis: The companies funding foundational AI — Microsoft, Google,
Apple, Meta, Amazon — are QQQ's largest components. QQQ rising
while SMH is flat or falling signals that the market is pricing
software and platform AI gains faster than hardware. This
divergence is a regime signal worth tracking.

Chain position: Parallel layer, not in the semiconductor chain.
QQQ represents the software and services layer benefiting from
AI adoption. It is a diversifier against semiconductor-specific
weakness, not a semiconductor position.

Divergence signal: QQQ outperforming SMH = software/platform
strength. SMH outperforming QQQ = hardware cycle strength.
Track the spread, not just the absolute levels.

Sizing: Core stability. RSP via StashAway. Berkshire patience.

Watch: QQQ vs SMH spread as software/hardware rotation signal,
hyperscaler earnings commentary on AI infrastructure spend
(as both a QQQ driver and an upstream signal for the chain).
""",

    "SMH": """
Role: Semiconductor ETF. Auto-diversified hardware exposure.

Thesis: Broad semiconductor cycle participation without
single-stock risk. SMH captures the hardware layer of the AI
thesis across the full ecosystem — design, manufacturing,
packaging, memory, and equipment.

Concentration note: SMH holds NVDA (~20%) and TSM (~10%) as
significant components. In a semiconductor downturn all three
move together — SMH does not provide meaningful diversification
against NVDA or TSM weakness. The diversification benefit is
real against idiosyncratic single-stock risk, not against
sector-wide pressure.

Signal use: SMH vs NVDA divergence is the most useful signal.
SMH dropping faster than NVDA = broader semiconductor weakness
beyond AI. NVDA dropping while SMH holds = NVDA-specific issue,
sector intact. Track the divergence, not just the levels.

Sizing: Core stability. RSP. Long-horizon.

Watch: SMH vs NVDA divergence, SMH vs QQQ spread (hardware vs
software cycle), semiconductor equipment orders as a leading
indicator for SMH direction.
""",

    "G3B.SI": """
Role: Local anchor. Singapore STI ETF. SGD-denominated stability.

Thesis: DBS, OCBC, UOB dividend income in SGD. Portfolio
stability when US markets are volatile. The key thesis assumption
is that G3B.SI moves differently from US tech — providing
cushioning when the semiconductor chain is under pressure.

Currency note: G3B.SI is SGD-denominated. A strengthening SGD
against USD increases effective USD returns when repatriating.
This is a natural hedge against USD weakness in the portfolio.

Divergence flag: G3B.SI falling while US tech is rising is a
thesis-integrity signal — it suggests Singapore-specific pressure
(banking sector, MAS policy, SGD currency) rather than global
risk-off. This happened recently and is worth tracking explicitly.

Sizing: Core stability. RSP. Berkshire patience on Singapore
banking fundamentals.

Watch: SGD/USD rate, Singapore banking sector health (DBS, OCBC,
UOB earnings), MAS monetary policy signals, STI vs S&P 500
correlation breakdown as a diversification health check.
""",

    "^VIX": """
Role: Macro fear gauge. Regime classifier. Not a holding.

Thesis: VIX is not an investment — it is the context layer for
every other position. The regime it signals changes how every
agent should weight its own output.

Regime classification:
  low_vix:   VIX below 15    — risk-on, complacency territory
  normal:    VIX 15–20       — baseline, no special weighting
  high_vix:  VIX 20–30       — elevated caution warranted
  crisis:    VIX above 30    — defensive posture, thesis review

Direction matters more than level: a VIX rising from 18 to 22
is more significant than a stable VIX at 25. Rate of change
signals emerging stress before the absolute level confirms it.

Divergence signal: VIX spike while semiconductors are green =
institutional hedging, not retail fear. This is a leading
indicator worth flagging explicitly — the smart money is buying
protection even as prices hold.

Watch: VIX direction (not just level), VIX vs realised
volatility spread (measures whether fear is justified by actual
moves), VIX term structure (contango vs backwardation signals
whether stress is expected to persist or resolve quickly).
"""
}

# ── PORTFOLIO RELATIONSHIPS ────────────────────────────────
# The causal chain connecting the portfolio as a whole.
# Injected into every Stage 1 agent as Layer 4 — the same
# text regardless of which ticker the agent is reasoning about.
# Gives agents the full picture of how the portfolio hangs
# together, not just the role of their assigned ticker.
# Update here if the investment thesis evolves.
PORTFOLIO_RELATIONSHIPS = """
PORTFOLIO THESIS
AI research breakthroughs drive hyperscaler data centre CapEx,
which drives semiconductor demand, which drives advanced chip
production, which drives photonics infrastructure adoption.

CAUSAL CHAIN
NVDA (demand anchor)
  → TSM (production floor — fabricates NVDA chips via CoWoS)
  → LITE (photonics — optical interconnects for NVDA clusters)
  → AVGO (parallel — networking + custom silicon for hyperscalers)

ETF LAYER
SMH amplifies semiconductor moves — holds NVDA and TSM as top
components. A semiconductor drawdown hits NVDA, TSM, and SMH
simultaneously. Diversification benefit is against idiosyncratic
risk, not sector-wide pressure.

QQQ captures the software and platform layer — Microsoft, Google,
Meta, Amazon. QQQ vs SMH divergence signals software/hardware
rotation and is worth tracking as a regime indicator.

G3B.SI provides SGD-denominated stability via Singapore banking
dividends. The thesis assumption is it moves differently from
US tech. When it does not — flag it as a thesis-integrity signal.

VIX is the regime classifier. Every agent's output should be
weighted by the current VIX regime.

KEY CONCENTRATION RISKS
1. NVDA, TSM, and SMH are structurally linked. In a semiconductor
   downturn, all three fall together. This is known and accepted.

2. The entire thematic growth layer (NVDA, TSM, AVGO, LITE)
   is exposed to US export controls on advanced semiconductors.
   A single regulatory event can affect all four simultaneously
   through a channel that has nothing to do with supply chain logic.

3. TSM carries permanent Taiwan Strait geopolitical risk.
   This risk does not appear and disappear with the news cycle —
   it is always structurally present.

SIZING PHILOSOPHY
Core stability: G3B.SI, QQQ, SMH — Berkshire patience, RSP.
Thematic growth: NVDA, TSM, AVGO — informed conviction.
Frontier bets: LITE — small sizing, managed risk, higher tolerance.
Quantum (post Day 30): IONQ, RGTI, QUBT, IBM — frontier only.
"""

# ── THESIS REVIEW TRACKING ─────────────────────────────────
# Tracks when each ticker thesis was last reviewed.
# Session start flags entries older than 30 days from Day 11.
# Semi-automated maintenance architecture:
#   Day 11: thesis_drafts + thesis_reviews tables, staleness flag,
#           correlation health checks from market_history
#   Day 14: watch item parser, intelligence feed triggers
#   Day 22: section-level AI drafts with rejection history awareness
#   Day 28: Streamlit review UI, thesis_overrides.json write on approval
# Human always decides. Rejections feed future drafts.
# Update dates here when you manually review and confirm a thesis.
THESIS_LAST_REVIEWED = {
    "NVDA":   "2026-06-09",
    "AVGO":   "2026-06-09",
    "LITE":   "2026-06-09",
    "TSM":    "2026-06-09",
    "QQQ":    "2026-06-09",
    "SMH":    "2026-06-09",
    "G3B.SI": "2026-06-09",
    "^VIX":   "2026-06-09",
}

# Portfolio relationship sections — reviewed independently.
# Empirical sections (etf_layer, stability_layer, concentration_risks)
# are validated automatically via market_history rolling correlations
# each session — no LLM call, no API cost, pure SQL.
PORTFOLIO_SECTIONS_LAST_REVIEWED = {
    "causal_chain":        "2026-06-09",
    "etf_layer":           "2026-06-09",
    "stability_layer":     "2026-06-09",
    "concentration_risks": "2026-06-09",
    "sizing_philosophy":   "2026-06-09",
}

# ── CORRELATION PAIRS ──────────────────────────────────────
# Defines which ticker pairs to check for rolling correlation
# each session. check_portfolio_correlations() in stock_monitor.py
# reads this list and runs a 30-day Pearson check on each pair.
#
# What correlation means in plain English:
#   Above 0.70 = the two positions are moving together strongly —
#   any diversification benefit between them is currently weak.
#   Above 0.95 = they are moving almost identically — you
#   effectively have one position, not two.
#
# What happens when threshold is breached:
#   A portfolio_relationship_alert signal is written to the signals
#   table. It surfaces in the run summary and gets injected into
#   the Meta-Agent's context so it reasons with this information.
#
# How to add a new pair:
#   Copy one dict block below and change ticker_a, ticker_b,
#   threshold, label, and rationale. That is all — the function
#   picks it up automatically on the next run.
#
# G3B.SI note: the diversification thesis for G3B.SI needs
# re-evaluation at Days 31-60 when the knowledge graph and
# regional lenses are built. The correlation check surfaces
# data — it does not replace proper investment analysis.
CORRELATION_PAIRS = [
    {
        # Diversification health check
        # G3B.SI should move independently of the semiconductor chain.
        # If correlation exceeds 0.70, the "local anchor" thesis is
        # currently broken — G3B.SI is moving with the chain, not
        # against it. This does not mean sell — it means the
        # diversification assumption needs reviewing.
        "ticker_a":  "G3B.SI",
        "ticker_b":  "SMH",
        "threshold": 0.70,
        "label":     "G3B.SI vs SMH — diversification health",
        "rationale": (
            "G3B.SI should move independently of the semiconductor "
            "chain. High correlation signals the diversification "
            "thesis is currently not holding."
        ),
    },
    {
        # Concentration signal
        # NVDA is approximately 20% of SMH. If their correlation
        # exceeds 0.95, NVDA is so dominant that holding both NVDA
        # and SMH gives almost no additional exposure — you are
        # essentially doubling your NVDA bet through SMH.
        "ticker_a":  "NVDA",
        "ticker_b":  "SMH",
        "threshold": 0.95,
        "label":     "NVDA vs SMH — concentration signal",
        "rationale": (
            "NVDA is ~20% of SMH. Extremely high correlation signals "
            "NVDA is dominating SMH returns — holding both gives "
            "minimal diversification benefit."
        ),
    },
]

# ── THESIS OVERRIDES ───────────────────────────────────────
# Loads human-approved thesis changes from thesis_overrides.json
# and merges them into TICKER_THESIS at startup.
#
# How it works:
#   1. thesis_overrides.json starts as an empty dict {}
#   2. On Day 28, the Streamlit review UI writes approved
#      changes here when you click approve
#   3. At startup, this block reads the file and patches
#      TICKER_THESIS in place — agents always see the merged result
#
# Why a separate file instead of editing TICKER_THESIS directly?
#   - TICKER_THESIS is version-controlled in Git — your base thesis
#   - thesis_overrides.json holds live approved changes — separate layer
#   - If you ever want to reset to base thesis, delete the overrides file
#   - The two-layer design means you never lose your original reasoning

# Build path relative to this file's location.
# Works regardless of which directory you run stock_monitor.py from.
_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "thesis_overrides.json")


def _load_thesis_overrides():
    """
    Reads thesis_overrides.json. Returns empty dict if file is
    missing or unreadable — never crashes the pipeline.
    """
    if not os.path.exists(_OVERRIDES_PATH):
        # File does not exist yet — no overrides to apply, that is fine
        return {}
    try:
        with open(_OVERRIDES_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        # Malformed JSON or permission error — warn and continue
        print(f"[CONFIG] WARNING: could not load thesis_overrides.json: {e}")
        return {}


def _deep_update(base, overrides):
    """
    Merges overrides into base one level deep.
    Why not dict.update()? Because dict.update() replaces the entire
    ticker entry. If overrides has only NVDA.thesis, we want to keep
    NVDA.watch_items and NVDA.sizing from base untouched.
    This function merges section by section instead.
    """
    for ticker, sections in overrides.items():
        if ticker in base and isinstance(base[ticker], dict):
            # Ticker exists — merge at section level, not ticker level
            base[ticker].update(sections)
        else:
            # New ticker not in base — add it wholesale
            base[ticker] = sections
    return base


# Apply overrides to TICKER_THESIS once at import time.
# After this line TICKER_THESIS reflects base + any approved changes.
# Agents import config and read TICKER_THESIS — they automatically
# get the patched version without any change to pipeline code.
_deep_update(TICKER_THESIS, _load_thesis_overrides())

# --- Scheduler & Resilience ---
# Time the pipeline fires daily — matches Windows Task Scheduler trigger
SCHEDULE_TIME = "12:00"

# If a run exceeds this many minutes, it is killed and marked failed
MAX_RUN_MINUTES = 30

# run_log rows with status='running' older than this are marked failed (stale lock cleanup)
STUCK_RUN_THRESHOLD_MINUTES = 60

# ── FIXTURE & ENV PATHS ────────────────────────────────────
# Passed to shared/utils.py wrappers so shared functions never
# construct project-specific paths themselves.
# Path(__file__).parent = the stock-monitor/ folder —
# works regardless of which directory the pipeline is run from.
FIXTURE_DIR        = Path(__file__).parent / "fixtures" / "agents"
PRICE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "normal_day.json"
ENV_PATH           = Path(__file__).parent / ".env"

# ── SLM CONFIGURATION ──────────────────────────────────────
#
# FULL MODE MATRIX — including SLM sovereign tier
#
# LIVE_DATA  LIVE_AGENTS  DEV_MODE  USE_SLM  SLM_MODE  SCENARIO                                         COST
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────
# False      False        True      False    —         Full fixture — build/test                        $0.00
# True       False        True      False    —         Live prices + fixture agents                     $0.00
# False      True         True      False    —         Fixture prices + live Haiku                     ~$0.05
# False      True         False     False    —         Fixture prices + live Sonnet                    ~$0.30
# True       True         True      False    —         Full live run — Haiku                           ~$0.05
# True       True         False     False    —         Full live run — Sonnet/demo                     ~$0.30
# True       True         False     True     fast      Full live — phi4-mini + gemma4:e4b               $0.00
# True       True         False     True     heavy     Full live — phi4-mini + qwen3.6 + gemma4:26b     $0.00
#
# When USE_SLM=True, USE_LIVE_AGENTS is implied True regardless of its value.
# SLM calls never touch the Anthropic API — full data sovereignty.
#
# SLM_MODE controls which models handle which stages:
#   fast:  phi4-mini for Stage 1 + Translator, gemma4:e4b for Stage 2/3
#   heavy: phi4-mini for Stage 1 + Translator, qwen3.6:35b-a3b for Stage 2,
#          gemma4:26b for Stage 3 (full sovereign production run)
#
# USE_SLM=False leaves all existing routing unchanged.
# Switch USE_SLM=True to go fully sovereign at zero API cost.

# Master SLM switch
# False = use Anthropic API tiers (existing behaviour, unchanged)
# True  = route all agent calls to local Ollama (sovereign, $0.00)
USE_SLM  = False

# Active SLM tier — only relevant when USE_SLM=True
# "fast"  = phi4-mini + gemma4:e4b  — dev runs, quick iteration
# "heavy" = phi4-mini + qwen3.6 + gemma4:26b — sovereign production
SLM_MODE = "fast"

# ── SLM MODEL REGISTRY ─────────────────────────────────────
# Ollama model tags — must match exactly what ollama list shows.
# Change here to swap models — zero code changes needed elsewhere.
SLM_FAST_MODEL  = "phi4-mini"         # fast tier default — Stage 1 + Translator
SLM_HEAVY_MODEL = "qwen3.6:35b-a3b"   # heavy tier Stage 2 — deep reasoning
SLM_HEAVY_MODEL_STAGE3 = "gemma4:26b" # heavy tier Stage 3 — sovereign Meta-Agent

# Per-stage SLM model assignment
# Controls which SLM model handles each pipeline stage.
# Values are tier names — resolved to actual model by the wrapper.
# Changing a stage from "fast" to "heavy" is a one-line edit here.
# Stage 1 revisit: Day 21 (feeds added), Day 31 (geospatial added)
SLM_STAGE_MODELS = {
    "stage1":     "fast",   # phi4-mini — 28 calls/run, speed critical
    "stage2":     "fast",   # gemma4:e4b — reasoning depth, one call/ticker
    "stage3":     "heavy",  # heavy model — Meta-Agent, most critical call
    "translator": "fast",   # phi4-mini — plain English, low complexity
}

# ── OLLAMA CONNECTION ───────────────────────────────────────
# Local REST endpoint — never changes unless Ollama port is reconfigured.
# Sovereign principle: this is a localhost address — no data leaves
# the machine. If this URL ever points outside localhost, reject it.
OLLAMA_BASE_URL = "http://localhost:11434/api/chat"
OLLAMA_TIMEOUT  = 600  # seconds — heavy models need up to 5 minutes per call

# ── SLM MODEL PRICING (shadow cost reference) ──────────────
# SLM calls cost $0.00 — added here so MODEL_PRICING is complete
# and shadow cost computation has a consistent reference point.
# Ollama does not charge per token — these entries exist only to
# make the pricing dict exhaustive and to document the zero-cost tier.
MODEL_PRICING.update({
    "phi4-mini":         {"input": 0.00, "output": 0.00},
    "gemma4:e4b":        {"input": 0.00, "output": 0.00},
    "qwen3.6:35b-a3b":   {"input": 0.00, "output": 0.00},
    "gemma4:26b":        {"input": 0.00, "output": 0.00},
})

# ── SHADOW COST REFERENCE MODELS ───────────────────────────
# When USE_SLM=True, the wrapper computes what this run would have
# cost on cloud models using actual token counts from the SLM call.
# These two model keys are the reference points for shadow cost rows
# in the run summary comparison table.
SHADOW_COST_HAIKU_MODEL  = "claude-haiku-4-5-20251001"
SHADOW_COST_SONNET_MODEL = "claude-sonnet-4-6"

# ─────────────────────────────────────────────────────────────
# INTELLIGENCE FEEDS — STAGE 1
# Storage only. No model reads feed content in Stage 1.
# Feed Stage 2 (agent consumption) gated on Day 42 red-team.
# ─────────────────────────────────────────────────────────────

FEED_SOURCES = [
    # AI
    {"domain": "ai", "name": "VentureBeat AI",          "url": "https://venturebeat.com/category/ai/feed/"},
    {"domain": "ai", "name": "arXiv cs.AI",             "url": "https://rss.arxiv.org/rss/cs.AI"},
    {"domain": "ai", "name": "Import AI",               "url": "https://importai.substack.com/feed"},
    {"domain": "ai", "name": "MIT Technology Review AI","url": "https://www.technologyreview.com/feed/"},
    {"domain": "ai", "name": "Google DeepMind Blog",    "url": "https://deepmind.google/blog/rss.xml"},
    # Quantum
    {"domain": "quantum", "name": "Quanta Quantum",         "url": "https://www.quantamagazine.org/tag/quantum-computing/feed/"},
    {"domain": "quantum", "name": "Quanta Magazine",         "url": "https://www.quantamagazine.org/feed/"},
    {"domain": "quantum", "name": "arXiv quant-ph",          "url": "https://rss.arxiv.org/rss/quant-ph"},
    {"domain": "quantum", "name": "IEEE Spectrum",            "url": "https://spectrum.ieee.org/feeds/feed.rss"},
    {"domain": "quantum", "name": "New Scientist Quantum",   "url": "https://www.newscientist.com/subject/physics/feed/"},
    # Geopolitics
    {"domain": "geopolitics", "name": "The Diplomat",              "url": "https://thediplomat.com/feed/"},
    {"domain": "geopolitics", "name": "Foreign Policy",            "url": "https://foreignpolicy.com/feed/"},
    {"domain": "geopolitics", "name": "Politico National Security", "url": "https://rss.politico.com/defense.xml"},
    # Current Affairs
    {"domain": "current_affairs", "name": "Channel NewsAsia",       "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"},
    {"domain": "current_affairs", "name": "Japan Times",            "url": "https://www.japantimes.co.jp/feed/"},
    {"domain": "current_affairs", "name": "Guardian",               "url": "https://www.theguardian.com/world/rss"},
    {"domain": "current_affairs", "name": "Al Jazeera",             "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"domain": "current_affairs", "name": "South China Morning Post","url": "https://www.scmp.com/rss/91/feed"},
    {"domain": "current_affairs", "name": "Politico Technology",    "url": "https://rss.politico.com/technology.xml"},
    {"domain": "current_affairs", "name": "Federal Reserve",        "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
    # Tech
    {"domain": "tech", "name": "Hacker News", "url": "https://news.ycombinator.com/rss"},
    {"domain": "tech", "name": "a16z Future", "url": "https://future.a16z.com/feed"},
]

# Injection controls — govern what makes it into the data package
FEED_MAX_HEADLINES_PER_DOMAIN = 5   # top N per domain by relevance score
FEED_RELEVANCE_THRESHOLD      = 1   # minimum keyword matches to pass filter
FEED_MAX_TOTAL_HEADLINES      = 30  # hard cap across all domains combined

# Keywords per ticker for relevance scoring
# Drawn from TICKER_THESIS — what words signal this ticker is relevant
FEED_KEYWORDS = {
    "NVDA": ["nvidia", "gpu", "cuda", "data center", "blackwell", "hopper",
             "jensen huang", "accelerated computing", "ai chip"],
    "AVGO": ["broadcom", "avgo", "custom chip", "asic", "hyperscaler",
             "networking", "vmware", "hock tan"],
    "LITE": ["lumentum", "lite", "photonics", "laser", "optical",
             "copper to light", "silicon photonics", "transceiver"],
    "TSM":  ["tsmc", "taiwan semiconductor", "cowos", "packaging",
             "foundry", "2nm", "3nm", "fab", "taiwan strait"],
    "QQQ":  ["nasdaq", "qqq", "tech stocks", "rate", "federal reserve",
             "treasury yield", "growth stocks", "tech selloff"],
    "SMH":  ["semiconductor", "smh", "chip", "sox index", "wafer",
             "equipment", "asml", "applied materials"],
    "G3B.SI": ["sti", "straits times index", "singapore", "dbs", "ocbc",
               "uob", "sgx", "singapore dollar", "mas"],
    "^VIX": ["vix", "volatility", "fear index", "market fear",
             "risk off", "sell off", "crash", "correction"],
}