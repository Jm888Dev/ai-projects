# CODEBASE_MAP.md
# Stock Monitor — Call chains, file inventory, execution order
# Generated: Day 15 — verified against actual code
# Refresh after major refactors and at Day 24 review.
# Never written from memory — always from actual file inspection.

---

## 1. FILE INVENTORY

| File | Location | Role |
|---|---|---|
| stock_monitor.py | stock-monitor/ | Pipeline orchestrator — main() calls everything. Contains three project wrappers: sm_call_llm, sm_save_price_fixtures, sm_send_email_alert |
| config.py | stock-monitor/ | All constants, flags, model routing, thesis, pricing. Includes FIXTURE_DIR, PRICE_FIXTURE_PATH, ENV_PATH path constants added Day 15 |
| database.py | stock-monitor/ | All schema definitions and every DB read/write function |
| intelligence.py | stock-monitor/ | Manual intelligence stub — replaced by RSS feeds Day 21 |
| analyst_persona.py | stock-monitor/prompts/ | All six agent system prompts and translator prompt |
| utils.py | shared/ | Config-free shared utilities: call_llm(), extract_json(), update_market_history(), save_price_fixtures(), send_email_alert(), format_warning(). Never imports either project config — callers inject config via project wrappers. |
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
| SESSION_LEDGER.md | docs/ | One row per day — features, learning, lessons |
| OPEN_QUESTIONS.md | docs/ | Backlog and design decisions with gating conditions |
| Day15_Spec.json | docs/ | Machine-readable handover spec — what was built, what is deferred |

---

## 2. EXECUTION ORDER — main() in stock_monitor.py

| Step | Function | File | DB Write |
|---|---|---|---|
| 1 | database.initialise_db() | database.py | Creates tables, seeds models |
| 2 | database.start_run() | database.py | run_log — status=running |
| 3 | score_persona_call_outcomes() | stock_monitor.py | persona_calls — outcome_5d, outcome_20d |
| 4 | check_stuck_runs() | stock_monitor.py | run_log — marks stale running rows failed |
| 5 | check_kill_triggers() | stock_monitor.py | None — reads signals |
| 6 | check_thesis_staleness() | stock_monitor.py | None — prints warnings |
| 7 | check_portfolio_correlations(run_id) | stock_monitor.py | signals — portfolio_relationship_alert |
| 8 | utils.update_market_history() | shared/utils.py | market_history — delta pull |
| 9 | data_sources.get_current_prices() | shared/data_sources.py | None |
| 10 | database.write_prices() | database.py | prices — one row per ticker |
| 11 | sm_save_price_fixtures(price_data) | stock_monitor.py (wrapper) | fixtures/normal_day.json if flags set |
| 12 | data_sources.get_intelligence_context() | shared/data_sources.py | None |
| 13 | determine_vix_regime() | stock_monitor.py | None |
| 14 (loop) | build_data_package() per ticker | stock_monitor.py | None |
| 15 (loop) | run_stage1_agent() x4 per ticker | stock_monitor.py | analysis, persona_calls, llm_calls |
| 16 (loop) | run_contrarian() per ticker | stock_monitor.py | analysis, persona_calls, llm_calls |
| 17 | run_meta_agent() | stock_monitor.py | analysis, signals, llm_calls |
| 18 | run_translator() | stock_monitor.py | analysis, llm_calls |
| 19 | display_results() | stock_monitor.py | None |
| 20 | database.finish_run() | database.py | run_log — status=complete |

---

## 3. CALL CHAINS — KEY FUNCTIONS

### ARCHITECTURAL RULE — NON-NEGOTIABLE
shared/utils.py must never import either project's config.py. Shared functions receive
config-dependent values as parameters from the caller. Each project defines thin wrappers
that inject its own config values once. Violating this poisons the importing project's
config via sys.modules caching. Enforce at every code review. No exceptions.

---

### Project wrappers — stock_monitor.py (Day 15)
The only place Stock Monitor config values are injected into shared functions.
Call sites use wrappers, never raw shared functions directly.

```
sm_call_llm(**kwargs)
  → injects: config.USE_LIVE_AGENTS, config.CAPTURE_LIVE_AGENTS_FOR_FIXTURES, config.FIXTURE_DIR
  → forwards: all caller kwargs untouched via **kwargs
  → calls: shared/utils.call_llm()
  → called by: run_stage1_agent(), run_contrarian(), run_meta_agent(), run_translator()

sm_save_price_fixtures(price_data)
  → injects: config.PRICE_FIXTURE_PATH, config.CAPTURE_LIVE_DATA_FOR_FIXTURES
  → calls: shared/utils.save_price_fixtures()
  → called by: main() when USE_LIVE_DATA=True

sm_send_email_alert(subject, body)
  → injects: config.ENV_PATH, project_tag='Stock Monitor'
  → calls: shared/utils.send_email_alert()
  → called by: run_meta_agent() on REDUCE/EXIT confidence >= 4, run_pipeline() on crash
```

---

### call_llm() — most called function in the project
- Lives in: shared/utils.py
- Called by: sm_call_llm() wrapper in stock_monitor.py (never called directly from pipeline)
- Parameters: prompt, system, model, max_tokens, temperature, fallback_model, client,
  call_type, use_live_agents, capture_fixtures, fixture_dir
- Reads: fixture_dir parameter (never hardcoded path), use_live_agents parameter
- Side effects: writes fixture files when use_live_agents=True and capture_fixtures=True
- Returns: (text, usage_dict) — usage_dict includes warnings list
- Config dependency: NONE — all config values injected by caller via sm_call_llm()

### main() call sequence
```
initialise_db → start_run → score_persona_call_outcomes → check_stuck_runs
→ check_kill_triggers → check_thesis_staleness
→ check_portfolio_correlations → update_market_history
→ get_current_prices → write_prices → sm_save_price_fixtures
→ get_intelligence_context → [per-ticker loop]
→ run_meta_agent → run_translator → display_results → finish_run
```

### run_stage1_agent() dependencies
- Calls: sm_call_llm(), extract_json(), database.write_llm_call(), database.write_analysis(), database.write_persona_call()
- Called by: main() — 4 times per ticker, 7 tickers = 28 calls per run
- Returns: (parsed_output, warnings_list)

### run_contrarian() dependencies
- Calls: sm_call_llm(), extract_json(), database.write_llm_call(), database.write_analysis(), database.write_persona_call()
- Called by: main() — once per ticker
- Returns: (parsed_output, warnings_list)

### run_meta_agent() dependencies
- Calls: sm_call_llm(), extract_json(), database.write_llm_call(), database.write_analysis(), database.write_signal(), sm_send_email_alert()
- Called by: main() — once per run
- Returns: (parsed_output, warnings_list)

### run_translator() dependencies
- Calls: sm_call_llm(), database.write_llm_call(), database.write_analysis()
- Called by: main() — once per run
- Returns: (text, warnings_list)

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

### run_pipeline() — entry point for Task Scheduler
- Calls: main(), sm_send_email_alert() on crash
- Called by: if __name__ == '__main__'
- Purpose: crash recovery wrapper — catches unhandled exceptions, emails on live runs

---

## 4. WARNING COLLECTION FLOW

```
sm_call_llm() → call_llm() → appends to usage["warnings"]
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

All warnings built via format_warning() in shared/utils.py — never free-form strings.

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
- CAPTURE_LIVE_DATA_FOR_FIXTURES — overwrites normal_day.json. Passed to sm_save_price_fixtures() via config.CAPTURE_LIVE_DATA_FOR_FIXTURES.
- CAPTURE_LIVE_AGENTS_FOR_FIXTURES — overwrites fixtures/agents/. Passed to call_llm() via sm_call_llm() wrapper.
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
| llm_calls | ~37 (one per sm_call_llm() invocation) | write_llm_call() |
| sentences | 0 (populated Day 20) | — |
| thesis_drafts | 0 (populated Day 22+) | — |
| thesis_reviews | 0 (populated Day 22+) | — |
| balance_ledger | 0 (manual topup only) | log_balance_topup() |
| models | 0 (seeded once) | initialise_db() |

---

## 7. SHARED MODULE DEPENDENCY MAP

```
stock_monitor.py
  ├── import config                    (stock-monitor/config.py)
  ├── import database                  (stock-monitor/database.py)
  ├── from shared.utils import ...     (shared/utils.py — config-free)
  ├── from shared.data_sources import  (shared/data_sources.py)
  └── wrappers: sm_call_llm, sm_save_price_fixtures, sm_send_email_alert
        └── inject config values into shared functions at call time

shared/utils.py
  ├── NO config imports — ever
  ├── Receives config values as parameters from caller wrappers
  └── Functions: call_llm, save_price_fixtures, send_email_alert,
                 format_warning, extract_json, update_market_history

hdb_analyser.py
  ├── import config                    (hdb-analyser/config.py)
  ├── from shared.utils import extract_json
  └── calls client.messages.create() directly (no shared call_llm yet)
      Day 16+: will add hdb_call_llm wrapper following same pattern
```

---

*Last updated: Day 15 — June 12, 2026*
