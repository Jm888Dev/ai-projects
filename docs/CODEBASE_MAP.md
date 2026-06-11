# CODEBASE_MAP.md
# Stock Monitor — Call chains, file inventory, execution order
# Generated: Day 13 — verified against actual code
# Refresh after major refactors and at Day 24 review.
# Never written from memory — always from actual file inspection.

---

## 1. FILE INVENTORY

| File | Location | Role |
|---|---|---|
| stock_monitor.py | stock-monitor/ | Pipeline orchestrator — main() calls everything |
| config.py | stock-monitor/ | All constants, flags, model routing, thesis, pricing |
| database.py | stock-monitor/ | All schema definitions and every DB read/write function |
| intelligence.py | stock-monitor/ | Manual intelligence stub — replaced by RSS feeds Day 13+ |
| analyst_persona.py | stock-monitor/prompts/ | All six agent system prompts and translator prompt |
| utils.py | shared/ | call_llm(), extract_json(), update_market_history(), save_price_fixtures(), send_email_alert(), format_warning() |
| data_sources.py | shared/ | get_current_prices(), get_intelligence_context() |
| reset_db.py | stock-monitor/tools/ | Drops and reinitialises the database |
| check_tables.py | stock-monitor/tools/ | Prints all tables with row counts |
| set_anthropic_balance.py | stock-monitor/tools/ | Logs API credit topups |
| normal_day.json | stock-monitor/fixtures/ | Price + intelligence fixture |
| fixtures/agents/*.json | stock-monitor/fixtures/agents/ | 37 captured agent outputs |
| .env | stock-monitor/ | API key and email credentials — never commit |
| thesis_overrides.json | stock-monitor/ | Human-approved thesis changes — empty until Day 22+ |
| prices.db | stock-monitor/ | SQLite database — 12 tables |
| DATA_DICTIONARY.md | docs/ | Cumulative schema and function reference |
| CODEBASE_MAP.md | docs/ | This file |

---

## 2. EXECUTION ORDER — main() in stock_monitor.py

| Step | Function | File | DB Write |
|---|---|---|---|
| 1 | database.initialise_db() | database.py | Creates tables, seeds models |
| 2 | database.start_run() | database.py | run_log — status=running |
| 3 | score_persona_call_outcomes() | stock_monitor.py | persona_calls — outcome_5d, outcome_20d |
| 4 | check_kill_triggers() | stock_monitor.py | None — reads signals |
| 5 | check_thesis_staleness() | stock_monitor.py | None — prints warnings |
| 6 | check_portfolio_correlations(run_id) | stock_monitor.py | signals — portfolio_relationship_alert |
| 7 | utils.update_market_history() | shared/utils.py | market_history — delta pull |
| 8 | data_sources.get_current_prices() | shared/data_sources.py | None |
| 9 | database.write_prices() | database.py | prices — one row per ticker |
| 10 | utils.save_price_fixtures() | shared/utils.py | fixtures/normal_day.json if flags set |
| 11 | data_sources.get_intelligence_context() | shared/data_sources.py | None |
| 12 | determine_vix_regime() | stock_monitor.py | None |
| 13 (loop) | build_data_package() per ticker | stock_monitor.py | None |
| 14 (loop) | run_stage1_agent() x4 per ticker | stock_monitor.py | analysis, persona_calls, llm_calls |
| 15 (loop) | run_contrarian() per ticker | stock_monitor.py | analysis, persona_calls, llm_calls |
| 16 | run_meta_agent() | stock_monitor.py | analysis, signals, llm_calls |
| 17 | run_translator() | stock_monitor.py | analysis, llm_calls |
| 18 | display_results() | stock_monitor.py | None |
| 19 | database.finish_run() | database.py | run_log — status=complete |

---

## 3. CALL CHAINS — KEY FUNCTIONS

### call_llm() — most called function in the project
- Called by: run_stage1_agent(), run_contrarian(), run_meta_agent(), run_translator()
- Reads: config.USE_LIVE_AGENTS, config.CAPTURE_LIVE_AGENTS_FOR_FIXTURES, fixtures/agents/*.json
- Side effects: writes fixture files when CAPTURE_LIVE_AGENTS_FOR_FIXTURES=True
- Returns: (text, usage_dict) — usage_dict includes warnings list

### main() call sequence
```
initialise_db → start_run → score_persona_call_outcomes
→ check_kill_triggers → check_thesis_staleness
→ check_portfolio_correlations → update_market_history
→ get_current_prices → write_prices → save_price_fixtures
→ get_intelligence_context → [per-ticker loop]
→ run_meta_agent → run_translator → display_results → finish_run
```

### run_stage1_agent() dependencies
- Calls: call_llm(), extract_json(), database.write_llm_call(), database.write_analysis(), database.write_persona_call()
- Called by: main() — 4 times per ticker, 7 tickers = 28 calls per run
- Returns: (parsed_output, warnings_list)

### build_data_package() dependencies
- Calls: build_chain_summary(), build_historical_context()
- Reads: config.TICKER_THESIS, config.PORTFOLIO_RELATIONSHIPS
- Does NOT call database or Claude API — pure Python string assembly

### check_portfolio_correlations() dependencies
- Calls: database.read_market_history(), database.write_signal()
- Reads: config.CORRELATION_PAIRS
- No LLM call — pure Python/pandas

### score_persona_call_outcomes() dependencies
- Calls: database.get_connection() directly for complex multi-table query
- Reads: persona_calls, market_history, run_log
- Writes: persona_calls.outcome_5d, persona_calls.outcome_20d

---

## 4. WARNING COLLECTION FLOW

```
call_llm() → appends to usage["warnings"]
    ↓
run_stage1_agent() → returns (parsed, usage["warnings"])
run_contrarian()   → returns (parsed, usage["warnings"])
run_meta_agent()   → returns (parsed, usage["warnings"])
run_translator()   → returns (text,   usage["warnings"])
    ↓
main() → run_warnings.extend(agent_warnings)
    ↓
Run summary → consolidated warnings block
```

Format: `SEVERITY | file | function() | description | fix`

---

## 5. MODE FLAG MATRIX

| USE_LIVE_DATA | USE_LIVE_AGENTS | DEV_MODE | Scenario | Cost |
|---|---|---|---|---|
| False | False | True | Full fixture — build/test | $0.00 |
| True | False | True | Live prices + fixture agents | $0.00 |
| False | True | True | Fixture prices + live Haiku | ~$0.05 |
| False | True | False | Fixture prices + live Sonnet | ~$0.30 |
| True | True | True | Full live run — Haiku | ~$0.05 |
| True | True | False | Full live run — Sonnet/demo | ~$0.50 |

Capture flags (apply only when corresponding LIVE flag is True):
- CAPTURE_LIVE_DATA_FOR_FIXTURES — overwrites normal_day.json
- CAPTURE_LIVE_AGENTS_FOR_FIXTURES — overwrites fixtures/agents/
Set both False during prompt tuning to freeze baseline.

---

## 6. DATABASE WRITE SUMMARY PER RUN

| Table | Rows written per run | Written by |
|---|---|---|
| run_log | 1 | start_run() / finish_run() |
| prices | 8 (one per ticker) | write_prices() |
| market_history | 0-N (delta pull) | write_market_history_rows() |
| analysis | ~37 (agents + translator) | write_analysis() |
| signals | ~25 (kill triggers + meta decisions + correlations) | write_signal() |
| persona_calls | ~35 (5 agents x 7 tickers) | write_persona_call() |
| llm_calls | ~37 (one per call_llm() invocation) | write_llm_call() |
| sentences | 0 (populated Day 15) | — |
| thesis_drafts | 0 (populated Day 22+) | — |
| thesis_reviews | 0 (populated Day 22+) | — |
| balance_ledger | 0 (manual topup only) | log_balance_topup() |
| models | 0 (seeded once) | initialise_db() |

---

*Last updated: Day 13 — June 11, 2026*
