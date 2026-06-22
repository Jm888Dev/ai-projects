# CODEBASE_MAP.md
**Stock Monitor — File Inventory, Call Chains, Execution Order**
Generated from actual code — never from memory. Refresh after major refactors and at dedicated review sessions.
Last verified: Day 20 (against Day 15 state — next refresh due after first queue item that touches architecture).

---

## 1. File Inventory

| File | Location | Role |
|---|---|---|
| stock_monitor.py | stock-monitor/ | Pipeline orchestrator. Contains three project wrappers: sm_call_llm, sm_save_price_fixtures, sm_send_email_alert |
| config.py | stock-monitor/ | All constants, flags, model routing, thesis, pricing, path constants |
| database.py | stock-monitor/ | All schema definitions and every DB read/write function |
| feeds.py | stock-monitor/ | Feed ingestion, scoring, storage, injection |
| intelligence.py | stock-monitor/ | Manual intelligence stub — superseded by feeds.py for live sources |
| analyst_persona.py | stock-monitor/prompts/ | All six agent system prompts and translator prompt |
| utils.py | shared/ | Config-free shared utilities. Never imports either project's config. |
| data_sources.py | shared/ | get_current_prices(), get_intelligence_context() |
| reset_db.py | stock-monitor/tools/ | Drops and reinitialises the database. Auto-backup before delete. |
| check_tables.py | stock-monitor/tools/ | Prints all tables with row counts |
| set_anthropic_balance.py | stock-monitor/tools/ | Logs API credit topups |
| slm_benchmark.py | stock-monitor/tools/ | Benchmarks Ollama models at real captured prompt sizes |
| feeds_audit.py | stock-monitor/tools/ | Health checker for all 22 sources |
| normal_day.json | stock-monitor/fixtures/ | Price + intelligence fixture |
| fixtures/agents/*.json | stock-monitor/fixtures/agents/ | 37 captured agent outputs |
| prices.db | stock-monitor/ | SQLite database — 12 tables |
| hdb_analyser.py | hdb-analyser/ | Main pipeline |
| config.py | hdb-analyser/ | All HDB constants |
| analyst_persona.py | hdb-analyser/prompts/ | Analyst and translator system prompts |

---

## 2. Execution Order — main() in stock_monitor.py

| Step | Function | File | DB Write |
|---|---|---|---|
| 1 | database.initialise_db() | database.py | Creates tables, seeds models |
| 2 | database.start_run() | database.py | run_log — status=running |
| 3 | score_persona_call_outcomes() | stock_monitor.py | persona_calls — outcome_5d, outcome_20d |
| 4 | check_stuck_runs() | stock_monitor.py | run_log — marks stale running rows failed |
| 5 | check_kill_triggers() | stock_monitor.py | None — reads signals |
| 6 | check_thesis_staleness() | stock_monitor.py | None — prints warnings |
| 7 | check_portfolio_correlations(run_id) | stock_monitor.py | signals — portfolio_relationship_alert |
| 8 | fetch_and_store_feeds() | stock-monitor/feeds.py | feeds table |
| 9 | utils.update_market_history() | shared/utils.py | market_history — delta pull |
| 10 | data_sources.get_current_prices() | shared/data_sources.py | None |
| 11 | database.write_prices() | database.py | prices |
| 12 | sm_save_price_fixtures(price_data) | stock_monitor.py wrapper | fixtures/normal_day.json if flags set |
| 13 | data_sources.get_intelligence_context() | shared/data_sources.py | None |
| 14 | determine_vix_regime() | stock_monitor.py | None |
| 15 (loop) | build_data_package() per ticker | stock_monitor.py | None — calls build_feed_injection() |
| 16 (loop) | run_stage1_agent() × 4 per ticker | stock_monitor.py | analysis, persona_calls, llm_calls |
| 17 (loop) | run_contrarian() per ticker | stock_monitor.py | analysis, persona_calls, llm_calls |
| 18 | run_meta_agent() | stock_monitor.py | analysis, signals, llm_calls |
| 19 | run_translator() | stock_monitor.py | analysis, llm_calls |
| 20 | display_results() | stock_monitor.py | None |
| 21 | database.finish_run() | database.py | run_log — status=complete |

---

## 3. Non-Negotiable Architectural Rules

**Rule 1 — Config isolation:**
shared/utils.py must never import either project's config.py. Shared functions receive config-dependent values as parameters injected by project wrappers. Violating this poisons the importing project's config via sys.modules caching (discovered Day 15). Enforce at every code review. No exceptions.

**Rule 2 — Sovereignty:**
_call_ollama() must only ever POST to localhost or 127.0.0.1. A ValueError is raised if any other base_url is passed.

**Rule 3 — num_ctx formula:**
Every Ollama call must size its context window explicitly. Never rely on Ollama's default (~2048 tokens) — it silently truncates without warning (discovered Day 19).
```
required_ctx = min(
    (len(prompt) / OLLAMA_CHARS_PER_TOKEN_ESTIMATE) + max_tokens + OLLAMA_NUM_CTX_SAFETY_MARGIN,
    OLLAMA_MODEL_MAX_CTX[model],
    OLLAMA_NUM_CTX_HARDWARE_CAP
)
```

---

## 4. Call Chains — Key Functions

### Project wrappers (stock_monitor.py)
The only place Stock Monitor config values are injected into shared functions. Call sites use wrappers, never raw shared functions directly.

```
sm_call_llm(**kwargs)
  → injects: USE_LIVE_AGENTS, CAPTURE_LIVE_AGENTS_FOR_FIXTURES, FIXTURE_DIR,
             SLM model resolution from SLM_STAGE_MODELS,
             shadow cost computation against MODEL_PRICING
  → calls: shared/utils.call_llm()
  → called by: run_stage1_agent(), run_contrarian(), run_meta_agent(), run_translator()

sm_save_price_fixtures(price_data)
  → injects: PRICE_FIXTURE_PATH, CAPTURE_LIVE_DATA_FOR_FIXTURES
  → calls: shared/utils.save_price_fixtures()

sm_send_email_alert(subject, body)
  → injects: ENV_PATH, project_tag='Stock Monitor'
  → calls: shared/utils.send_email_alert()
```

### call_llm() — most called function
- Lives in: shared/utils.py
- Called via: sm_call_llm() wrapper only — never called directly from pipeline
- Returns: (text, usage_dict) — usage_dict includes warnings list AND prompt_text
- Config dependency: NONE — all config values injected by caller

### Warning collection flow
```
sm_call_llm() → call_llm() → appends to usage["warnings"]
  ↓
run_stage1_agent()  → returns (parsed, usage["warnings"])
run_contrarian()    → returns (parsed, usage["warnings"])
run_meta_agent()    → returns (parsed, usage["warnings"])
run_translator()    → returns (text,   usage["warnings"])
  ↓
main() → run_warnings.extend(agent_warnings)
  ↓
Run summary → consolidated warnings block
```

### run_pipeline() — Task Scheduler entry point
- Wraps main() in try/except
- Sends email alert on crash (live runs only)
- Called by: if __name__ == '__main__'

---

## 5. Shared Module Dependency Map

```
stock_monitor.py
  ├── import config                     (stock-monitor/config.py)
  ├── import database                   (stock-monitor/database.py)
  ├── from stock_monitor.feeds import   (stock-monitor/feeds.py)
  ├── from shared.utils import ...      (shared/utils.py — config-free)
  ├── from shared.data_sources import   (shared/data_sources.py)
  └── wrappers: sm_call_llm, sm_save_price_fixtures, sm_send_email_alert
        └── inject config values at call time

shared/utils.py
  ├── NO config imports — ever
  └── Functions: call_llm, _call_ollama, save_price_fixtures, send_email_alert,
                 format_warning, extract_json, update_market_history

hdb_analyser.py
  ├── import config                     (hdb-analyser/config.py)
  └── from shared.utils import extract_json
      (calls client.messages.create() directly — no hdb_call_llm wrapper yet)
```

---

## 6. Database Write Summary Per Run

| Table | Rows Per Run | Written By |
|---|---|---|
| run_log | 1 | start_run() / finish_run() |
| prices | 8 (one per ticker) | write_prices() |
| market_history | 0–N (delta pull) | write_market_history_rows() |
| feeds | 0–N (new headlines only, UNIQUE dedup) | fetch_and_store_feeds() |
| analysis | ~37 | write_analysis() |
| signals | ~25 | write_signal() |
| persona_calls | ~35 | write_persona_call() |
| llm_calls | ~37 | write_llm_call() |
| thesis_drafts / thesis_reviews | 0 (populated Day 27+) | — |
| balance_ledger | 0 (manual only) | log_balance_topup() |
| sentences | 0 (future) | — |

---

## 7. Mode Flag Matrix

| USE_LIVE_DATA | USE_LIVE_AGENTS | DEV_MODE | Scenario | Cost |
|---|---|---|---|---|
| False | False | True | Full fixture — build/test | $0.00 |
| True | False | True | Live prices + fixture agents | $0.00 |
| False | True | True | Fixture prices + live Haiku | ~$0.05 |
| False | True | False | Fixture prices + live Sonnet | ~$0.30 |
| True | True | True | Full live — Haiku | ~$0.05 |
| True | True | False | Full live — Sonnet/demo | ~$0.50 |

Capture flags apply only when the corresponding LIVE flag is True. Set both False during prompt tuning to freeze baseline.

---

## 8. Known Issues / Deferred Fixes

| Issue | Severity | Fix | Status |
|---|---|---|---|
| config.DB_PATH uses bare relative path | Low | Apply Path(__file__).parent fix (same class as Day 15 fix) | Deferred |
| STAGE_3_MAX_TOKENS=4000 required a retry in Day 19 live run | Low | Consider raising default to 6000 | Flagged for Day 28 config review |
| hdb_analyser.py calls client.messages.create() directly | Low | Add hdb_call_llm wrapper following sm_call_llm pattern | Deferred |
| first_time_buyer backward-compat boolean still in BUYER_PROFILE | Cleanup | Remove once buyer_type confirmed stable | Next HDB hygiene session |

---

*Last updated: Day 20. Next refresh: after first queue item that modifies file structure or call chains.*
