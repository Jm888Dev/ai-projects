# Day 27 Summary — Stock Monitor | 2026-07-10

## What was built

1. **GROUNDING RULE cleanup (Item 1)** — 3-line GROUNDING RULE block removed from top
   of Bull, Bear, Black Swan, Pragmatist system prompts in `analyst_persona.py`.
   Contrarian's `CRITICAL GROUNDING RULE` (line 627) untouched — different, legitimate.
   Verified by grep (one remaining instance — Contrarian only). Syntax PASS.

2. **Anthropic tool-use wiring (Item 2)** — three files:
   - `shared/utils.py`: `output_schema=None` added to `call_llm()`. `_attempt()`
     conditionally adds `tools` + `tool_choice` when schema provided. Extracts
     `tool_block.input`, serialises to `json.dumps()` so `extract_json()` downstream
     is unchanged. `stop_reason="tool_use"` on success — existing `=="max_tokens"`
     truncation check still correct.
   - `stock_monitor.py`: Schema imports from `prompts.schemas`. `_resolve_schema(call_type)`
     added — maps call_type prefix to `.model_json_schema()`, returns None for Translator
     (plain text path). Cloud branch of `sm_call_llm()` resolves and passes `output_schema`.
     Docstring updated for USE_SLM=False path.
   - `stock_monitor.py` truncation bug fixed: previous session's edit chain had truncated
     file at line 2137 (open f-string). Tail restored from `git show HEAD`.

3. **Config fixes** — Duplicate `USE_SLM = True` at line 649 removed (was silently
   overriding line 635 since Day 25 — every config.py import set USE_SLM=True regardless
   of the line 635 value). `_SONNET` updated `claude-sonnet-4-6` → `claude-sonnet-5`
   (current model string per Anthropic docs July 2026). `MODEL_PRICING` and
   `SHADOW_COST_SONNET_MODEL` updated to match.

4. **Cloud token budgets raised** — confirmed by two live runs:
   - Run 1 (old budgets): 28 retries, 13 still truncated, 1301s
   - `STAGE_1_MAX_TOKENS` 1200→2500 (Black Swan failed at 1800)
   - `STAGE_2_MAX_TOKENS` 2000→4000 (Contrarian failed at 3000)
   - `STAGE_3_MAX_TOKENS` 4000→6000 (resolved at 6000)
   - Run 2 (new budgets): 0 retries, 0 truncations, 0 errors, 770s ✓

## What was learned

- Anthropic `tool_use` is the cloud FSM equivalent: force-calls a named tool with JSON
  Schema `input_schema`; response is parsed Python dict in `tool_block.input`. Interface
  preserved by serialising back to `json.dumps()` — all downstream callers unchanged.
- Cost tracker counts only final-call tokens. Retries re-send full input — Anthropic
  billed ~$1 vs $0.55 reported (28 retry calls each resending full prompt, uncounted).
- Cowork mode mounts the selected folder (`ai-projects`) into a Linux sandbox — bash +
  git accessible within that scope.
- `claude-sonnet-4-6` is an outdated model string; `claude-sonnet-5` is current (July 2026).

## Session contract additions (permanent, logged to memory)

- **Ask before reading:** explain what file and why before any read. Mack decides.
- **Show-don't-do:** show exact diff, Mack applies. No direct edits.

## Open questions logged

- **OQ-Day27-A:** Cost tracker counts only final-call tokens. Retries re-send full input;
  Anthropic bills both. Fix: accumulate tokens across all `_attempt()` calls before logging.

## State at close

Production defaults confirmed: `USE_SLM=True`, `USE_LIVE_DATA=True`,
`USE_LIVE_AGENTS=False`, `DEV_MODE=True`.

## CODEBASE_MAP trigger

YES — `_resolve_schema()` added to `stock_monitor.py` (new function); `call_llm()`
call chain changed (output_schema parameter + tool_use branch). Refresh needed before
next session that touches these paths.
