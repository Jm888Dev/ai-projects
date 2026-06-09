# config.py
# All project constants live here. One file, one edit.
# Nothing is hardcoded in the pipeline scripts.

# ── DATA MODE ──────────────────────────────────────────────
# False = read from fixtures (development, prompt tuning, testing)
# True  = fetch from live sources (real sessions, demo, production)
# Change this one line to switch modes — nothing else changes.
USE_LIVE_DATA = False

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
STAGE_1_MODEL    = _HAIKU
STAGE_2_MODEL    = _HAIKU if DEV_MODE else _SONNET
STAGE_3_MODEL    = _HAIKU if DEV_MODE else _SONNET
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
TRANSLATOR_MAX_TOKENS = 1200   # was 1000 — slight increase for richer briefings

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