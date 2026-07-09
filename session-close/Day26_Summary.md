# Day 26 Summary — Stock Monitor | 2026-07-09

## What was built

1. **`llm_calls.ticker` column** — `ALTER TABLE llm_calls ADD COLUMN ticker TEXT`
   applied to live prices.db. `database.py` CREATE TABLE updated. `write_llm_call()`
   signature extended with `ticker=None`. Four call sites in `stock_monitor.py` updated:
   `stage1_*` calls pass `ticker=ticker`; `stage3_meta_agent` and `translator` pass
   `ticker="portfolio"`. This is the correct fix for the benchmark data-source bug.

2. **`load_captured_prompt()` fixed in `tools/slm_benchmark.py`** — Added `ticker`
   parameter. Both SQL queries updated: `AND (? IS NULL OR ticker = ?)` filter added,
   `ORDER BY input_tokens DESC` replaced with `ORDER BY rowid DESC`. Callers updated:
   xl call site passes `ticker=EXPECTED_TICKER`; xxl call site passes
   `ticker="portfolio"`. Root cause confirmed: June 16 G3B.SI run had higher input
   tokens than any NVDA run, so `ORDER BY input_tokens DESC` always loaded G3B.SI
   regardless of which ticker was under test. Models were correct — the test harness
   was wrong.

3. **SLM token ceilings raised** — Stage 1 primary 2400→6000, fallback 1800→4800.
   Stage 2 primary 3600→6000. Translator primary 2400→6000, fallback 1800→4800.
   Validated by full 8-ticker live run: 3 retries fired and resolved, 0 still truncated.

4. **json-repair fallback in `extract_json()`** (`shared/utils.py`) — On `json.JSONDecodeError`,
   attempts `repair_json(clean, return_objects=True)` before returning failure. Handles
   missing string-open quotes (the specific QQQ bear failure mode: `"primary_argument":
   QQQ's core thesis...` without opening quote). Tested on real malformed output — PASS.

5. **TARGET TICKER framing in `run_stage1_agent()`** — Prompt now opens with
   `"TARGET TICKER FOR THIS ANALYSIS: {ticker}\nReason about {ticker} only."` before
   the data package. Adds explicit call-site grounding independent of system prompt.

6. **Grounding rules added to Stage 1 system prompts** — GROUNDING RULE block added
   to top of Bull, Bear, Black Swan, Pragmatist system prompts. **Flagged as premature**
   — the drift was a code bug, not a model anchoring failure. These lines are harmless
   but unnecessary. Cleanup logged for next hygiene session.

7. **Full 8-ticker live SLM run** — Run ID `2026-07-09_08:08:52`. All 7 tickers
   analyzed correctly by their own agents. 0 errors, 0 warnings. QQQ bear JSON parse
   failure recovered by json-repair in production. Translator completed without
   truncation (3,877 tokens). Pipeline output: NVDA REDUCE, AVGO REDUCE, LITE REDUCE,
   TSM HOLD, QQQ REDUCE, SMH REDUCE, G3B.SI REDUCE.

## What was learned

- **Benchmark data-source bug vs model failure are indistinguishable without reading the SQL.**
  `ORDER BY input_tokens DESC` silently prioritized a historical G3B.SI run over all
  NVDA runs. Looked like G3B.SI anchoring. Was deterministic mislabeling.
- **Fix root cause before patching symptoms.** Grounding rules were added to prompts
  before the actual cause (wrong SQL ordering) was identified. The prompts already had
  ticker grounding — more was unnecessary.
- **json-repair is conservative and correct** for the missing-quote failure mode.
  Does not over-repair; returns empty on ambiguous input.
- **QQQ bear `regime_sensitivity` logic inverted** — model wrote "weakens in high_vix"
  for a bear thesis (should strengthen). Content quality gap, not structural failure.
  Logged for prompt review.

## Open questions logged

- **OQ-Day26-A:** QQQ bear `regime_sensitivity` field inverted — bear thesis should
  strengthen in high_vix, not weaken. Likely a prompt instruction gap. Review bear
  system prompt `regime_sensitivity` field guidance.
- **Cleanup:** Remove premature GROUNDING RULE lines from Stage 1 system prompts
  (Bull, Bear, Black Swan, Pragmatist). Harmless but unnecessary.

## State at close

Config is in correct production state: `USE_SLM=True`, `USE_LIVE_DATA=True`,
all 8 TICKERS active. No reverts needed.

## Next session

Forward queue item 1 (OQ-Day25-A) is partially resolved — token budgets raised
and empirically validated by 8-ticker live run. Formal benchmark re-run against
NVDA captures still pending but lower urgency now that live run confirms stability.
Next priority: item 2 (Anthropic tool-use wiring for LLM path) or item 6 (HDB hygiene).
