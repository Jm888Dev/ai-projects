```json
{
  "day": 26,
  "date": "2026-07-09",
  "project": "Stock Monitor",
  "last_run_id": "2026-07-09_08:08:52",
  "config_state": {
    "USE_SLM": true,
    "USE_LIVE_DATA": true,
    "USE_LIVE_AGENTS": false,
    "TICKERS": "all 8 active",
    "stage1_primary_max_tokens": 6000,
    "stage2_primary_max_tokens": 6000,
    "translator_primary_max_tokens": 6000
  }
}
```

## What shipped
- `llm_calls.ticker` column: ALTER TABLE + database.py + write_llm_call() + 4 call sites
- `load_captured_prompt()`: ticker filter + ORDER BY rowid DESC (was input_tokens DESC)
- SLM token ceilings: Stage 1/2/Translator primary raised to 6000
- json-repair fallback in extract_json() (shared/utils.py)
- TARGET TICKER framing in run_stage1_agent() prompt
- GROUNDING RULE in Stage 1 system prompts (premature — cleanup queued)

## Full 8-ticker run result
NVDA REDUCE, AVGO REDUCE, LITE REDUCE, TSM HOLD, QQQ REDUCE, SMH REDUCE, G3B.SI REDUCE
3 retries resolved, 0 truncated, 0 errors, 0 warnings

## Next session starts at
Forward Queue item 1 (remove premature GROUNDING RULE from Stage 1 prompts — 10 min cleanup)
Then item 2 (Anthropic tool-use wiring) or item 7 (HDB hygiene) — Mack's call
