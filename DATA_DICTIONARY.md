# DATA_DICTIONARY.md
# Stock Monitor — Cumulative Data Dictionary
# Generated: Day 13 — verified against actual database.py and config.py
# Update this file at the end of every session alongside the Day N summary.
# This is a living document — it describes current reality, not history.
# When this conflicts with a Day summary, this document wins.

---

## 1. DATABASE TABLES (prices.db)

### models
Reference table — normalised model registry. Seeded at initialise_db().

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| model_id | TEXT UNIQUE | e.g. claude-haiku-4-5-20251001 |
| alias | TEXT | e.g. haiku-4-5 |
| provider | TEXT DEFAULT anthropic | anthropic / ollama (Day 25) |
| tier | TEXT | haiku / sonnet / opus / slm |

Seeded rows: claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-8

---

### prices
One row per ticker per run. Audit trail of what each agent saw at moment of reasoning. Separate from market_history which is the canonical daily close record.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT NOT NULL | JOIN key — links to run_log |
| timestamp | TEXT NOT NULL | ISO datetime of capture |
| ticker | TEXT NOT NULL | e.g. NVDA, G3B.SI |
| instrument_type | TEXT | equity / etf / index |
| price | REAL | Price at moment of capture |
| prev_close | REAL | Previous session close |
| pct_change | REAL | (price - prev_close) / prev_close * 100 |
| capture_context | TEXT DEFAULT unclassified | market_open_normal / market_closed_after_hours / etc |
| intraday_position | REAL | 0.0=day low, 1.0=day high, NULL if closed |
| reconciliation | TEXT DEFAULT unresolved | close_matched / intraday_capture / unresolved |

---

### market_history
Canonical OHLCV record per ticker per trading day. 5-year backfill on first run, delta pull each session. This is market truth — prices table is agent context.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| ticker | TEXT NOT NULL | e.g. NVDA |
| trade_date | TEXT NOT NULL | YYYY-MM-DD |
| open | REAL | Opening price |
| high | REAL | Day high |
| low | REAL | Day low |
| close | REAL | Closing price — canonical |
| volume | INTEGER | Daily volume |
| pct_change | REAL | Daily percentage change |
| source | TEXT DEFAULT yfinance | yfinance / fixture |
| inserted_at | TEXT NOT NULL | ISO datetime of insert |

UNIQUE constraint on (ticker, trade_date) — INSERT OR IGNORE prevents duplicates.

---

### analysis
Raw Claude outputs. One row per agent call per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT NOT NULL | JOIN key |
| timestamp | TEXT NOT NULL | ISO datetime |
| analysis_type | TEXT NOT NULL | bull / bear / black_swan / pragmatist / contrarian / meta_agent / translator |
| ticker | TEXT | NULL for portfolio-level calls (meta_agent, translator) |
| source | TEXT NOT NULL | stock_monitor |
| output | TEXT NOT NULL | Raw Claude response text |
| truncated | INTEGER DEFAULT 0 | 1 if output hit token limit |

---

### signals
Derived signals. One row per flagged condition per run. Decision history of the pipeline.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT NOT NULL | JOIN key |
| timestamp | TEXT NOT NULL | ISO datetime |
| ticker | TEXT NOT NULL | Ticker the signal applies to |
| signal_type | TEXT NOT NULL | See signal_type values below |
| value | REAL | The measured value (e.g. correlation coefficient) |
| threshold | REAL | The threshold it was compared against |
| triggered | INTEGER DEFAULT 0 | 1=condition fired, 0=evaluated but not triggered |
| direction | TEXT | ACCUMULATE / HOLD / REDUCE / EXIT |
| persona | TEXT | Which agent raised the signal |
| entity_a | TEXT | Graph edge candidate — Day 45+ |
| relationship | TEXT | Graph edge candidate — Day 45+ |
| entity_b | TEXT | Graph edge candidate — Day 45+ |
| notes | TEXT | Human-readable explanation |
| outcome | TEXT | correct / incorrect / partial / void — filled T+3 |
| resolved_by_run_id | TEXT | Run that scored the outcome |
| human_override | INTEGER DEFAULT 0 | 1 if manually overridden |
| divergence_score | INTEGER | 1=magnitude only, 2-3=directional disagreement |

**signal_type values:**
- `kill_trigger` — pre-committed exit condition (triggered=0) or fired condition (triggered=1)
- `meta_decision` — portfolio manager ACCUMULATE/HOLD/REDUCE/EXIT per ticker
- `portfolio_relationship_alert` — correlation threshold breach
- `divergence` — agent directional disagreement
- `premortem` — stress test fired
- `persistent_divergence` — divergence auto-escalated after 5 sessions

---

### run_log
Pipeline health. One row per run. status stays 'running' if pipeline crashes.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT UNIQUE | YYYY-MM-DD_HH:MM:SS — primary JOIN key |
| started_at | TEXT NOT NULL | ISO datetime |
| completed_at | TEXT | NULL if crashed |
| status | TEXT DEFAULT running | running / complete / failed |
| data_mode | TEXT DEFAULT fixture | live / fixture |
| tickers_attempted | INTEGER | Total tickers in run |
| tickers_succeeded | INTEGER | Tickers with price data |
| tickers_failed | INTEGER | Tickers with no price data |
| analyst_input_tokens | INTEGER | Total Stage 1-3 input tokens |
| analyst_output_tokens | INTEGER | Total Stage 1-3 output tokens |
| translator_input_tokens | INTEGER | Translator input tokens |
| translator_output_tokens | INTEGER | Translator output tokens |
| analyst_duration_secs | REAL | Wall clock for agent calls |
| translator_duration_secs | REAL | Wall clock for translator |
| fallback_used | INTEGER | 1 if fallback model used |
| error_count | INTEGER | Errors during run |
| total_cost_usd | REAL | Sum of llm_calls.cost_usd |
| notes | TEXT | Free text |

---

### llm_calls
Full LLM audit trail. One row per call_llm() invocation.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT NOT NULL | JOIN key |
| timestamp | TEXT NOT NULL | ISO datetime |
| call_type | TEXT NOT NULL | stage1_bull / stage1_bear / stage2_contrarian / stage3_meta_agent / translator |
| model_requested | TEXT NOT NULL | Model requested in config |
| model_used | TEXT | Actual model used (may be fallback or fixture:call_type) |
| fallback_used | INTEGER DEFAULT 0 | 1 if fallback triggered |
| input_tokens | INTEGER | Tokens in prompt |
| output_tokens | INTEGER | Tokens in response |
| duration_secs | REAL | Call wall clock |
| cost_usd | REAL | Computed from MODEL_PRICING at insert time |
| status | TEXT DEFAULT success | success / fallback / error |
| error_message | TEXT | Error text if status=error |
| retried | INTEGER DEFAULT 0 | 1 if truncation retry triggered |
| truncated | INTEGER DEFAULT 0 | 1 if still truncated after retry |
| retry_budget | INTEGER | Token budget used on retry |

---

### sentences
RAG source — Day 20. Currently 0 rows. Populated Day 20.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT NOT NULL | JOIN key |
| timestamp | TEXT NOT NULL | ISO datetime |
| source_table | TEXT NOT NULL | analysis |
| source_id | INTEGER NOT NULL | analysis.id |
| analysis_type | TEXT NOT NULL | bull / bear / etc |
| persona | TEXT | Which agent |
| section | TEXT NOT NULL | Section of analysis |
| sentence | TEXT NOT NULL | Individual sentence |
| tickers_mentioned | TEXT | Comma-separated tickers |
| sentence_type | TEXT | Classified Day 20 |
| sentiment | TEXT | Classified Day 20 |

---

### persona_calls
Voting ledger for outcome calibration. One row per persona per ticker per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| run_id | TEXT NOT NULL | JOIN key |
| timestamp | TEXT NOT NULL | ISO datetime |
| persona | TEXT NOT NULL | bull / bear / black_swan / pragmatist / contrarian |
| ticker | TEXT NOT NULL | Ticker the call applies to |
| direction | TEXT | ACCUMULATE / HOLD / REDUCE / EXIT |
| confidence_score | INTEGER | 1–5 self-reported confidence |
| regime_tag | TEXT | low_vix / normal / high_vix / crisis |
| vix_level | REAL | VIX at time of call |
| rationale_summary | TEXT | First 200 chars of primary argument |
| price_at_signal | REAL | Immutable baseline price at call time |
| outcome_5d | TEXT | correct / incorrect / partial / void — scored at +5 trading days |
| outcome_20d | TEXT | correct / incorrect / partial / void — scored at +20 trading days |

---

### balance_ledger
Manual API credit tracking. One row per topup or reconciliation.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| timestamp | TEXT NOT NULL | ISO datetime |
| amount_usd | REAL NOT NULL | Amount topped up |
| notes | TEXT | e.g. "Opening balance Day 9" |

---

### thesis_drafts
AI-generated thesis drafts awaiting human review.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| timestamp | TEXT NOT NULL | ISO datetime |
| ticker | TEXT NOT NULL | Ticker the draft covers |
| section | TEXT NOT NULL | Section of thesis |
| draft_text | TEXT NOT NULL | AI-generated draft |
| trigger_source | TEXT | correlation_check / feed_match / human |
| rationale | TEXT | AI reasoning |
| status | TEXT DEFAULT pending | pending / approved / rejected / modified |

---

### thesis_reviews
Human decisions on thesis drafts.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| timestamp | TEXT NOT NULL | ISO datetime |
| draft_id | INTEGER NOT NULL | FK to thesis_drafts.id |
| ticker | TEXT NOT NULL | Ticker reviewed |
| section | TEXT NOT NULL | Section reviewed |
| action | TEXT NOT NULL | approved / rejected / modified |
| modified_text | TEXT | Human-edited version if action=modified |
| reason | TEXT | Why accepted / rejected / changed |
| reviewer | TEXT DEFAULT human | human (future: persona name) |
| source | TEXT DEFAULT ai_draft | ai_draft / human_initiated |

---

## 2. CONFIG.PY CONSTANTS

### Mode flags
| Constant | Type | Default | Description |
|---|---|---|---|
| USE_LIVE_DATA | bool | False | True=yfinance fetch, False=fixture prices |
| USE_LIVE_AGENTS | bool | False | True=Claude API, False=fixture agents |
| CAPTURE_LIVE_DATA_FOR_FIXTURES | bool | True | True=overwrite normal_day.json on live run |
| CAPTURE_LIVE_AGENTS_FOR_FIXTURES | bool | True | True=overwrite fixtures/agents/ on live run |
| DEV_MODE | bool | True | True=all Haiku (~$0.05), False=Haiku+Sonnet (~$0.50) |

### Model routing
| Constant | Value | Description |
|---|---|---|
| STAGE_1_MODEL | claude-haiku-4-5-20251001 | Always Haiku — Stage 1 agents |
| STAGE_2_MODEL | Haiku if DEV_MODE else Sonnet | Contrarian |
| STAGE_3_MODEL | Haiku if DEV_MODE else Sonnet | Meta-Agent |
| TRANSLATOR_MODEL | claude-haiku-4-5-20251001 | Always Haiku |
| FALLBACK_MODEL | claude-haiku-4-5-20251001 | Always Haiku |

### Token budgets
| Constant | Value | Description |
|---|---|---|
| STAGE_1_MAX_TOKENS | 1200 | Stage 1 agents |
| STAGE_2_MAX_TOKENS | 2000 | Contrarian reads four inputs |
| STAGE_3_MAX_TOKENS | 4000 | Meta-Agent covers 8 tickers |
| TRANSLATOR_MAX_TOKENS | 2500 | Plain English briefing |

### Temperature
| Constant | Value | Description |
|---|---|---|
| STAGE_1_TEMPERATURE | 0.6 | High — extreme committed positions |
| STAGE_2_TEMPERATURE | 0.7 | High — paradox hunting |
| STAGE_3_TEMPERATURE | 0.1 | Very low — deterministic, auditable |
| TRANSLATOR_TEMPERATURE | 0.5 | Mid — natural language variation |

### Tickers
| Ticker | Type | Role |
|---|---|---|
| NVDA | equity | Demand anchor |
| AVGO | equity | Network gatekeeper |
| LITE | equity | Photonics pure-play |
| TSM | equity | Production floor |
| QQQ | etf | Nasdaq-100 |
| SMH | etf | Semiconductor ETF |
| G3B.SI | etf | STI ETF — local anchor |
| ^VIX | index | Fear gauge — regime classifier |

### Other constants
| Constant | Type | Description |
|---|---|---|
| DB_PATH | str | prices.db |
| MODEL_PRICING | dict | Per-million-token USD pricing per model |
| TICKER_THESIS | dict | Per-ticker structural thesis — 8 entries |
| PORTFOLIO_RELATIONSHIPS | str | Causal chain, ETF layer, concentration risks |
| THESIS_LAST_REVIEWED | dict | Per-ticker last review date — staleness flag |
| PORTFOLIO_SECTIONS_LAST_REVIEWED | dict | Per-section last review date |
| CORRELATION_PAIRS | list of dicts | Ticker pairs for rolling 30-day Pearson checks |
| SCHEDULE_TIME | str | '12:00' — noon daily Task Scheduler trigger |
| MAX_RUN_MINUTES | int | 30 — timeout guard for unattended runs |
| STUCK_RUN_THRESHOLD_MINUTES | int | 60 — runs older than this marked failed at session start |
| FIXTURE_DIR | Path | stock-monitor/fixtures/agents/ — passed to sm_call_llm wrapper |
| PRICE_FIXTURE_PATH | Path | stock-monitor/fixtures/normal_day.json — passed to sm_save_price_fixtures |
| ENV_PATH | Path | stock-monitor/.env — passed to sm_send_email_alert |

---

## 3. KEY FUNCTIONS

### shared/utils.py

**ARCHITECTURAL RULE — NON-NEGOTIABLE:** This module must never import either project's config.py. Shared functions receive config-dependent values as parameters from the caller. Each project defines thin wrappers that inject its own config values once. Violating this poisons the importing project's config via sys.modules caching. Enforce at every code review. No exceptions.

| Function | Signature | Returns | Description |
|---|---|---|---|
| format_warning(severity, file, function, description, fix) | — | str | Pipe-delimited warning string. SEVERITY \| file \| function() \| description \| fix |
| call_llm(prompt, system, model, max_tokens, temperature, fallback_model, client, call_type, use_live_agents, capture_fixtures, fixture_dir) | — | (str, dict) | Universal Claude API wrapper. Handles fixtures, fallback, truncation retry, capture. Config-free — callers inject values via project wrappers |
| extract_json(raw) | — | (dict, None) or (None, str) | Extracts clean JSON from Claude response |
| update_market_history(tickers, use_live) | — | None | Delta pull from yfinance → market_history |
| save_price_fixtures(price_data, fixture_path, capture) | — | None | Updates fixture JSON prices block. fixture_path and capture passed by caller — no hardcoded paths |
| send_email_alert(subject, body, env_path, project_tag) | — | bool | SMTP alert. env_path and project_tag passed by caller — works for any project |

### stock_monitor.py — project wrappers (Day 15)
These wrappers are the only place Stock Monitor config values are injected into shared functions. Call sites use wrappers, never raw shared functions directly.

| Function | Returns | Description |
|---|---|---|
| sm_call_llm(**kwargs) | (str, dict) | Injects USE_LIVE_AGENTS, CAPTURE_LIVE_AGENTS_FOR_FIXTURES, FIXTURE_DIR into call_llm() |
| sm_save_price_fixtures(price_data) | None | Injects PRICE_FIXTURE_PATH, CAPTURE_LIVE_DATA_FOR_FIXTURES into save_price_fixtures() |
| sm_send_email_alert(subject, body) | bool | Injects ENV_PATH, project_tag='Stock Monitor' into send_email_alert() |

### shared/data_sources.py
| Function | Returns | Description |
|---|---|---|
| get_current_prices(tickers, use_live) | list of dicts | Live yfinance or fixture prices |
| get_intelligence_context(use_live) | dict | Manual stub or fixture intelligence block |

### database.py
| Function | Returns | Description |
|---|---|---|
| get_connection() | sqlite3.Connection | Row factory enabled. Use as context manager |
| initialise_db() | None | Creates all tables, seeds models |
| generate_run_id() | str | YYYY-MM-DD_HH:MM:SS timestamp string |
| compute_call_cost(model_used, input_tokens, output_tokens) | float | USD cost from MODEL_PRICING |
| get_estimated_balance() | dict or None | Estimated remaining API credit |
| start_run(run_id, data_mode) | None | Opens run_log entry |
| finish_run(run_id, status, stats) | None | Closes run_log entry |
| write_prices(run_id, price_data) | None | Writes price rows |
| write_analysis(run_id, output_text, analysis_type, ticker, source, truncated) | int | Returns row id |
| write_signal(run_id, ticker, signal_type, ...) | None | Writes signal row |
| write_persona_call(run_id, persona, ticker, ..., price_at_signal) | None | Writes persona_calls row |
| write_llm_call(run_id, call_type, ...) | None | Writes llm_calls audit row |
| log_balance_topup(amount_usd, notes) | None | Writes balance_ledger entry |
| read_recent_prices(ticker, limit) | list | Last N price rows |
| read_market_history(ticker, limit) | list | Last N market_history rows |
| read_recent_signals(triggered_only, limit) | list | Recent signal rows |
| read_run_history(limit) | list | Last N run_log rows |
| get_latest_market_history_date(ticker) | str or None | Last stored trade_date |
| write_market_history_rows(rows) | int | Batch insert to market_history |

### stock_monitor.py
| Function | Returns | Description |
|---|---|---|
| score_persona_call_outcomes() | None | Scores persona_calls at +5 and +20 trading-day horizons |
| check_stuck_runs() | int | Marks stale running rows failed, returns count cleared |
| check_kill_triggers() | dict | Active kill triggers per ticker |
| check_thesis_staleness() | list | Entries older than 30 days |
| check_portfolio_correlations(run_id) | list | Pearson correlation breach dicts |
| build_data_package(ticker, ...) | str | 6-layer prompt string for agents |
| build_chain_summary(all_price_data) | str | Python-assembled live chain snapshot |
| build_historical_context(ticker) | dict | Trajectory stats from market_history |
| determine_vix_regime(all_price_data) | (str, float) | Regime tag + VIX level |
| run_stage1_agent(agent_name, ...) | (dict, list) | Parsed output + warnings list |
| run_contrarian(stage1_outputs, ...) | (dict, list) | Parsed output + warnings list |
| run_meta_agent(all_ticker_outputs, ...) | (dict, list) | Portfolio decisions + warnings list |
| run_translator(meta_output, run_id) | (str, list) | Plain English briefing + warnings list |
| display_results(price_data, meta_output, briefing) | None | Prints run output to terminal |
| run_pipeline() | None | Crash recovery wrapper around main(). Entry point for Task Scheduler |

---

## 4. WARNING FORMAT

All warnings use the pipe-delimited format via format_warning() in shared/utils.py:

```
SEVERITY | file | function() | description with variable values | fix action
```

Severity values: `ERROR` or `WARN ` (padded to 5 chars for alignment)

Machine-readable — import directly into Excel or SQLite for trend analysis.

---

## 5. FIXTURE FILES

| File | Location | Description |
|---|---|---|
| normal_day.json | stock-monitor/fixtures/ | Price + intelligence fixture. Auto-updated when USE_LIVE_DATA=True and CAPTURE_LIVE_DATA_FOR_FIXTURES=True |
| stage1_bull_NVDA.json | stock-monitor/fixtures/agents/ | Captured Bull agent output for NVDA |
| stage1_bear_NVDA.json | stock-monitor/fixtures/agents/ | ...and so on for all 37 agent fixtures |
| stage3_meta_agent.json | stock-monitor/fixtures/agents/ | Meta-Agent portfolio output |
| translator.json | stock-monitor/fixtures/agents/ | Translator plain English output |

---

## 6. .ENV VARIABLES

| Variable | Description |
|---|---|
| ANTHROPIC_API_KEY | Claude API key — never commit |
| EMAIL_FROM | ex888machina@gmail.com |
| EMAIL_TO | ex888machina@gmail.com |
| EMAIL_PASSWORD | Gmail App Password (16 chars) |
| SMTP_SERVER | smtp.gmail.com |
| SMTP_PORT | 587 |

---

*Last updated: Day 15 — June 12, 2026*
