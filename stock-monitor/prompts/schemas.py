# prompts/schemas.py
#
# Production output contracts for the Stock Monitor six-agent pipeline.
# Each class defines the exact shape of one agent's JSON output.
#
# v1.1 CHANGES (this version)
# ----------------------------
# 1. reasoning_trace renamed to reasoning_raw_text and moved to the FIRST
#    reasoning-phase field (immediately after persona/ticker identity, before
#    any evidence field). Rationale: constrained decoding fills fields in
#    declared order. Under v1.0 ordering, reasoning_trace sat near the end —
#    meaning the model had already committed to direction/confidence before
#    it ever wrote a scratchpad. That is backwards: conclude-then-rationalize
#    instead of reason-then-conclude. Moving it to the front forces genuine
#    reasoning before the FSM locks in a conclusion.
#
# 2. raw_data_citations: Optional[List[str]] added to every schema.
#    Requires (via prompt instruction, NOT a Pydantic min_length constraint)
#    at least 2 verbatim numeric data points from the input, plus at least
#    1 citation from the middle-layer data (chain summary / portfolio
#    relationships — the zone Item A designated as accepted attention loss).
#
#    WHY THIS IS NOT A HARD-REQUIRED FIELD:
#    A hard min_length=2 constraint would recreate the exact failure mode
#    reasoning_raw_text was moved to the front to prevent. If the input
#    genuinely does not contain 2 clean numeric data points (thin dataset,
#    quiet news day), a required field with a minimum count gives the model
#    no legal way to say so — it is forced to invent a second number to
#    close the JSON object. That is schema-forced hallucination, the same
#    problem the Day 21 FSM finding named.
#
#    SOFT ENFORCEMENT INSTEAD: the field is Optional with no length floor.
#    The system prompt instructs the model to supply 2+ citations. If fewer
#    exist, the model populates what it honestly has (0 or 1 items) and
#    uses the existing data_quality_flag field to say why. This reuses
#    infrastructure that already exists for exactly this purpose — one
#    mechanism for "insufficient data," not two competing ones.
#
#    Same soft treatment applies to the middle-layer citation requirement.
#
#    OPEN ITEM (Section 10, not built this session): a detection process
#    that tracks data_quality_flag fire rate per ticker/data source across
#    runs, to distinguish a systematically broken source from normal
#    graceful degradation on a given day.
#
# FIELD ORDER CONVENTION — identity → reasoning_raw_text → evidence → reason → conclude
# ----------------------------------------------------------------------------------------
# Identity fields (persona, ticker) come first — they cost the model
# nothing to fill (persona is a Literal, ticker is echoed from the prompt)
# and preserve the ticker-grounding context established Day 24.
# reasoning_raw_text comes immediately after identity — before the model
# has written any evidence or committed to any conclusion.
# Evidence fields come next (what the data shows).
# Reasoning fields come next (what that evidence means).
# Conclusion fields come last (the committed call).
#
# OPTIONAL FIELDS — reasoning_raw_text, raw_data_citations, data_quality_flag
# -----------------------------------------------------------------------------
# reasoning_raw_text: Optional[str]
#   A scratchpad the model uses before committing to conclusions. Now the
#   first reasoning-phase field in every schema. Especially valuable for
#   SLMs with thinking modes — gives thinking tokens a productive outlet
#   instead of burning the output budget before valid JSON appears.
#   Value is stored in llm_calls for audit purposes.
#
# raw_data_citations: Optional[List[str]]
#   Verbatim numeric data points lifted from the input. Soft-enforced via
#   prompt instruction (2+ total, 1+ from the middle layer) — see above.
#
# data_quality_flag: Optional[str]
#   A field the model can populate when input data is insufficient,
#   corrupted, or missing — including when raw_data_citations cannot meet
#   the requested count. Prevents the model from fabricating confident
#   output when the honest answer is "I don't have enough data."
#   A model that cannot say "I don't know" is a model that hallucinates.
#
# HOW TO USE THESE SCHEMAS
# ------------------------
# SLM path (Ollama): pass schema.model_json_schema() to the `format`
#   parameter in the Ollama API call. Already wired in slm_benchmark.py.
#   Production wiring in _call_ollama() is a future queue item.
#
# LLM path (Anthropic): use as tool input_schema in tool_use calls.
#   Production wiring is a future queue item.
#
# IMPORT PATTERN
# --------------
# from prompts.schemas import (
#     BullOutput, BearOutput, BlackSwanOutput, PragmatistOutput,
#     ContrarianOutput, MetaAgentOutput,
# )
#
# RULES
# -----
# - Never change a field name without updating the pipeline function
#   that reads it. These are the contracts the database depends on.
#   v1.1 renames reasoning_trace -> reasoning_raw_text: every downstream
#   parser referencing the old name must be updated in the same session
#   this file is deployed. A rename does not raise a Pydantic error on
#   the old attribute access — it silently returns None. Verify by hand.
# - Never make a required field optional without understanding what
#   downstream code assumes about its presence.
# - Translator is intentionally absent — it produces plain text, not JSON.
#   Schema-guided decoding does not apply to the Translator.

from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE BULL
# Fields ordered: identity → reasoning_raw_text → evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class BullOutput(BaseModel):
    """
    Output contract for the Bull persona.
    Direction is locked to ACCUMULATE or HOLD — the Bull cannot hedge.
    Constrained decoding masks REDUCE and EXIT tokens entirely.
    """
    # IDENTITY — who produced this output and for which ticker (filled first,
    # near-zero cost, preserves ticker grounding per Day 24 fix)
    persona: Literal["bull"]
    ticker: str

    # REASONING SCRATCHPAD — filled before any evidence or conclusion field,
    # so the model reasons before the FSM locks it into a structured answer
    reasoning_raw_text: Optional[str] = None  # free-form thinking space, stored in llm_calls for audit

    # EVIDENCE — what the data shows
    supporting_evidence: str  # two to three specific data points with numbers cited
    raw_data_citations: Optional[List[str]] = None  # verbatim numeric points; soft target 2+, 1+ from middle layer

    # REASONING — what the evidence means in context
    key_assumption: str        # the single assumption the entire bull case depends on
    regime_sensitivity: str    # whether the call changes in different VIX regimes

    # QUALITY GATE — flag before concluding if data is poor, or if citation target unmet
    data_quality_flag: Optional[str] = None  # populated if input data is insufficient, suspect, or citations fell short

    # CONCLUSION — the committed call, produced after evidence and reasoning
    primary_argument: str                              # one committed bull thesis sentence
    direction: Literal["ACCUMULATE", "HOLD"]          # Bull cannot produce REDUCE or EXIT
    confidence: int = Field(ge=1, le=5)               # 1=low conviction, 5=maximum conviction
    watch_items: List[str] = Field(min_length=2, max_length=2)  # exactly two invalidation conditions


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE BEAR
# Fields ordered: identity → reasoning_raw_text → evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class BearOutput(BaseModel):
    """
    Output contract for the Bear persona.
    Direction is locked to REDUCE or EXIT — the Bear cannot express optimism.
    Constrained decoding masks ACCUMULATE and HOLD tokens entirely.
    """
    # IDENTITY
    persona: Literal["bear"]
    ticker: str

    # REASONING SCRATCHPAD — before evidence/conclusion, same rationale as Bull
    reasoning_raw_text: Optional[str] = None

    # EVIDENCE — stress-test data points cited before any conclusion
    supporting_evidence: str  # two to three specific data points with numbers cited
    raw_data_citations: Optional[List[str]] = None  # soft target 2+, 1+ from middle layer

    # REASONING — what the evidence means and what the bull is getting wrong
    key_assumption: str        # the bull assumption the Bear believes is wrong or fragile
    regime_sensitivity: str    # whether the bear call strengthens in high_vix vs low_vix

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION
    primary_argument: str                          # one committed bear thesis sentence
    direction: Literal["REDUCE", "EXIT"]          # Bear cannot produce ACCUMULATE or HOLD
    confidence: int = Field(ge=1, le=5)
    watch_items: List[str] = Field(min_length=2, max_length=2)


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE BLACK SWAN
# Fields ordered: identity → reasoning_raw_text → evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class BlackSwanOutput(BaseModel):
    """
    Output contract for the Black Swan persona.

    Two structural differences from Bull/Bear:
    1. confidence capped at 3 — tail risks are low probability by definition.
       A Black Swan with confidence=5 is a contradiction in terms.
    2. Completely different content fields — no primary_argument,
       no supporting_evidence. The Black Swan's job is unmapped risk
       identification, not thesis building.

    Field order is evidence-first within the reasoning zone:
    structural_fragility and underweighted_risk (what already exists in
    the data) before unmapped_risk (the tail thesis).
    """
    # IDENTITY
    persona: Literal["black_swan"]
    ticker: str

    # REASONING SCRATCHPAD
    reasoning_raw_text: Optional[str] = None

    # EVIDENCE — structural weaknesses observed before naming the tail risk
    structural_fragility: str   # the underlying weakness that enables a non-linear shock
    underweighted_risk: str     # a known risk the market systematically misprices
    raw_data_citations: Optional[List[str]] = None  # soft target 2+, 1+ from middle layer

    # REASONING — how a shock would propagate
    contagion_path: str         # which other portfolio tickers get hit and through what mechanism

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the tail risk thesis, committed after structural analysis
    unmapped_risk: str                         # the specific tail risk the market is not pricing
    direction: Literal["REDUCE", "EXIT"]      # Black Swan never recommends ACCUMULATE
    confidence: int = Field(ge=1, le=3)       # capped at 3 — tail risks are inherently low probability
    watch_items: List[str] = Field(min_length=2, max_length=2)


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE PRAGMATIST
# Fields ordered: identity → reasoning_raw_text → evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class PragmatistOutput(BaseModel):
    """
    Output contract for the Pragmatist persona.

    Unlike Bull/Bear/BlackSwan, the Pragmatist can produce any of the four
    directions — it goes where the statistical evidence points.

    Field order reflects the Pragmatist's data-first mandate:
    volume and trend (raw data) before regime context (interpretation)
    before statistical_anchor (the probability statement).
    """
    # IDENTITY
    persona: Literal["pragmatist"]
    ticker: str

    # REASONING SCRATCHPAD
    reasoning_raw_text: Optional[str] = None

    # EVIDENCE — raw statistical observations, no narrative
    volume_assessment: str   # is the price move backed by conviction volume or thin tape?
    trend_assessment: str    # price relative to moving averages and recent range
    raw_data_citations: Optional[List[str]] = None  # soft target 2+, 1+ from middle layer

    # REASONING — macro overlay applied to statistical baseline
    regime_context: str      # how the current macro regime affects this ticker historically

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the probability statement, produced after all evidence is assessed
    statistical_anchor: str                                        # the most probable near-term outcome with specific numbers
    direction: Literal["ACCUMULATE", "HOLD", "REDUCE", "EXIT"]   # goes where data leads
    confidence: int = Field(ge=1, le=5)
    watch_items: List[str] = Field(min_length=2, max_length=2)


# ─────────────────────────────────────────────────────────────
# STAGE 2 SCHEMA — THE CONTRARIAN
# Fields ordered: identity → reasoning_raw_text → evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class ContrarianOutput(BaseModel):
    """
    Output contract for the Contrarian persona.

    The Contrarian reads all four Stage 1 outputs and finds where they
    accidentally agree. Its evidence phase identifies the consensus;
    its reasoning phase challenges it; its conclusion states where the
    committee collectively missed.

    shared_blind_spot is positioned as evidence (not conclusion) because
    it must be identified before the Contrarian forms its own view.
    The Contrarian's direction follows from what was missed — not from
    the committee consensus.
    """
    # IDENTITY
    persona: Literal["contrarian"]
    ticker: str

    # REASONING SCRATCHPAD
    reasoning_raw_text: Optional[str] = None

    # EVIDENCE — what the committee collectively produced
    hidden_consensus: str   # where Bull and Bear accidentally agree despite opposite biases
    shared_blind_spot: str  # the single assumption ALL FOUR agents made without questioning
                            # this is the most important field in this schema
    raw_data_citations: Optional[List[str]] = None  # soft target 2+, 1+ from middle layer

    # REASONING — what the blind spot means and what it changes
    unasked_question: str    # the one question none of the four agents asked
    strongest_challenge: str # the most powerful challenge to the committee consensus

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the Contrarian's own view, derived from what was missed
    contrarian_rationale: str                                      # why the view differs from consensus
    direction: Literal["ACCUMULATE", "HOLD", "REDUCE", "EXIT"]
    confidence: int = Field(ge=1, le=5)


# ─────────────────────────────────────────────────────────────
# STAGE 3 SUB-MODEL — TICKER DECISION
# One block per ticker inside MetaAgentOutput
# No persona/ticker identity block here — the ticker symbol is already
# the dict key in the parent MetaAgentOutput.tickers field, so
# reasoning_raw_text is this model's first field.
# ─────────────────────────────────────────────────────────────

class TickerDecision(BaseModel):
    """
    One ticker's decision block inside the Meta-Agent's portfolio output.
    Defined as a separate sub-model so MetaAgentOutput can reference it
    as Dict[str, TickerDecision] — one block per ticker symbol.

    Field order: reasoning_raw_text first (no identity fields exist here
    to precede it) → tensions (evidence) → kill triggers (reasoning,
    derived from analysis) → rationale and decision (conclusion).

    Kill triggers are positioned in the reasoning phase because they are
    derived from the analysis — they encode what conditions would change
    the decision, which is a reasoning output, not a conclusion.
    """
    # REASONING SCRATCHPAD — first field; no identity fields precede it
    # because the ticker symbol already lives as the dict key one level up
    reasoning_raw_text: Optional[str] = None

    # EVIDENCE — where the five agents disagreed before the Meta-Agent decided
    key_tensions: str   # where agents disagreed most and how it was resolved
    raw_data_citations: Optional[List[str]] = None  # soft target 2+, 1+ from middle layer

    # REASONING — pre-committed conditions derived from the analysis
    # Three types, always present, always in this order:
    kill_trigger_1: str  # price/technical trigger — specific, measurable, executable
    kill_trigger_2: str  # thesis integrity trigger — what specific event breaks the thesis
    kill_trigger_3: str  # macro regime trigger — what macro condition forces defensive posture

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the authoritative decision for this ticker
    primary_rationale: str                             # one sentence grounded in agent evidence
    decision: Literal["ACCUMULATE", "HOLD", "REDUCE", "EXIT"]
    confidence: int = Field(ge=1, le=5)
    review_horizon: Literal["T+3 sessions", "T+1 week", "immediate"]


# ─────────────────────────────────────────────────────────────
# STAGE 3 SCHEMA — THE META-AGENT (PORTFOLIO MANAGER)
# ─────────────────────────────────────────────────────────────

class MetaAgentOutput(BaseModel):
    """
    Output contract for the Meta-Agent.

    Portfolio-level output — one TickerDecision block per ticker,
    nested inside a dictionary keyed by ticker symbol.

    Dict[str, TickerDecision] means:
    - str = the ticker symbol (e.g. "NVDA", "TSM")
    - TickerDecision = the full evidence→reason→conclude block for that ticker

    The portfolio_summary and premortem fields are portfolio-level conclusions
    that can only be produced after all per-ticker decisions are complete —
    they are positioned last for this reason.
    """
    # CONTEXT — session identity and risk regime (always first)
    portfolio_session: str  # YYYY-MM-DD
    vix_regime: Literal["low_vix", "normal", "high_vix", "crisis"]

    # EVIDENCE + CONCLUSION (nested) — one TickerDecision per ticker
    # The per-ticker analysis is itself reasoning_raw_text→evidence→reason→
    # conclude inside TickerDecision. At the portfolio level, the full set
    # of ticker decisions is the evidence base for the portfolio summary.
    tickers: Dict[str, TickerDecision]

    # PORTFOLIO-LEVEL CONCLUSION — produced after all ticker decisions exist
    portfolio_summary: str              # cross-ticker tensions and overall portfolio posture

    # STRESS SIGNAL — gates the weekly premortem agent
    premortem_flag: bool                # true when any of the four stress conditions fire
    premortem_scenario: Optional[str] = None  # present only when premortem_flag is True