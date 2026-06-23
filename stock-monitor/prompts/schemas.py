# prompts/schemas.py
#
# Production output contracts for the Stock Monitor six-agent pipeline.
# Each class defines the exact shape of one agent's JSON output.
#
# WHY THIS FILE EXISTS
# --------------------
# Previously, the pipeline relied on prompt instructions alone to produce
# valid JSON — "return only a valid JSON object, use exactly this schema."
# That is Level 1 structured output: instruction-based, ~80-95% reliable.
#
# These Pydantic models enable Level 3 structured output: constrained
# decoding. When passed to Ollama's `format` parameter, the inference
# engine builds a finite state machine from the schema and masks invalid
# tokens at generation time. The model physically cannot produce output
# that violates the contract.
#
# FIELD ORDER CONVENTION — evidence → reason → conclude
# ------------------------------------------------------
# Fields are ordered to match the model's natural reasoning sequence.
# Evidence fields come first (what the data shows).
# Reasoning fields come next (what that evidence means).
# Conclusion fields come last (the committed call).
# This ordering is deliberate — constrained decoding fills fields in the
# order they appear in the class. We want the model to ground itself in
# evidence before committing to a direction.
#
# OPTIONAL FIELDS — data_quality_flag and reasoning_trace
# --------------------------------------------------------
# Every schema includes two optional fields:
#
# reasoning_trace: Optional[str]
#   A scratchpad the model can use before committing to conclusions.
#   Positioned in the reasoning phase so the model can think before
#   it concludes. Especially valuable for SLMs with thinking modes —
#   gives thinking tokens a productive outlet instead of burning
#   the output budget before valid JSON appears.
#   Value is stored in llm_calls for audit purposes.
#
# data_quality_flag: Optional[str]
#   A field the model can populate when input data is insufficient,
#   corrupted, or missing. Prevents the model from fabricating confident
#   output when the honest answer is "I don't have enough data."
#   A model that cannot say "I don't know" is a model that hallucinates.
#   This field is the schema-level equivalent of the pipeline's graceful
#   degradation principle.
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
# - Never make a required field optional without understanding what
#   downstream code assumes about its presence.
# - Translator is intentionally absent — it produces plain text, not JSON.
#   Schema-guided decoding does not apply to the Translator.

from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE BULL
# Fields ordered: evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class BullOutput(BaseModel):
    """
    Output contract for the Bull persona.
    Direction is locked to ACCUMULATE or HOLD — the Bull cannot hedge.
    Constrained decoding masks REDUCE and EXIT tokens entirely.
    """
    # IDENTITY — who produced this output and for which ticker
    persona: Literal["bull"]
    ticker: str

    # EVIDENCE — what the data shows (filled first, before any conclusion)
    supporting_evidence: str  # two to three specific data points with numbers cited

    # REASONING — what the evidence means in context
    key_assumption: str        # the single assumption the entire bull case depends on
    regime_sensitivity: str    # whether the call changes in different VIX regimes
    reasoning_trace: Optional[str] = None  # optional scratchpad before committing to conclusion

    # QUALITY GATE — flag before concluding if data is poor
    data_quality_flag: Optional[str] = None  # populated if input data is insufficient or suspect

    # CONCLUSION — the committed call, produced after evidence and reasoning
    primary_argument: str                              # one committed bull thesis sentence
    direction: Literal["ACCUMULATE", "HOLD"]          # Bull cannot produce REDUCE or EXIT
    confidence: int = Field(ge=1, le=5)               # 1=low conviction, 5=maximum conviction
    watch_items: List[str] = Field(min_length=2, max_length=2)  # exactly two invalidation conditions


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE BEAR
# Fields ordered: evidence → reason → conclude
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

    # EVIDENCE — stress-test data points cited before any conclusion
    supporting_evidence: str  # two to three specific data points with numbers cited

    # REASONING — what the evidence means and what the bull is getting wrong
    key_assumption: str        # the bull assumption the Bear believes is wrong or fragile
    regime_sensitivity: str    # whether the bear call strengthens in high_vix vs low_vix
    reasoning_trace: Optional[str] = None

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION
    primary_argument: str                          # one committed bear thesis sentence
    direction: Literal["REDUCE", "EXIT"]          # Bear cannot produce ACCUMULATE or HOLD
    confidence: int = Field(ge=1, le=5)
    watch_items: List[str] = Field(min_length=2, max_length=2)


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE BLACK SWAN
# Fields ordered: evidence → reason → conclude
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

    Field order is evidence-first: structural_fragility and underweighted_risk
    (what already exists in the data) before unmapped_risk (the tail thesis).
    """
    # IDENTITY
    persona: Literal["black_swan"]
    ticker: str

    # EVIDENCE — structural weaknesses observed before naming the tail risk
    structural_fragility: str   # the underlying weakness that enables a non-linear shock
    underweighted_risk: str     # a known risk the market systematically misprices

    # REASONING — how a shock would propagate
    contagion_path: str         # which other portfolio tickers get hit and through what mechanism
    reasoning_trace: Optional[str] = None

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the tail risk thesis, committed after structural analysis
    unmapped_risk: str                         # the specific tail risk the market is not pricing
    direction: Literal["REDUCE", "EXIT"]      # Black Swan never recommends ACCUMULATE
    confidence: int = Field(ge=1, le=3)       # capped at 3 — tail risks are inherently low probability
    watch_items: List[str] = Field(min_length=2, max_length=2)


# ─────────────────────────────────────────────────────────────
# STAGE 1 SCHEMA — THE PRAGMATIST
# Fields ordered: evidence → reason → conclude
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

    # EVIDENCE — raw statistical observations, no narrative
    volume_assessment: str   # is the price move backed by conviction volume or thin tape?
    trend_assessment: str    # price relative to moving averages and recent range

    # REASONING — macro overlay applied to statistical baseline
    regime_context: str      # how the current macro regime affects this ticker historically
    reasoning_trace: Optional[str] = None

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the probability statement, produced after all evidence is assessed
    statistical_anchor: str                                        # the most probable near-term outcome with specific numbers
    direction: Literal["ACCUMULATE", "HOLD", "REDUCE", "EXIT"]   # goes where data leads
    confidence: int = Field(ge=1, le=5)
    watch_items: List[str] = Field(min_length=2, max_length=2)


# ─────────────────────────────────────────────────────────────
# STAGE 2 SCHEMA — THE CONTRARIAN
# Fields ordered: evidence → reason → conclude
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

    # EVIDENCE — what the committee collectively produced
    hidden_consensus: str   # where Bull and Bear accidentally agree despite opposite biases
    shared_blind_spot: str  # the single assumption ALL FOUR agents made without questioning
                            # this is the most important field in this schema

    # REASONING — what the blind spot means and what it changes
    unasked_question: str    # the one question none of the four agents asked
    strongest_challenge: str # the most powerful challenge to the committee consensus
    reasoning_trace: Optional[str] = None

    # QUALITY GATE
    data_quality_flag: Optional[str] = None

    # CONCLUSION — the Contrarian's own view, derived from what was missed
    contrarian_rationale: str                                      # why the view differs from consensus
    direction: Literal["ACCUMULATE", "HOLD", "REDUCE", "EXIT"]
    confidence: int = Field(ge=1, le=5)


# ─────────────────────────────────────────────────────────────
# STAGE 3 SUB-MODEL — TICKER DECISION
# One block per ticker inside MetaAgentOutput
# Fields ordered: evidence → reason → conclude
# ─────────────────────────────────────────────────────────────

class TickerDecision(BaseModel):
    """
    One ticker's decision block inside the Meta-Agent's portfolio output.
    Defined as a separate sub-model so MetaAgentOutput can reference it
    as Dict[str, TickerDecision] — one block per ticker symbol.

    Field order: tensions (evidence) → kill triggers (reasoning, derived
    from analysis) → rationale and decision (conclusion).

    Kill triggers are positioned in the reasoning phase because they are
    derived from the analysis — they encode what conditions would change
    the decision, which is a reasoning output, not a conclusion.
    """
    # EVIDENCE — where the five agents disagreed before the Meta-Agent decided
    key_tensions: str   # where agents disagreed most and how it was resolved

    # REASONING — pre-committed conditions derived from the analysis
    # Three types, always present, always in this order:
    kill_trigger_1: str  # price/technical trigger — specific, measurable, executable
    kill_trigger_2: str  # thesis integrity trigger — what specific event breaks the thesis
    kill_trigger_3: str  # macro regime trigger — what macro condition forces defensive posture

    reasoning_trace: Optional[str] = None

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
    # The per-ticker analysis is itself evidence→reason→conclude inside
    # TickerDecision. At the portfolio level, the full set of ticker
    # decisions is the evidence base for the portfolio summary.
    tickers: Dict[str, TickerDecision]

    # PORTFOLIO-LEVEL CONCLUSION — produced after all ticker decisions exist
    portfolio_summary: str              # cross-ticker tensions and overall portfolio posture

    # STRESS SIGNAL — gates the weekly premortem agent
    premortem_flag: bool                # true when any of the four stress conditions fire
    premortem_scenario: Optional[str] = None  # present only when premortem_flag is True