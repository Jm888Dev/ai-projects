# Day 24 Handover — Stock Monitor | 2026-06-24

## State
```json
{
  "day": 24,
  "project": "Stock Monitor",
  "last_committed": "Day 24 — Contrarian grounding in analyst_persona.py + load_stage1_outputs(), Item A attention-priority prompt reorder in build_data_package() + build_synthetic_prompt(), document governance redesign",
  "next_queue_item": "schemas.py v1.1 — rename reasoning_trace to reasoning_raw_text, move to FIRST field position, add raw_data_citations list[str] min 2 verbatim numeric data points from input"
}
```

## Pipeline Architecture (don't re-explain, just orient)
Six-agent adversarial pipeline: Stage 1 (Bull/Bear/BlackSwan/Pragmatist, parallel, extreme bias) → Stage 2 Contrarian (epistemic audit, finds hidden consensus) → Stage 3 Meta-Agent (portfolio decisions, ACCUMULATE/HOLD/REDUCE/EXIT) → Translator (plain English). All agents use Pydantic output schemas (prompts/schemas.py). SLM tier routes to Ollama for local inference. Cloud tier routes to Anthropic API.

## SLM Routing — LOCKED (do not re-open)
- Stage 1 xl: qwen3.6:35b-a3b primary (schema-guided, 2400 tokens) / gpt-oss:20b fallback (1800)
- Stage 2 Contrarian xl: qwen3.6:35b-a3b primary (schema-guided, 6000) / Cloud Haiku fallback — NO SLM fallback exists, every other model drifted to G3B.SI on contrarian benchmark
- Stage 3 xxl: gpt-oss:20b primary (schema-guided, 6000) / qwen3.6 fallback
- Preprocessing: phi4-mini prompt-only
- Retired: magistral (schema never engages), gemma4:26b (FSM collapse at small/medium/xl)

## Done (don't re-explain)
- Contrarian ticker grounding: STOCK_CONTRARIAN_SYSTEM_PROMPT now has CRITICAL GROUNDING RULE — model must stay on TARGET TICKER, never switch to G3B.SI or other portfolio tickers. Same grounding in load_stage1_outputs() block header.
- Item A prompt reorder: build_data_package() layer order is now TOP=price+thesis (time-sensitive), MIDDLE=chain+portfolio (accepted attention loss), BOTTOM=hist+intel+triggers+feeds (immediately above output). Mirrors in build_synthetic_prompt().
- Full benchmark grid: all 10 models tested on BullOutput + ContrarianOutput schemas. qwen3.6 only model that passed contrarian xl without drift (twice). All others drifted to G3B.SI.
- Five systemic risks mapped: (1) correlated hallucination → Item C model diversity, (2) linear info decay → raw_data_citations in schemas, (3) lost-in-middle → Item A + tiered injection + KG, (4) schema forced hallucination → reasoning_raw_text first, (5) model diversity → corpus split post-KG.
- Knowledge graph confirmed permanent architecture: item 19 entity schema IS the KG node schema. Graph is queried never injected — each agent receives targeted subgraph 200-500 tokens.
- Document governance: 4 PK uploads only (SESSION_LEDGER 50 lines, DATA_DICTIONARY 500, Master Plan 350, Day Summary 80). Git-only: this handover. New content displaces old.

## Next (in order)
1. schemas.py v1.1: rename reasoning_trace → reasoning_raw_text, move to FIRST field in all six schemas (chain-of-density enforcement — model dumps scratchpad before committing to structured output). Add raw_data_citations: list[str] min 2 verbatim numeric data points. Add instruction requiring ≥1 middle-layer data point citation. Update all downstream parsers referencing reasoning_trace.
2. Wire locked routing into SLM_STAGE_MODELS in config.py
3. Schema-guided production wiring in _call_ollama(): add optional schema_dict parameter, pass to Ollama format key. Pre-production check: verify gpt-oss holds ticker discipline in MetaAgentOutput per-ticker dict at xxl (Stage 3 exposure untested — it drifted at Stage 2).
4. Item 19 graph-first: full article extraction + Layer 7 entity/event classification. Entity schema must carry stable entity IDs, typed relationships (EXPOSED_TO, REGULATED_BY...), source provenance, impact scores. Tiered injection: Bear/BlackSwan get full article text, Bull/Pragmatist get 150-word standardised summaries.

## Parked (don't ask about these)
- OQ-Day24-A: why only qwen3.6 resists contrarian drift — thinking-mode hypothesis, qwen3:8b dense test designed but skipped (same-family fallback violates diversity principle). RISK: qwen3.6 could drift for unknown reasons. Post-KG.
- Non-Qwen Stage 2 SLM fallback: every model tested drifted on contrarian xl. Cloud Haiku is interim fallback. Hunt deferred post-KG.
- Item C Stage 1 corpus-diversity split: Bull/Pragmatist → gpt-oss (Western corpus), Bear/BlackSwan → qwen3.6 (Chinese corpus, different export-control priors). Agreed, deferred post-KG.
- Asymmetric debate loop: Pragmatist + BlackSwan critique Bull/Bear outputs before Contrarian sees them. Queue after Arbitrator (item 13).
- XML anchoring Layer 3/4: wrap middle layers in XML tags to make accepted-loss zone searchable. Cloud path first, verify SLM equivalence before assuming.

## Open Questions (don't answer yet)
- OQ-Day21-A: schema-guided decoding may introduce directional bias — never mix prompt-only and schema-guided runs in calibration data without decode_mode tag
- OQ-Day21-B: do fixed schemas limit feed context from 20+ sources — answer when item 19 is live
- OQ-Day21-C: gemma4:26b collapse — partially resolved, context-size/budget-dependent
- OQ-Day23-A: content drift — phi4-mini filled ticker=NVDA correctly but reasoning body discussed LITE. Semantic check needed, current harness only detects field-level mismatch.
- OQ-Day24-B: does Item A prompt reorder measurably improve mid-context attention — answer via eval harness (item 17)
- OQ-Day24-C: does KG hierarchical retrieval prevent lost-in-the-middle at scale — answer at item 26

## Key Decisions (locked — do not re-open)
- SLM routing locked Day 24 — see routing table above
- Item D resolved: keep full data package for Contrarian, rely on Item A reorder. No build_contrarian_data_package().
- KG built through queue via item 19 graph-first output — not early as empty container
- magistral retired permanently across all routing consideration
- gemma4:26b retired from schema-guided routing — use prompt-only only
- Document governance: 4 PK uploads, Git-only handover, hard line ceilings enforced from Day 25 onward
