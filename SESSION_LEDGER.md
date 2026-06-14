# SESSION_LEDGER.md — One Row Per Day

Living document. Updated at the end of every session alongside the Day N summary docx.
Columns: **Features introduced** (what the product can now do) · **AI learning accomplished** (concepts genuinely understood by building) · **Lessons learnt** (what changed how we work).

---

## Days 1–12 (seeded retroactively from Day summaries, 12 Jun 2026)

### Day 1 — Environment & First Contact
- **Features:** Full Windows dev environment — Python, VS Code, Git/GitHub, venv (`myenv`), `.env` secrets handling. `hello_claude.py` — first successful Claude API call.
- **AI learning:** API key auth, the messages endpoint, request/response anatomy.
- **Lessons:** Environment discipline first (venv, gitignore, .env) prevents every downstream "works on my machine" problem.

### Day 2 — Stock Monitor ETL
- **Features:** `stock-monitor.py` — yfinance extract-transform-load working for the ticker universe.
- **AI learning:** Separating data acquisition from reasoning — the pipeline shape that everything later builds on.
- **Lessons:** Real market data is messy (missing fields, indices vs equities); handle it at the edge, not in the logic.

### Day 3 — Working with JSON
- **Features:** Structured JSON flowing between pipeline stages; Claude output parsed into Python objects.
- **AI learning:** LLM output is probabilistic text, not guaranteed JSON — the parsing problem that Day 5 solves properly.
- **Lessons:** Never trust model output format; validate before use.

### Day 4 — System Prompts & Chained Calls
- **Features:** stock_monitor v3 — portfolio context moved to `system=` parameter; Translator persona chained after Analyst (JSON → plain English). HDB Analyser project scaffolded and pushed.
- **AI learning:** System prompt vs user message split (standing brief vs live query); chained call pattern — one model's output as another's input, the seed of agentic pipelines.
- **Lessons:** Don't dilute a persona to fix its audience problem — add a second persona. Like a bank analyst briefing: onboard once, then send only the day's data.

### Day 5 — HDB Analyser v1 & Deterministic Parsing
- **Features:** HDB pipeline end-to-end: data.gov.sg fetch, pandas filter/sample, section-by-section analyst briefing (7 focused calls), structured dict + plain-English output. `extract_json()` deterministic cleaner.
- **AI learning:** Anchoring failure mode in single large calls; per-section calls with own token budgets; buyer profile as a dict with None-flagging for missing fields.
- **Lessons:** Any cleaning that can be done in code should be done in code — prompt formatting instructions are not load-bearing. Confident wrong numbers on a large-ticket purchase are worse than no numbers (verification discipline locked).

### Day 6 — Config as Single Source of Truth
- **Features:** All constants (models, budgets, temperatures, endpoints, section lists) moved to per-project `config.py`. `ANALYST_SECTION_DEPENDENCIES` — surgical context passing. Per-section translator token budgets.
- **AI learning:** Context economics — declaring exactly which prior sections each call needs controls tokens without losing quality. `response.usage` for cost accounting.
- **Lessons:** Magic numbers are silent bugs. Function names that differ by one character are maintenance nightmares — naming for debuggability.

### Day 7 — Clean Code & Consolidation
- **Features:** `shared/utils.py` created (first cross-project code). READMEs for both projects. HDB persona rewrite: tone rebalanced, word limits, point form, `next_steps` section. Config audits passed on both projects.
- **AI learning:** Prompt as a contract — word limits force prioritisation; token budgets are the ceiling, word limits the design constraint. 33% token / 49% duration reduction from prompt discipline alone.
- **Lessons:** DRY across projects; pay technical debt before adding complexity. Reading real output critically is how prompts actually improve.

### Day 8 — call_llm() & The Database
- **Features:** `call_llm()` universal wrapper (primary → fallback → graceful degradation, usage dict returned). SQLite `prices.db` with six tables (prices, analysis, signals, run_log, llm_calls, sentences). Transaction safety with rollback. `run_id` as the linking key. TICKERS as dict with instrument_type.
- **AI learning:** Abstracting the model interface so model swaps are config changes, not refactors. Schema designed for future days (persona columns, graph-edge columns reserved).
- **Lessons:** Partial writes must be impossible — context-manager commits with rollback. Design the schema for where you're going, not where you are.

### Day 9 — Six-Agent Architecture Locked & Data Foundation
- **Features:** 10-table schema with truncation columns; six-agent model routing in config; truncation guard in call_llm() (retry 1.5×, flag-and-pass-through); `data_sources.py` fixture/live abstraction; `market_history` 5-year backfill (10,034 rows) with idempotent delta-pull; cost tracking (MODEL_PRICING, cost_usd at insert, balance_ledger); four tools scripts.
- **AI learning:** Adversarial multi-agent design — extreme biases prevent middle-of-the-road output; separation of argument generation from judgment; agent fatigue and why staged structured JSON beats a free-for-all. Kill triggers as thesis-aware pre-commitments, not stop-losses.
- **Lessons:** A 90% complete argument is still signal — flag truncation, never discard. Fixture infrastructure from day one; agents must never know which mode they're in.

### Day 10 — First Live Run
- **Features:** Full three-stage pipeline working: Stage 1 (Bull/Bear/Black Swan/Pragmatist, parallel isolation per ticker) → Contrarian → Meta-Agent (ACCUMULATE/HOLD/REDUCE/EXIT + 3 kill triggers per ticker). Six-layer data package builder. `check_kill_triggers()` at session start. `persona_calls` voting ledger with regime tags. VIX regime classifier. Volume signals. DEV_MODE flag. Premortem redesigned as stress-test trigger. Two-layer output prompt stubs created.
- **AI learning:** Portfolio-level synthesis vs per-ticker reasoning; confidence score semantics per persona; compress() pattern for inter-stage context.
- **Lessons:** First live run flagged G3B.SI as a potential false diversifier — the system produced a genuine insight on day one of operation. Wrong answers surface right questions.

### Day 11 — Thesis Maintenance & Agent Fixtures
- **Features:** `thesis_drafts` + `thesis_reviews` tables (human-in-the-loop review workflow). `thesis_overrides.json` with `_deep_update()` section-level merge and UTF-8-sig BOM handling. `check_thesis_staleness()` non-blocking 30-day flag. `USE_LIVE_AGENTS` + capture flags — 37 agent fixtures captured; hard stop on missing fixtures.
- **AI learning:** Fixture infrastructure as the foundation of prompt tuning — frozen inputs isolate whether output changes come from prompts or data. Divergence as signal: directional (score 2–3) persisted, magnitude noted only.
- **Lessons:** Hard stop over silent fallback. Indentation errors are silent architecture bugs. Three-question warning standard locked (what/where/fix).

### Day 12 — Map, Measure, Alert
- **Features:** Codebase map (15 files, 12-table reference, call chains, mode-flag matrix). `check_portfolio_correlations()` — extensible CORRELATION_PAIRS, SGX/NYSE holiday intersection handling. Gmail SMTP alerts on REDUCE/EXIT confidence ≥ 4. `score_persona_call_outcomes()` stub — T-3 sessions, 1% void threshold, 35 calls scored.
- **AI learning:** Pure-Python health checks beside LLM reasoning — correlation math confirmed quantitatively (0.831) what the Meta-Agent flagged qualitatively. Scoring horizon design (session count vs calendar days; void as honest ambiguity).
- **Lessons:** Outlook.com blocks basic SMTP auth — check OAuth2 requirements before assuming password auth. A codebase map saved more time than it cost. Bearish consensus was wrong on AVGO/LITE, right on G3B.SI — the calibration data has begun.

---

## Days 13+ (updated per session)

### Day 13 — Hygiene + Scoring Upgrade
- **Features:** Warning message audit complete across all three files (`shared/utils.py`, `database.py`, `stock_monitor.py`). `format_warning()` single formatter added to `shared/utils.py` — pipe-delimited, machine-readable. Runner functions (`run_stage1_agent`, `run_contrarian`, `run_meta_agent`, `run_translator`) now return `(output, warnings_list)` tuples. `main()` collects via `run_warnings.extend()` and prints consolidated summary at end of run. `score_persona_call_outcomes()` upgraded from T-3 session stub to +5/+20 trading-day horizons using `market_history` closes. `price_at_signal` logged at call time as immutable baseline. `outcome_5d` and `outcome_20d` columns added to `persona_calls` via safe `ALTER TABLE`. Living documents seeded — `DATA_DICTIONARY.md` and `CODEBASE_MAP.md` verified line-by-line against actual code and placed in `docs/` folder. VS Code workspace updated to include `docs/`.
- **AI learning:** `format_warning()` pattern — one formatter, one place, pipe-delimited output is machine-readable and importable into Excel or SQLite for trend analysis. Returning warnings via tuples keeps state clean, avoids global mutation, and scales to async on Day 17 without modification. Two scoring horizons because a call can be correct at +5 and wrong at +20 — both data points matter for Day 15 calibration. `price_at_signal` as immutable baseline: scoring against intraday prices at run time is unreliable; the price at the exact moment of the call is the only honest reference point.
- **Lessons:** Seed living documents from actual code, not memory or summaries — two discrepancies found during verification. VS Code workspace requires manual folder entry for new top-level directories. The pipe-delimiter decision costs nothing at write time and unlocks analysis later — always build for the reader, not just the writer.

### Day 14 — Unattended Operation
- **Features:** `check_stuck_runs()` — queries `run_log` for rows with `status='running'` older than `STUCK_RUN_THRESHOLD_MINUTES`, marks them `failed`, logs a `format_warning()`. Runs at session start before kill triggers so stale locks never block a new run. `run_pipeline()` — top-level crash recovery wrapper around `main()`. Catches any unhandled exception, prints to log, sends email alert on live runs. Entry point for Task Scheduler. Windows Task Scheduler task configured — daily trigger at 12:00pm, venv Python path, `Start in` set to project folder, runs only when user is logged on. Three new constants in `config.py`: `SCHEDULE_TIME = '12:00'`, `MAX_RUN_MINUTES = 30`, `STUCK_RUN_THRESHOLD_MINUTES = 60`. `schedule` library installed (1.2.2) for future in-process timeout guard work. OPEN_QUESTIONS.md seeded with four backlog entries: OQ-001 Arbitration Stage, OQ-002 Reflection at Stage 1, OQ-003 Iterative Debate Loop, OQ-004 Audit Lineage.
- **AI learning:** Two-layer scheduling — OS owns the clock (Task Scheduler), Python owns the resilience (`run_pipeline()` wrapper and stuck-run detection). The `schedule` library requires a permanently running process — wrong tool for a laptop that closes; Task Scheduler is the Windows equivalent of cron. Graceful degradation design: every failure path must log to `run_log`, alert if live, and exit cleanly — a silent crash is more dangerous than a noisy one. Maker-checker principle applied to backlog design: the arbitration stage discussion surfaced that Meta-Agent self-arbitrating is a control failure equivalent to a credit committee reviewing its own memo.
- **Lessons:** `Start in` field is mandatory in Task Scheduler — missing it causes `0x2` file not found error; the script launches but cannot find `prices.db`, `config.py`, or fixtures. Bare variable names need `config.` prefix — Python only searches local and module scope, never imported modules. Imports always belong at the top of the file, never inside function bodies. The DB was updating correctly all along — the apparent issue was querying from the wrong directory. Rollover discipline: SESSION_LEDGER.md takes five minutes and should never carry forward.

### Day 15 — Shared Module Architecture Fix
- **Features:** `shared/utils.py` made fully config-free — `import config`, `sys.path.insert`, and `_STOCK_MONITOR_DIR` removed from module level. `call_llm()` signature extended with `use_live_agents`, `capture_fixtures`, `fixture_dir` parameters (safe defaults: `use_live_agents=True`, `capture_fixtures=False`, `fixture_dir=None`). `save_price_fixtures()` parameterised with `fixture_path` and `capture` — no hardcoded paths. `send_email_alert()` parameterised with `env_path` and `project_tag` — works for any project. Three project wrappers added to `stock_monitor.py`: `sm_call_llm()`, `sm_save_price_fixtures()`, `sm_send_email_alert()` — each injects Stock Monitor config values once. Three new path constants added to `stock-monitor/config.py`: `FIXTURE_DIR`, `PRICE_FIXTURE_PATH`, `ENV_PATH`. `from pathlib import Path` added to `stock-monitor/config.py`. Both pipelines confirmed clean after refactor. Architectural rule documented in code header and Claude memory. HDB `.env` API key corrected (stale key). `hdb_analyser.py` bug fixed: `run_translator_section()` except block now returns `(error_string, {"input": 0, "output": 0})` tuple — was returning single value causing unpack error. HDB pipeline confirmed end-to-end clean. HDB granularity upgrade deferred to Day 16.
- **AI learning:** `sys.modules` caching is the silent killer of shared module imports — the first `import config` wins and subsequent imports return the cached version regardless of `sys.path` order. This is why `shared/utils.py` importing `stock-monitor/config.py` poisoned HDB's config lookup even though `hdb-analyser/config.py` was correctly on the path. `**kwargs` as a pass-through clause — collects all caller arguments and forwards them untouched, like a SWIFT intermediary that adds routing data without inspecting the payment. Project wrappers as the correct pattern for config injection into shared functions: one declaration, zero repetition at call sites, loud failure if misconfigured. The devil's advocate exercise surfaced three genuine challenges (YAGNI, parameter creep, wrong day) and was resolved by correctly identifying that `send_email_alert` and `save_price_fixtures` are genuinely shared — HDB will use both. Parameterization is not YAGNI when the callers already exist.
- **Lessons:** When a module imports correctly in isolation but fails inside a script, always check `sys.modules` caching from prior imports — the path search is bypassed if the module name is already registered. Shared modules must never import project config — enforce at every code review, no exceptions. The session close rule was violated at Day 14 (ledger deferred); institutionalised as non-negotiable from Day 15 forward — cut scope, never cut the close. Always read existing living documents and produce the complete file, not a partial entry to manually insert.
