# tools/slm_benchmark.py
# SLM Token Evaluator — benchmarks local Ollama models on prompt size,
# inference speed, and output quality (JSON validity + hallucination detection).
#
# Usage:
#   python tools/slm_benchmark.py                        # all sizes, synthetic
#   python tools/slm_benchmark.py --size small           # one size only
#   python tools/slm_benchmark.py --mode realistic       # real data package
#   python tools/slm_benchmark.py --max-tokens 800       # stress test output
#   python tools/slm_benchmark.py --size large --mode realistic --max-tokens 800
#
# Results logged to slm_benchmarks table in prices.db.
# Run summary printed to terminal at end.

import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────
# Add project root and stock-monitor to path so config and database
# are importable from the tools/ subdirectory
_TOOL_DIR    = Path(__file__).parent
_PROJECT_DIR = _TOOL_DIR.parent
_ROOT_DIR    = _PROJECT_DIR.parent

sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_PROJECT_DIR))

import config
import database

# Import production system prompts — single source of truth for agent behaviour.
# Benchmark must use the same prompts as production so routing decisions
# reflect real pipeline performance, not benchmark-specific prompt quality.
from prompts.analyst_persona import (
    STOCK_BULL_SYSTEM_PROMPT,
    STOCK_BEAR_SYSTEM_PROMPT,
    STOCK_BLACK_SWAN_SYSTEM_PROMPT,
    STOCK_PRAGMATIST_SYSTEM_PROMPT,
    STOCK_CONTRARIAN_SYSTEM_PROMPT,
    STOCK_META_AGENT_SYSTEM_PROMPT,
)

# Maps each schema name to its production system prompt.
# Selected in main() based on --schema flag.
# Prompt-only runs (no --schema) fall back to BENCHMARK_SYSTEM_PROMPT.
SCHEMA_SYSTEM_PROMPTS = {
    "bull":        STOCK_BULL_SYSTEM_PROMPT,
    "bear":        STOCK_BEAR_SYSTEM_PROMPT,
    "black_swan":  STOCK_BLACK_SWAN_SYSTEM_PROMPT,
    "pragmatist":  STOCK_PRAGMATIST_SYSTEM_PROMPT,
    "contrarian":  STOCK_CONTRARIAN_SYSTEM_PROMPT,
    "meta_agent":  STOCK_META_AGENT_SYSTEM_PROMPT,
}

# ── Constants ─────────────────────────────────────────────────
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_CHAT_URL = config.OLLAMA_BASE_URL

# Valid direction values for the Stock Monitor pipeline
VALID_DIRECTIONS = {"ACCUMULATE", "HOLD", "REDUCE", "EXIT"}

# The single ticker every benchmark prompt is built around. All prompt
# layers (_build_layer_1, chain summary, thesis) are hardcoded to this.
# Injected into the system prompt so the model is explicitly grounded,
# and checked against the model's output ticker in assess_quality() so
# drift to another ticker (e.g. gemma4:e4b reasoning about G3B.SI on an
# NVDA prompt) is flagged, not silently accepted. One source of truth —
# injection and verification both read this, so they cannot disagree.
EXPECTED_TICKER = "NVDA"

# Prompt size labels — built from real data layers, not padding
# Approximate token counts after assembly:
#   small  ~300   — Layer 1 only (price + instruction)
#   medium ~1500  — Layers 1-3 (price + thesis + chain summary)
#   large  ~3000  — Layers 1-6 (full current data package)
#   xl     ~5000  — Layers 1-6 + RSS feed headlines (Day 21 simulation)
#   xxl    ~10000 — Layers 1-6 + feeds + RAG chunks (Day 20+21 simulation)
PROMPT_SIZE_LABELS = ["small", "medium", "large", "xl", "xxl"]

# System prompt used for all benchmark calls
BENCHMARK_SYSTEM_PROMPT = f"""You are a Bull analyst for a stock monitoring pipeline.
You are analysing exactly one ticker: {EXPECTED_TICKER}. Your entire analysis must
be about {EXPECTED_TICKER} and no other ticker. Other tickers may appear in the data
as context — do not switch your analysis to them.
Analyse the provided data and return ONLY a JSON object with exactly these fields:
{{
  "ticker": "{EXPECTED_TICKER}",
  "direction": "ACCUMULATE or HOLD or REDUCE or EXIT",
  "confidence": <integer 1-5>,
  "primary_argument": "<one sentence>",
  "key_assumption": "<one sentence>"
}}
Return JSON only. No preamble, no explanation, no markdown."""

# ── Synthetic feed headlines (Day 21 simulation) ───────────────
# Structured like real RSS feed output — varied content, realistic length.
# Used in xl and xxl prompts to simulate what agents will receive
# after Feed Stage 1 is wired on Day 21.
SYNTHETIC_FEED_HEADLINES = """
INTELLIGENCE FEEDS — INGESTED HEADLINES (last 24 hours)

AI & RESEARCH SIGNALS:
  - Anthropic releases Claude 4 with extended context window and improved
    reasoning capabilities; enterprise adoption accelerating across financial
    services sector with several tier-1 banks announcing pilot deployments.
  - Google DeepMind publishes Gemini Ultra 2 benchmark results showing
    significant gains on mathematical reasoning and code generation tasks;
    hyperscaler AI infrastructure spending cited as primary enabler.
  - arXiv: New paper on speculative decoding achieves 3x inference speedup
    on transformer architectures without quality degradation; implications
    for data centre GPU utilisation efficiency significant.
  - Microsoft Azure AI announces 40% capacity expansion in Singapore and
    Tokyo data centres; sovereign AI demand from ASEAN governments driving
    regional infrastructure buildout beyond original projections.
  - NVIDIA announces Blackwell Ultra architecture preview at GTC Singapore;
    CoWoS-S packaging density increased 60% versus H100 generation;
    hyperscaler allocation already oversubscribed through Q3 2026.

GEOPOLITICAL SIGNALS:
  - Taiwan Strait: PLA naval exercise scheduled for next week within 50nm
    of TSMC Hsinchu campus; US carrier group repositioning to South China
    Sea in response; semiconductor supply chain risk elevated.
  - US Commerce Department expands Entity List with 12 additional Chinese
    AI chip design firms; Huawei advanced packaging subsidiary included;
    TSMC CoWoS allocation to US hyperscalers expected to increase.
  - Japan announces 2 trillion yen semiconductor sovereignty fund; TSMC
    Kumamoto Phase 2 fast-tracked with full government backing; geopolitical
    diversification of production floor thesis receiving policy confirmation.
  - Singapore MAS issues guidance on AI model risk management for financial
    institutions; local banks accelerating AI governance frameworks ahead
    of mandatory compliance deadline in Q4 2026.
  - South Korea announces DRAM export controls matching US restrictions;
    memory supply chain concentration risk increasing for AI training clusters.

QUANTUM COMPUTING SIGNALS:
  - IBM achieves 1000-qubit milestone with error correction below threshold
    for practical computation; cryptography implications flagged by NIST;
    timeline for quantum advantage in optimisation problems revised to 2028.
  - IonQ announces partnership with defence contractor for quantum-secured
    communications; government contract worth $340M over 5 years; pure-play
    quantum revenue model validation.

CURRENT AFFAIRS - SINGAPORE:
  - MAS monetary policy unchanged; SGD NEER maintained at current slope
    and width; Singapore core inflation 2.1% YoY, within target band.
  - DBS Q1 results beat consensus by 8%; net interest margin stable;
    management guides for continued dividend growth through 2027.
  - Singapore budget 2026 forward estimates show increased SkillsFuture
    allocation for AI and digital skills; enterprise transformation grants
    expanded to cover AI deployment costs.

SOCIAL SENTIMENT:
  - Reddit r/investing: NVDA sentiment 67% bullish on 2,341 posts;
    dominant theme is Blackwell allocation cycle; bear case centres on
    valuation and China export restrictions.
  - Reddit r/wallstreetbets: LITE mentioned in 89 posts with 71% bearish
    sentiment; optical interconnect thesis questioned after recent price
    action; retail positioning asymmetrically short.
  - Reddit r/stocks: SMH ETF inflows positive for 12 consecutive sessions;
    institutional rebalancing into semiconductor exposure cited by multiple
    commenters tracking 13F filings.
"""

# ── Synthetic RAG chunks (Day 20 simulation) ───────────────────
# Structured like ChromaDB retrieved chunks from regulatory and
# thesis documents. Used in xxl prompts to simulate what agents
# will receive after RAG pipeline is wired on Day 20.
SYNTHETIC_RAG_CHUNKS = """
RETRIEVED CONTEXT — REGULATORY AND THESIS DOCUMENTS

[Source: NVDA_thesis_section_supply_chain, similarity: 0.94]
The semiconductor supply chain thesis rests on a three-layer assumption:
hyperscaler CapEx commitments translate into GPU allocation cycles which
translate into downstream photonics and networking demand. The critical
dependency is the CoWoS advanced packaging bottleneck at TSMC — without
CoWoS-S or CoWoS-L capacity, Blackwell chips cannot be assembled at the
density required for NVLink cluster configurations. As of Q1 2026, TSMC
CoWoS capacity utilisation was reported at 94% with a 6-9 month lead time
for new bookings. This creates a natural supply constraint that supports
NVDA pricing power through at least Q3 2026 under the base case scenario.

[Source: PORTFOLIO_RELATIONSHIPS_concentration_risks, similarity: 0.91]
Concentration risk analysis as of Day 12: G3B.SI vs SMH rolling 30-day
Pearson correlation measured at 0.831, breaching the 0.70 threshold for
the diversification health check. NVDA vs SMH correlation at 0.287, within
the 0.95 concentration threshold. Meta-Agent flagged G3B.SI as a potential
false diversifier on first live run (Day 10). Formal re-evaluation deferred
to Days 31-60 when knowledge graph and regional lenses are built. Current
portfolio correlation structure suggests the diversification benefit of
G3B.SI against semiconductor chain weakness is overstated.

[Source: TICKER_THESIS_AVGO_custom_silicon, similarity: 0.88]
AVGO custom silicon thesis: as hyperscalers build custom AI chips to reduce
NVDA dependence, AVGO wins the custom chip design layer and the networking
infrastructure connecting AI clusters. AVGO custom ASIC pipeline with
Google, Meta, and Apple represents the decoupling thesis. AVGO networking
(Ethernet switching) is infrastructure that every AI cluster needs
regardless of GPU vendor. Decoupling signal: AVGO rising while NVDA falls
equals hyperscaler rotation toward custom silicon. This is a thesis
confirmation signal, not a contradiction. Note: custom silicon revenue
currently less than 5% of AVGO total revenue despite being the primary
thesis driver — valuation risk if custom silicon adoption is slower than
the market has priced.

[Source: MAS_GUIDELINES_AI_model_risk_2026, similarity: 0.85]
Monetary Authority of Singapore AI Model Risk Management Guidelines (2026):
financial institutions deploying AI systems for investment-related
recommendations must maintain explainability documentation for all model
outputs, implement human-in-the-loop review for decisions above threshold
materiality, conduct quarterly model validation against out-of-sample
performance benchmarks, and maintain audit trails linking model inputs to
outputs with a minimum retention period of 7 years. AI systems classified
as high-risk under MAS criteria (systems influencing investment decisions
above SGD 100,000) require approval from the Chief Risk Officer before
production deployment. Backtesting requirements mandate minimum 24 months
of live paper-trading performance data before real-money deployment is
permitted.

[Source: TICKER_THESIS_LITE_photonics, similarity: 0.83]
LITE photonics thesis: the copper-to-light transition inside data centres.
As AI clusters scale beyond the bandwidth limits of copper interconnects,
optical interconnects become mandatory infrastructure. LITE is the primary
beneficiary of this transition. The thesis only activates if NVDA demand
and TSMC production are both healthy upstream — LITE is a downstream bet
on the thesis holding. Chain position: downstream, dependent on upstream
chain health. A sustained NVDA drawdown or TSMC capacity reduction is a
thesis-integrity threat for LITE before it is a price signal. Sizing:
frontier bet, small position, higher volatility tolerance than core or
thematic holdings.
"""


# ── Prompt builders ────────────────────────────────────────────

def _build_layer_1(nvda_price="$206.10", pct_change="-0.75",
                   vol_signal="low (0.31x avg)", vix="18.83",
                   vix_regime="normal"):
    """
    Layer 1 — Live price data for target ticker.
    Always present. ~100 tokens.
    """
    return (
        f"Analyse the following data package for NVDA as a Bull analyst.\n\n"
        f"LAYER 1 — LIVE PRICE DATA\n"
        f"  Ticker:          NVDA (equity)\n"
        f"  Current price:   {nvda_price}\n"
        f"  Change:          {pct_change}%\n"
        f"  Volume signal:   {vol_signal}\n"
        f"  VIX level:       {vix} ({vix_regime} regime)\n\n"
        f"Return JSON: direction, confidence, primary_argument, key_assumption.\n"
    )


def _build_layer_2():
    """
    Layer 2 — Static ticker thesis from config.
    ~400 tokens from actual TICKER_THESIS.
    """
    return (
        f"LAYER 2 — TICKER THESIS\n"
        f"{config.TICKER_THESIS.get('NVDA', 'No thesis defined.')}\n\n"
    )


def _build_layer_3():
    """
    Layer 3 — Chain summary (all tickers today).
    Simulated from fixture prices. ~200 tokens.
    """
    return (
        "LAYER 3 — CHAIN SUMMARY (live state today)\n"
        "  NVDA       (demand anchor)      -0.75%  $206.10  vol: low\n"
        "  AVGO       (network gatekeeper) -2.19%  $387.52  vol: low\n"
        "  LITE       (photonics)          -5.44%  $843.50  vol: low\n"
        "  TSM        (production floor)   -0.13%  $427.50  vol: low\n"
        "  QQQ        (nasdaq-100)         -0.69%  $710.49  vol: low\n"
        "  SMH        (semiconductor ETF)  -0.92%  $592.13  vol: low\n"
        "  G3B.SI     (local anchor)       +1.08%  $5.218   vol: normal\n"
        "  ^VIX       (fear gauge)         -0.48%  $18.83   regime: normal\n\n"
    )


def _build_layer_4():
    """
    Layer 4 — Portfolio relationships from config.
    ~300 tokens from actual PORTFOLIO_RELATIONSHIPS.
    """
    return (
        f"LAYER 4 — PORTFOLIO RELATIONSHIPS\n"
        f"{config.PORTFOLIO_RELATIONSHIPS}\n\n"
    )


def _build_layer_5():
    """
    Layer 5 — Historical context (trajectory stats).
    Simulated from typical market_history output. ~300 tokens.
    """
    return (
        "LAYER 5 — HISTORICAL CONTEXT\n"
        "  Sessions in database:  1255\n"
        "  3-day return:          -1.84%\n"
        "  5-day return:          -3.21%\n"
        "  Trend direction:       down_short_term\n"
        "  Streak:                -3 sessions\n"
        "  Position in range:     0.31 (0=at low, 1=at high)\n"
        "  10-day high:           $224.80\n"
        "  10-day low:            $198.40\n"
        "  Distance from high:    -8.32%\n"
        "  50-day MA:             $213.44  (above: False)\n"
        "  200-day MA:            $198.71  (above: True)\n"
        "  Volatility regime:     elevated\n\n"
    )


def _build_layer_6():
    """
    Layer 6 — Intelligence context (macro, geo, AI, sentiment).
    Simulated from fixture intelligence block. ~300 tokens.
    """
    return (
        "LAYER 6 — INTELLIGENCE CONTEXT\n"
        "  Macro regime:\n"
        "    Fed stance:        pause — rates unchanged at 4.25-4.50%\n"
        "    Rate environment:  elevated — headwind for growth multiples\n"
        "    Dollar strength:   moderate — USDSGD 1.342\n"
        "    Key macro signal:  PCE inflation 2.3% YoY, above Fed target\n\n"
        "  Geopolitical signals:\n"
        "    - Taiwan Strait military exercise risk elevated (PLA activity)\n"
        "    - US export controls on advanced AI chips to China expanding\n"
        "    - Japan semiconductor sovereignty fund announced\n\n"
        "  AI research signals:\n"
        "    - NVIDIA Blackwell Ultra architecture preview positive\n"
        "    - Hyperscaler CapEx commitments intact per latest earnings\n\n"
        "  Regulatory signals:\n"
        "    - US AI executive order implementation guidance released\n"
        "    - Singapore MAS AI model risk guidelines effective Q4 2026\n\n"
        "  Sentiment:\n"
        "    Retail positioning:    67% bullish on NVDA (r/investing)\n"
        "    Institutional flows:   net positive SMH inflows 12 sessions\n"
        "    Contrarian indicator:  retail bullishness elevated — caution\n\n"
        "  Active kill triggers:  None currently active.\n\n"
    )


def build_synthetic_prompt(size_label):
    """
    Builds a layered data package prompt matching the real pipeline structure.

    Layer composition by size:
      small  — Layer 1 only (price + instruction)
      medium — Layers 1-4 (price + thesis + chain + portfolio)
      large  — Layers 1-6 (full current data package)
      xl     — Layers 1-6 + RSS feed headlines (Day 21 simulation)
      xxl    — Layers 1-6 + feeds + RAG chunks (Day 20+21 simulation)

    Why layered instead of padded?
    Padding with repeated keywords produces unrealistic attention patterns.
    Real prompts have varied content types — structured data, prose thesis,
    tabular chain summaries, bullet intelligence feeds, dense RAG chunks.
    Each content type tokenizes and processes differently. Layered prompts
    give honest benchmark data for routing decisions.
    """
    if size_label == "small":
        return _build_layer_1()

    elif size_label == "medium":
        # TOP: price + thesis. MIDDLE: chain + portfolio (accepted loss).
        # No historical or intelligence at medium — not enough layers to matter.
        return (
            _build_layer_1()          # TOP — price data
            + _build_layer_2()        # TOP — thesis
            + _build_layer_3()        # MIDDLE — chain summary
            + _build_layer_4()        # MIDDLE — portfolio relationships
        )

    elif size_label == "large":
        # TOP: price + thesis. MIDDLE: chain + portfolio.
        # BOTTOM: historical + intelligence.
        return (
            _build_layer_1()          # TOP — price data
            + _build_layer_2()        # TOP — thesis
            + _build_layer_3()        # MIDDLE — chain summary (accepted loss)
            + _build_layer_4()        # MIDDLE — portfolio relationships (accepted loss)
            + _build_layer_5()        # BOTTOM — historical anchors
            + _build_layer_6()        # BOTTOM — intelligence context
        )

    elif size_label == "xl":
        # Layers 1-6 + RSS feed headlines
        # Layer order matches build_data_package() production structure — Day 24.
        # TOP: price + thesis. MIDDLE: chain + portfolio (accepted attention loss).
        # BOTTOM: historical + intelligence + feeds (immediately above output marker).
        return (
            _build_layer_1()          # TOP — price data
            + _build_layer_2()        # TOP — thesis
            + _build_layer_3()        # MIDDLE — chain summary (accepted loss)
            + _build_layer_4()        # MIDDLE — portfolio relationships (accepted loss)
            + _build_layer_5()        # BOTTOM — historical anchors
            + _build_layer_6()        # BOTTOM — intelligence context
            + SYNTHETIC_FEED_HEADLINES  # BOTTOM — feeds, immediately above output
        )

    elif size_label == "xxl":
        # Layers 1-6 + feeds + RAG chunks
        # Same ordering as xl. RAG chunks appended last — they are the most
        # targeted retrieved content and benefit most from bottom-of-prompt
        # attention weighting.
        return (
            _build_layer_1()          # TOP — price data
            + _build_layer_2()        # TOP — thesis
            + _build_layer_3()        # MIDDLE — chain summary (accepted loss)
            + _build_layer_4()        # MIDDLE — portfolio relationships (accepted loss)
            + _build_layer_5()        # BOTTOM — historical anchors
            + _build_layer_6()        # BOTTOM — intelligence context
            + SYNTHETIC_FEED_HEADLINES  # BOTTOM — feeds
            + SYNTHETIC_RAG_CHUNKS    # BOTTOM — RAG chunks, last and highest attention
        )

    else:
        raise ValueError(
            f"Unknown prompt size '{size_label}'. "
            f"Valid values: {PROMPT_SIZE_LABELS}"
        )


def build_realistic_prompt():
    """
    Loads the actual data package from the Stock Monitor fixture file.
    Returns (prompt_text, size_label).
    Falls back to large synthetic if fixture not found.
    """
    fixture_path = config.PRICE_FIXTURE_PATH

    if not fixture_path.exists():
        print(f"  [WARN] Fixture not found at {fixture_path} "
              f"— falling back to synthetic large prompt.")
        return build_synthetic_prompt("large"), "large"

    try:
        with open(fixture_path, "r", encoding="utf-8-sig") as f:
            fixture = json.load(f)

        prices   = fixture.get("prices", [])
        nvda_row = next(
            (r for r in prices if r.get("ticker") == "NVDA"), {}
        )

        prompt = (
            _build_layer_1(
                nvda_price=f"${nvda_row.get('price', 'N/A')}",
                pct_change=str(nvda_row.get("pct_change", "N/A")),
                vol_signal=nvda_row.get("volume_signal", "N/A"),
            )
            + _build_layer_2()
            + _build_layer_3()
            + _build_layer_4()
            + _build_layer_5()
            + _build_layer_6()
        )
        return prompt, "realistic"

    except Exception as e:
        print(f"  [WARN] Failed to load fixture: {e} "
              f"— falling back to synthetic large prompt.")
        return build_synthetic_prompt("large"), "large"

def load_captured_prompt(call_type_prefix, run_id=None):
    """
    Loads a real captured prompt from llm_calls.prompt_text instead of
    building synthetic content. This is the honest alternative to
    build_synthetic_prompt() for xl and xxl sizes — real pipeline
    content at real token weight, not a guess at what Day 20/21
    content might look like.

    call_type_prefix: matches call_type using LIKE — e.g. 'stage1_pragmatist'
                       matches 'stage1_pragmatist' exactly (no wildcard needed
                       since call_type doesn't include ticker for stage1 rows
                       in llm_calls — only in the analysis table).
    run_id:            specific run to pull from. None = most recent capture
                       for this call_type_prefix.

    Returns (prompt_text, actual_input_tokens) or (None, None) if no
    matching row exists yet — caller must capture a live run first.
    """
    try:
        with database.get_connection() as conn:
            if run_id:
                row = conn.execute(
                    """
                    SELECT prompt_text, input_tokens
                    FROM llm_calls
                    WHERE call_type = ? AND run_id = ?
                      AND prompt_text IS NOT NULL
                    ORDER BY input_tokens DESC
                    LIMIT 1
                    """,
                    (call_type_prefix, run_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT prompt_text, input_tokens
                    FROM llm_calls
                    WHERE call_type = ?
                      AND prompt_text IS NOT NULL
                    ORDER BY input_tokens DESC
                    LIMIT 1
                    """,
                    (call_type_prefix,),
                ).fetchone()

            if row is None:
                return None, None

            return row["prompt_text"], row["input_tokens"]

    except Exception as e:
        print(f"  [WARN] Failed to load captured prompt for "
              f"'{call_type_prefix}' — {e}")
        return None, None


def load_stage1_outputs(ticker="NVDA", run_id=None):
    """
    Loads real Stage 1 agent outputs from the analysis table for use as
    Contrarian benchmark input. The Contrarian's production system prompt
    expects four Stage 1 outputs to audit — without them, the model has
    nothing to find consensus in and collapses to generic output.

    Using real captured outputs rather than synthetic stubs ensures the
    Contrarian benchmark reflects actual pipeline conditions — including
    the real verbosity, structure, and quality of Stage 1 agents.

    ticker:  which ticker's Stage 1 outputs to load (default: NVDA —
             matches EXPECTED_TICKER so the Contrarian audits the same
             ticker the benchmark is grounding everything else in)
    run_id:  specific run to pull from. None = most recent run that has
             all four personas for this ticker.

    Returns a formatted string block ready to append to the prompt,
    or None if no complete Stage 1 set exists in the database.
    """
    personas = ["bull", "bear", "black_swan", "pragmatist"]

    try:
        with database.get_connection() as conn:
            if run_id:
                # Pull from specific run
                rows = conn.execute(
                    """
                    SELECT analysis_type, output
                    FROM analysis
                    WHERE ticker = ?
                      AND analysis_type IN ('bull','bear','black_swan','pragmatist')
                      AND run_id = ?
                    ORDER BY analysis_type
                    """,
                    (ticker, run_id),
                ).fetchall()
            else:
                # Pull from most recent run that has all four personas
                # Subquery finds the latest run_id with a complete set
                rows = conn.execute(
                    """
                    SELECT analysis_type, output
                    FROM analysis
                    WHERE ticker = ?
                      AND analysis_type IN ('bull','bear','black_swan','pragmatist')
                      AND run_id = (
                          SELECT run_id
                          FROM analysis
                          WHERE ticker = ?
                            AND analysis_type IN ('bull','bear','black_swan','pragmatist')
                          GROUP BY run_id
                          HAVING COUNT(DISTINCT analysis_type) = 4
                          ORDER BY run_id DESC
                          LIMIT 1
                      )
                    ORDER BY analysis_type
                    """,
                    (ticker, ticker),
                ).fetchall()

        if not rows or len(rows) < 4:
            print(f"  [WARN] Incomplete Stage 1 outputs for {ticker} "
                  f"— found {len(rows) if rows else 0} of 4 personas. "
                  f"Run a live pipeline session first to populate the analysis table.")
            return None

        # Assemble into the format the Contrarian system prompt expects
        block = f"\nSTAGE 1 AGENT OUTPUTS — TARGET TICKER: {ticker}\n"
        block += f"GROUNDING: You are auditing the Stage 1 outputs below for {ticker} ONLY.\n"
        block += f"Your ticker field must be {ticker}. Other tickers appear as portfolio context — do not switch your analysis to them.\n\n"

        for row in rows:
            persona_label = row["analysis_type"].upper().replace("_", " ")
            block += f"{persona_label} OUTPUT:\n"
            block += row["output"]
            block += "\n\n"

        return block

    except Exception as e:
        print(f"  [WARN] Failed to load Stage 1 outputs for {ticker}: {e}")
        return None
    
# ── Ollama helpers ─────────────────────────────────────────────

def get_available_models():
    """
    Queries Ollama's tags endpoint to discover all locally pulled models.
    Returns list of model name strings e.g. ['phi4-mini', 'gemma4:e4b'].
    Exits with a clear message if Ollama is not running.
    """
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=10)
        response.raise_for_status()
        data    = response.json()
        models  = [m["name"] for m in data.get("models", [])]
        return models
    except requests.exceptions.ConnectionError:
        print(
            "\n[ERROR] Cannot connect to Ollama at http://localhost:11434\n"
            "Fix: Ollama is not running. Start it from the Windows Start menu\n"
            "     or run: Start-Process 'C:\\Users\\Mack\\AppData\\Local"
            "\\Programs\\Ollama\\ollama.exe'\n"
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Failed to query Ollama models: {e}")
        sys.exit(1)


def call_model(model, prompt, max_tokens, schema_dict=None, system_prompt=None):
    # system_prompt: agent-appropriate instruction for this schema.
    # When None, falls back to BENCHMARK_SYSTEM_PROMPT (Bull prompt-only default).
    if system_prompt is None:
        system_prompt = BENCHMARK_SYSTEM_PROMPT
    # schema_dict: optional JSON Schema dict produced by a Pydantic model's
    # .model_json_schema() method. When present, Ollama applies constrained
    # decoding — the model physically cannot produce tokens that violate the
    # schema. When None, the model runs prompt-only (existing behaviour).
    """
    Makes one inference call to Ollama and returns timing + token counts.
    Returns a dict with all fields needed for the benchmark row.
    Never crashes — catches all errors and returns an error result dict.
    """
    # num_ctx must be set explicitly — Ollama defaults to a small context
    # window (commonly 2048 tokens) regardless of model capability.
    # Without this, prompts larger than the default are silently truncated
    # and the model reasons on a fragment with no warning of any kind.
    # This was discovered Day 19 — xxl benchmark on phi4-mini returned
    # JSON=NO, Dir=NO, Halluc=YES because a 24,740-token prompt was cut
    # to ~4,000 tokens before the model ever saw it.
    #
    # num_ctx covers INPUT + OUTPUT combined, not output alone. Estimated
    # from prompt character length using config.OLLAMA_CHARS_PER_TOKEN_ESTIMATE,
    # capped at this specific model's real ceiling from
    # config.OLLAMA_MODEL_MAX_CTX — never a flat guessed number.
    estimated_input_tokens = len(prompt) // config.OLLAMA_CHARS_PER_TOKEN_ESTIMATE
    estimated_input_tokens += len(system_prompt) // config.OLLAMA_CHARS_PER_TOKEN_ESTIMATE

    required_ctx = (
        estimated_input_tokens + max_tokens + config.OLLAMA_NUM_CTX_SAFETY_MARGIN
    )

    model_ceiling = config.OLLAMA_MODEL_MAX_CTX.get(
        model, config.OLLAMA_NUM_CTX_FALLBACK_MAX
    )
    required_ctx = min(
        required_ctx, model_ceiling, config.OLLAMA_NUM_CTX_HARDWARE_CAP
    )

    payload = {
        "model":   model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        "stream":  False,
        "options": {
            "num_predict":  max_tokens,
            "temperature":  0.1,
            "num_ctx":      required_ctx,
        },
    }

    # If a schema was provided, add the format parameter to the payload.
    # This activates Ollama's constrained decoding — the inference engine
    # builds a finite state machine from the schema and masks invalid tokens
    # at generation time. The model cannot produce output that violates the
    # contract. Supported since Ollama 0.3.0 — we are on 0.30.8.
    if schema_dict is not None:
        payload["format"] = schema_dict

    start = time.time()
    try:
        response = requests.post(
            OLLAMA_CHAT_URL,
            json=payload,
            timeout=config.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        duration = round(time.time() - start, 1)
        data     = response.json()

        text         = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count", 0)
        out_tokens   = data.get("eval_count", 0)
        tokens_per_s = round(out_tokens / duration, 2) if duration > 0 else 0

        return {
            "success":      True,
            "text":         text,
            "input_tokens": input_tokens,
            "output_tokens": out_tokens,
            "duration_secs": duration,
            "tokens_per_sec": tokens_per_s,
            "error":        None,
        }

    except requests.exceptions.Timeout:
        duration = round(time.time() - start, 1)
        return {
            "success":       False,
            "text":          "",
            "input_tokens":  0,
            "output_tokens": 0,
            "duration_secs": duration,
            "tokens_per_sec": 0,
            "error":         f"Timeout after {duration}s "
                             f"(OLLAMA_TIMEOUT={config.OLLAMA_TIMEOUT}s)",
        }

    except Exception as e:
        duration = round(time.time() - start, 1)
        return {
            "success":       False,
            "text":          "",
            "input_tokens":  0,
            "output_tokens": 0,
            "duration_secs": duration,
            "tokens_per_sec": 0,
            "error":         str(e),
        }


# ── Quality assessment ─────────────────────────────────────────

def assess_quality(text, schema_dict=None):
    # schema_dict: when provided, expected fields are derived from the schema
    # itself rather than the hardcoded four-field prompt-only set.
    # This prevents schema fields from being flagged as hallucinations —
    # the hallucination check must know what fields are legitimate.
    """
    Assesses output quality on three dimensions:

    json_valid: did the model return parseable JSON?
      The pipeline depends on extract_json() — if the model can't
      produce parseable JSON on a simple prompt, it's not usable
      for Stage 1 agents regardless of speed.

    direction_valid: is the direction field one of the four valid values?
      ACCUMULATE / HOLD / REDUCE / EXIT are the only legal values.
      Anything else is a schema violation — the pipeline would drop
      this call and log a JSON parse failure.

    hallucination_flag: did the model invent fields not in the schema,
      or return a direction that sounds plausible but isn't valid
      (e.g. 'BUY', 'SELL', 'NEUTRAL', 'STRONG_BUY')?
      These look reasonable to a human but break the pipeline.

    Returns dict with the three boolean fields.
    """
    from shared.utils import extract_json

    # Attempt JSON extraction using the same function the pipeline uses
    parsed, error = extract_json(text)

    if parsed is None:
        return {
            "json_valid":        0,
            "direction_valid":   0,
            "hallucination_flag": 1,
            "ticker_mismatch":   0,   # JSON didn't parse — failure already
                                      # captured by json_valid/hallucination;
                                      # no object to read a ticker from
        }

    direction = parsed.get("direction", "").upper().strip()

    direction_valid    = 1 if direction in VALID_DIRECTIONS else 0

    # Hallucination check 1 — direction outside valid set
    # Common hallucinations: BUY, SELL, NEUTRAL, STRONG_BUY, STRONG_SELL
    direction_hallucination = 1 if (direction and direction not in VALID_DIRECTIONS) else 0

    # Hallucination check 2 — invented top-level fields not in schema.
    # When schema-guided decoding is active, expected fields come from the
    # schema contract itself. When prompt-only, use the hardcoded four-field
    # set that matches the BENCHMARK_SYSTEM_PROMPT output instructions.
    if schema_dict is not None:
        # Extract field names from the JSON Schema properties dict.
        # model_json_schema() produces {"properties": {"field": {...}, ...}}
        expected_fields = set(schema_dict.get("properties", {}).keys())
    else:
        # Prompt-only mode — fields from BENCHMARK_SYSTEM_PROMPT.
        # "ticker" added Day 22 — the system prompt now requires the model
        # to emit which ticker it analysed, so it is an expected field, not
        # an invented one. Without it here, the ticker field would be flagged
        # as a hallucination in prompt-only mode.
        expected_fields = {"ticker", "direction", "confidence", "primary_argument", "key_assumption"}

    actual_fields     = set(parsed.keys())
    invented_fields   = actual_fields - expected_fields
    field_hallucination = 1 if invented_fields else 0

    hallucination_flag = 1 if (direction_hallucination or field_hallucination) else 0

    # Ticker grounding check — did the model analyse the ticker we asked about?
    # Reads EXPECTED_TICKER (same constant injected into the system prompt in
    # Fix 2, so instruction and check can never disagree).
    # The system prompt REQUIRES a ticker field. So on parseable output:
    #   - ticker present and != EXPECTED_TICKER  → mismatch (drifted to another ticker)
    #   - ticker absent entirely                 → mismatch (ignored a direct instruction)
    #   - ticker present and == EXPECTED_TICKER  → match
    # Absence is a failure of instruction-following, not a neutral "no opinion",
    # so it is flagged, not excused.
    output_ticker = parsed.get("ticker", "").upper().strip()
    ticker_mismatch = 0 if output_ticker == EXPECTED_TICKER else 1

    return {
        "json_valid":         1,
        "direction_valid":    direction_valid,
        "hallucination_flag": hallucination_flag,
        "ticker_mismatch":    ticker_mismatch,
    }


# ── Database write ─────────────────────────────────────────────

def write_benchmark_result(benchmark_run_id, model, size_label,
                           mode, result, quality, max_tokens,
                           decode_mode="prompt_only"):
    # decode_mode: 'prompt_only' (default) or 'schema_guided'.
    # Records which decoding method was used for this benchmark row.
    # Allows direct comparison between modes in the slm_benchmarks table
    # without needing separate benchmark runs or separate tables.
    """
    Writes one benchmark result row to slm_benchmarks table.
    Non-blocking — never crashes the benchmark run on a write failure.
    """
    try:
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO slm_benchmarks (
                    benchmark_run_id, timestamp, model,
                    prompt_size, prompt_mode, decode_mode,
                    input_tokens, output_tokens,
                    duration_secs, tokens_per_sec, max_tokens,
                    json_valid, direction_valid, hallucination_flag,
                    ticker_mismatch,
                    raw_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    benchmark_run_id,
                    datetime.now().isoformat(),
                    model,
                    size_label,
                    mode,
                    decode_mode,          # 'prompt_only' or 'schema_guided'
                    result["input_tokens"],
                    result["output_tokens"],
                    result["duration_secs"],
                    result["tokens_per_sec"],
                    max_tokens,
                    quality.get("json_valid", 0),
                    quality.get("direction_valid", 0),
                    quality.get("hallucination_flag", 0),
                    quality.get("ticker_mismatch", 0),
                    result["text"][:5000],
                ),
            )
    except Exception as e:
        print(f"  [WARN] Failed to write benchmark row: {e}")


# ── Display ────────────────────────────────────────────────────

def print_results_table(results):
    """
    Prints a formatted comparison table of all benchmark results.
    Sorted by prompt size then tokens/sec descending so the fastest
    model at each size is immediately visible.
    """
    if not results:
        print("\nNo results to display.")
        return

    print("\n" + "=" * 90)
    print("  SLM BENCHMARK RESULTS")
    print("=" * 90)
    print(
        f"  {'Model':<22} {'Size':<8} {'In':>6} {'Out':>6} "
        f"{'Secs':>7} {'Tok/s':>6} {'JSON':>5} {'Dir':>5} {'Halluc':>7} {'Mismatch':>9}"
    )
    print(f"  {'-'*22} {'-'*8} {'-'*6} {'-'*6} {'-'*7} {'-'*6} {'-'*5} {'-'*5} {'-'*7} {'-'*9}")

    size_order = {"small": 0, "medium": 1, "large": 2, "realistic": 3}
    sorted_results = sorted(
        results,
        key=lambda r: (size_order.get(r["size"], 9), -r["tokens_per_sec"])
    )

    for r in sorted_results:
        status = "OK  " if r["success"] else "FAIL"
        print(
            f"  {r['model']:<22} {r['size']:<8} "
            f"{r['input_tokens']:>6} {r['output_tokens']:>6} "
            f"{r['duration_secs']:>7.1f} {r['tokens_per_sec']:>6.1f} "
            f"{'YES' if r['json_valid'] else 'NO':>5} "
            f"{'YES' if r['direction_valid'] else 'NO':>5} "
            f"{'YES' if r['hallucination_flag'] else 'NO':>7} "
            f"{'YES' if r.get('ticker_mismatch') else 'NO':>9}"
        )
        if r.get("error"):
            print(f"    ERROR: {r['error']}")

    print("=" * 90)
    print(
        "  Columns: In=input tokens | Out=output tokens | "
        "Tok/s=output tokens per second\n"
        "  JSON=parseable JSON | Dir=valid direction | "
        "Halluc=invented fields or invalid direction"
    )
    print("=" * 90)

    # ── Recommendation ──────────────────────────────────────────
    # Find the fastest model that produces valid JSON on large prompts
    # Use largest prompt size tested as the recommendation baseline
    sizes_tested = [r["size"] for r in results]
    size_priority = ["xxl", "xl", "realistic", "large", "medium", "small"]
    baseline_size = next(
        (s for s in size_priority if s in sizes_tested), "small"
    )

    large_valid = [
        r for r in results
        if r["size"] == baseline_size
        and r["json_valid"]
        and r["direction_valid"]
        and not r["hallucination_flag"]
        and r["success"]
    ]

    if large_valid:
        best = max(large_valid, key=lambda r: r["tokens_per_sec"])
        print(f"\n  RECOMMENDATION: '{best['model']}' — fastest valid model "
              f"on large prompts at {best['tokens_per_sec']} tok/s output")
    else:
        print("\n  RECOMMENDATION: No model produced valid JSON on large "
              "prompts — consider prompt simplification before SLM deployment")

    print()


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark local Ollama SLM models for Stock Monitor use"
    )
    parser.add_argument(
        "--size",
        choices=["small", "medium", "large", "xl", "xxl", "all"],
        default="all",
        help="Prompt size to test (default: all)"
    )
    parser.add_argument(
        "--mode",
        choices=["synthetic", "realistic"],
        default="synthetic",
        help="Prompt mode: synthetic padding or real fixture data (default: synthetic)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1200,
        help="Max output tokens per call (default: 400)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Specific models to test (default: all pulled models)"
    )
    parser.add_argument(
        "--schema",
        choices=["bull", "bear", "black_swan", "pragmatist", "contrarian", "meta_agent"],
        default=None,
        help=(
            "Optional: activate schema-guided decoding using the named agent schema. "
            "When set, Ollama constrains output to the Pydantic contract at token level. "
            "When absent, runs prompt-only mode (existing behaviour). "
            "Example: --schema bull"
        )
    )
    args = parser.parse_args()

    # ── Schema loading ─────────────────────────────────────────
    # Import the requested Pydantic schema and convert it to a JSON Schema
    # dict using .model_json_schema(). This dict is what Ollama's format
    # parameter expects — it describes the exact shape of valid output.
    # Only imported when --schema is passed so the benchmark still runs
    # without prompts/schemas.py in environments that don't have it.
    schema_dict = None
    decode_mode = "prompt_only"

    if args.schema:
        # Map CLI name to the matching Pydantic class
        schema_map = {
            "bull":        "BullOutput",
            "bear":        "BearOutput",
            "black_swan":  "BlackSwanOutput",
            "pragmatist":  "PragmatistOutput",
            "contrarian":  "ContrarianOutput",
            "meta_agent":  "MetaAgentOutput",
        }
        class_name = schema_map[args.schema]

        # Dynamic import — only load prompts.schemas when --schema is passed
        import importlib
        schemas_module = importlib.import_module("prompts.schemas")
        schema_class   = getattr(schemas_module, class_name)

        # Convert Pydantic model to JSON Schema dict for Ollama's format parameter
        schema_dict = schema_class.model_json_schema()
        decode_mode = "schema_guided"

        print(f"  Schema-guided decoding: {class_name}")
        print(f"  JSON Schema fields: {list(schema_dict.get('properties', {}).keys())}\n")
        
    # Select system prompt matching the schema being tested.
    # Falls back to BENCHMARK_SYSTEM_PROMPT for prompt-only runs.
    active_system_prompt = SCHEMA_SYSTEM_PROMPTS.get(args.schema, BENCHMARK_SYSTEM_PROMPT) if args.schema else BENCHMARK_SYSTEM_PROMPT
    # ── Setup ──────────────────────────────────────────────────
    database.initialise_db()
    benchmark_run_id = f"bench_{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}"

    print(f"\n{'='*60}")
    print(f"  SLM BENCHMARK — {benchmark_run_id}")
    print(f"  Mode: {args.mode.upper()} | Max tokens: {args.max_tokens}")
    print(f"{'='*60}\n")

    # ── Discover models ────────────────────────────────────────
    if args.models:
        models = args.models
        print(f"  Models specified: {', '.join(models)}")
    else:
        models = get_available_models()
        print(f"  Models found: {', '.join(models)}\n")

    if not models:
        print("  No models available. Pull models with: ollama pull <model>")
        sys.exit(0)

    # ── Build prompt list ──────────────────────────────────────
    if args.mode == "realistic":
        prompt, size_label = build_realistic_prompt()
        prompts_to_run = [(prompt, size_label)]
    else:
        if args.size == "all":
            sizes = ["small", "medium", "large", "xl", "xxl"]
        else:
            sizes = [args.size]

        prompts_to_run = []
        for s in sizes:
            if s == "xl":
                # xl = real Stage 1 prompt, largest agent (pragmatist)
                # from the most recent live capture run
                prompt, actual_tokens = load_captured_prompt("stage1_pragmatist")
                if prompt is None:
                    print(f"  [WARN] No captured prompt found for "
                          f"'stage1_pragmatist' — run a live pipeline "
                          f"session first to populate llm_calls.prompt_text. "
                          f"Falling back to synthetic xl.")
                    prompts_to_run.append((build_synthetic_prompt("xl"), "xl"))
                else:
                    print(f"  [xl] Using captured stage1_pragmatist prompt "
                          f"({actual_tokens} input tokens)")
                    # Contrarian benchmark needs real Stage 1 outputs appended —
                    # the production system prompt expects four agent outputs to audit
                    if args.schema == "contrarian":
                        stage1_block = load_stage1_outputs(ticker=EXPECTED_TICKER)
                        if stage1_block:
                            prompt += stage1_block
                    prompts_to_run.append((prompt, "xl"))

            elif s == "xxl":
                # xxl = real Stage 3 Meta-Agent prompt — the dominant
                # cost driver and the size that matters most for the
                # heavy tier sovereign routing decision
                prompt, actual_tokens = load_captured_prompt("stage3_meta_agent")
                if prompt is None:
                    print(f"  [WARN] No captured prompt found for "
                          f"'stage3_meta_agent' — run a live pipeline "
                          f"session first to populate llm_calls.prompt_text. "
                          f"Falling back to synthetic xxl.")
                    prompts_to_run.append((build_synthetic_prompt("xxl"), "xxl"))
                else:
                    print(f"  [xxl] Using captured stage3_meta_agent prompt "
                          f"({actual_tokens} input tokens)")
                    prompts_to_run.append((prompt, "xxl"))

            else:
                prompts_to_run.append((build_synthetic_prompt(s), s))

    # ── Run benchmarks ─────────────────────────────────────────
    all_results = []
    total_calls = len(models) * len(prompts_to_run)
    call_num    = 0

    for model in models:
        print(f"  Testing: {model}")

        for prompt, size_label in prompts_to_run:
            call_num += 1
            print(
                f"    [{call_num}/{total_calls}] "
                f"{size_label} prompt..."
            )

            result  = call_model(model, prompt, args.max_tokens, schema_dict=schema_dict, system_prompt=active_system_prompt)
            quality = assess_quality(result["text"], schema_dict=schema_dict) if result["success"] else {
                "json_valid": 0, "direction_valid": 0, "hallucination_flag": 0,
                "ticker_mismatch": 0
            }

            # Status line
            if result["success"]:
                print(
                    f"    OK — {result['duration_secs']}s | "
                    f"in={result['input_tokens']} out={result['output_tokens']} | "
                    f"{result['tokens_per_sec']} tok/s | "
                    f"JSON={'YES' if quality['json_valid'] else 'NO'} | "
                    f"Dir={'YES' if quality['direction_valid'] else 'NO'} | "
                    f"Halluc={'YES' if quality['hallucination_flag'] else 'NO'}"
                )
            else:
                print(f"    FAILED — {result['error']}")

            # Collect for summary table
            all_results.append({
                "model":            model,
                "size":             size_label,
                "success":          result["success"],
                "input_tokens":     result["input_tokens"],
                "output_tokens":    result["output_tokens"],
                "duration_secs":    result["duration_secs"],
                "tokens_per_sec":   result["tokens_per_sec"],
                "json_valid":       quality.get("json_valid", 0),
                "direction_valid":  quality.get("direction_valid", 0),
                "hallucination_flag": quality.get("hallucination_flag", 0),
                "ticker_mismatch":  quality.get("ticker_mismatch", 0),
                "error":            result.get("error"),
            })

            # Write to database — xl/xxl use real captured prompts even
            # when args.mode is 'synthetic', so log the honest mode per-row
            # rather than trusting the CLI flag blindly
            actual_mode = "realistic" if size_label in ("xl", "xxl") else args.mode

            write_benchmark_result(
                benchmark_run_id=benchmark_run_id,
                model=model,
                size_label=size_label,
                mode=actual_mode,
                result=result,
                quality=quality,
                max_tokens=args.max_tokens,
                decode_mode=decode_mode,
            )

        print()

    # ── Summary table ──────────────────────────────────────────
    print_results_table(all_results)
    print(f"  Results saved to slm_benchmarks table (run: {benchmark_run_id})\n")


if __name__ == "__main__":
    main()