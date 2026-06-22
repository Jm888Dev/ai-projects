# SESSION_LEDGER.md
**Stock Monitor + HDB Analyser — Session History**
Updated end of every session. Three columns per day: **Built** (what the product can now do), **Learned** (concepts genuinely understood by building), **Lessons** (what changed how we work). Day numbers are retrospective labels — assigned after the session, never pre-committed.

---

## Days 1–12 — Seeded retroactively

| Day | Built | Learned | Lessons |
|---|---|---|---|
| 1 | Full Windows dev environment (Python, VS Code, Git, venv, .env). First Claude API call via hello_claude.py. | API key auth, messages endpoint, request/response anatomy. | Environment discipline first — venv, gitignore, .env — prevents every downstream "works on my machine" problem. |
| 2 | stock-monitor.py — yfinance ETL for ticker universe. | Separating data acquisition from reasoning — the pipeline shape everything later builds on. | Real market data is messy (missing fields, indices vs equities); handle it at the edge, not in the logic. |
| 3 | Structured JSON flowing between pipeline stages; Claude output parsed into Python objects. | LLM output is probabilistic text, not guaranteed JSON — the parsing problem Day 5 solves properly. | Never trust model output format; validate before use. |
| 4 | stock_monitor v3 — portfolio context in system= parameter; Translator chained after Analyst (JSON → plain English). HDB Analyser project scaffolded and pushed. | System prompt vs user message (standing brief vs live query); chained call pattern — one model's output as another's input, the seed of agentic pipelines. | Don't dilute a persona to fix its audience problem — add a second persona. |
| 5 | HDB pipeline end-to-end: data.gov.sg fetch, pandas filter/sample, section-by-section analyst (7 calls), extract_json() deterministic cleaner. | Anchoring failure mode in single large calls; per-section calls with own token budgets; buyer profile with None-flagging for missing fields. | Any cleaning done in code shouldn't be left to prompt instructions. Confident wrong numbers on a large-ticket purchase are worse than no numbers. |
| 6 | All constants moved to per-project config.py. ANALYST_SECTION_DEPENDENCIES — surgical context passing. Per-section translator token budgets. | Context economics — declaring exactly which prior sections each call needs controls tokens without losing quality. response.usage for cost accounting. | Magic numbers are silent bugs. Naming for debuggability, not brevity. |
| 7 | shared/utils.py created (first cross-project code). READMEs for both projects. HDB persona rewrite: tone, word limits, next_steps section. | Prompt as a contract — word limits force prioritisation; token budgets are the ceiling, word limits the design constraint. | DRY across projects; pay technical debt before adding complexity. Reading real output critically is how prompts improve. |
| 8 | call_llm() universal wrapper (primary → fallback → graceful degradation). SQLite prices.db — 6 tables, transaction safety, run_id linking key. TICKERS as dict with instrument_type. | Abstracting the model interface so model swaps are config changes, not refactors. Schema designed for where you're going, not where you are. | Partial writes must be impossible — context-manager commits with rollback. |
| 9 | 10-table schema with truncation columns; six-agent model routing in config; truncation guard in call_llm() (retry 1.5×, flag-and-pass-through); data_sources.py fixture/live abstraction; market_history 5-year backfill (10,034 rows); cost tracking; four tool scripts. | Adversarial multi-agent design — extreme biases prevent middle-of-the-road output; staged structured JSON beats a free-for-all. Kill triggers as thesis-aware pre-commitments, not stop-losses. | A 90% complete argument is still signal — flag truncation, never discard. Fixture infrastructure from day one; agents must never know which mode they're in. |
| 10 | Full three-stage pipeline live: Stage 1 (Bull/Bear/Black Swan/Pragmatist) → Contrarian → Meta-Agent (ACCUMULATE/HOLD/REDUCE/EXIT + 3 kill triggers per ticker). Six-layer data package builder. check_kill_triggers() at session start. persona_calls voting ledger. VIX regime classifier. Two-layer output prompt stubs created. | Portfolio-level synthesis vs per-ticker reasoning; confidence score semantics per persona; compress() for inter-stage context. | First live run flagged G3B.SI as a potential false diversifier — the system produced a genuine insight on day one. Wrong answers surface right questions. |
| 11 | thesis_drafts + thesis_reviews tables. thesis_overrides.json with _deep_update() section-level merge. check_thesis_staleness() non-blocking 30-day flag. USE_LIVE_AGENTS + capture flags — 37 agent fixtures captured; hard stop on missing fixtures. | Fixture infrastructure as the foundation of prompt tuning — frozen inputs isolate whether output changes come from prompts or data. Divergence as signal: directional (score 2–3) persisted, magnitude noted only. | Hard stop over silent fallback. Indentation errors are silent architecture bugs. Three-question warning standard locked. |
| 12 | Codebase map (15 files, 12-table reference, call chains, mode-flag matrix). check_portfolio_correlations() — extensible CORRELATION_PAIRS, SGX/NYSE holiday handling. Gmail SMTP alerts on REDUCE/EXIT confidence ≥ 4. score_persona_call_outcomes() stub — T-3 sessions, 35 calls scored. | Pure-Python health checks beside LLM reasoning — correlation math (0.831) confirmed quantitatively what Meta-Agent flagged qualitatively. Scoring horizon design. | Outlook.com blocks basic SMTP auth — check OAuth2 requirements before assuming password auth. A codebase map saved more time than it cost. |

---

## Days 13–19

### Day 13 — Hygiene + Scoring Upgrade
**Built:** Warning audit complete across shared/utils.py, database.py, stock_monitor.py. format_warning() single formatter added — pipe-delimited, machine-readable. Runner functions now return (output, warnings_list) tuples. main() collects via run_warnings.extend() and prints consolidated summary. score_persona_call_outcomes() upgraded from T-3 stub to +5/+20 trading-day horizons using market_history closes. price_at_signal logged at call time as immutable baseline. outcome_5d / outcome_20d columns added to persona_calls via safe ALTER TABLE. DATA_DICTIONARY.md and CODEBASE_MAP.md seeded from actual code — two discrepancies found during verification.

**Learned:** format_warning() pattern — one formatter, one place, pipe-delimited output is machine-readable and importable into Excel or SQLite. Returning warnings via tuples keeps state clean, avoids global mutation, scales to async later. Two scoring horizons because a call can be correct at +5 and wrong at +20. price_at_signal as immutable baseline: scoring against intraday prices is unreliable.

**Lessons:** Seed living documents from actual code, not memory — two discrepancies found immediately. VS Code workspace requires manual folder entry for new top-level directories. Build for the reader, not just the writer.

---

### Day 14 — Unattended Operation
**Built:** check_stuck_runs() — queries run_log for status='running' rows older than STUCK_RUN_THRESHOLD_MINUTES, marks them failed. run_pipeline() — crash-recovery wrapper around main(); catches unhandled exceptions, emails on live runs; entry point for Task Scheduler. Windows Task Scheduler configured — daily 12:00pm, venv Python path, Start in set to project folder. Three new config constants: SCHEDULE_TIME, MAX_RUN_MINUTES, STUCK_RUN_THRESHOLD_MINUTES. OPEN_QUESTIONS.md seeded with OQ-001–004.

**Learned:** Two-layer scheduling — OS owns the clock (Task Scheduler), Python owns the resilience (run_pipeline() + stuck-run detection). schedule library requires a permanently running process — wrong tool for a laptop; Task Scheduler is the Windows equivalent of cron. Every failure path must log to run_log, alert if live, exit cleanly — a silent crash is more dangerous than a noisy one.

**Lessons:** Start in field is mandatory in Task Scheduler — missing it causes 0x2 file not found error. Bare variable names need config. prefix. Imports always at the top of file, never inside function bodies.

---

### Day 15 — Shared Module Architecture Fix
**Built:** shared/utils.py made fully config-free — import config, sys.path.insert, and _STOCK_MONITOR_DIR removed from module level. call_llm() extended with use_live_agents, capture_fixtures, fixture_dir parameters. save_price_fixtures() and send_email_alert() parameterised to be project-agnostic. Three project wrappers added to stock_monitor.py: sm_call_llm(), sm_save_price_fixtures(), sm_send_email_alert() — each injects Stock Monitor config once. Three new path constants in config.py: FIXTURE_DIR, PRICE_FIXTURE_PATH, ENV_PATH. HDB .env corrected. HDB pipeline end-to-end clean.

**Learned:** sys.modules caching is the silent killer of shared module imports — the first import config wins and subsequent imports return the cached version regardless of sys.path order. **kwargs as a pass-through clause. Project wrappers as the correct pattern for config injection — one declaration, zero repetition at call sites.

**Lessons:** When a module imports correctly in isolation but fails inside a script, always check sys.modules caching from prior imports. Shared modules must never import project config — enforce at every code review, no exceptions. Session close rule institutionalised — cut scope, never cut the close.

---

### Day 16 — Sovereign SLM Tier
**Built:** Ollama 0.30.8 installed. _call_ollama() added to shared/utils.py — raw requests.post() to localhost, sovereignty guard raises ValueError if base_url is not localhost. call_llm() extended with SLM parameters. sm_call_llm() extended with SLM model resolution + shadow cost computation. Full SLM config block added to config.py. MODEL_PRICING extended with zero-cost SLM entries. Three new llm_calls columns: thinking_tokens, shadow_cost_haiku_usd, shadow_cost_sonnet_usd. One new run_log column: slm_model. slm_benchmarks table created. tools/slm_benchmark.py built. Database reset and 5-year backfill re-run (8,787 rows). Feed Relevance Engine three-layer architecture designed (OQ-006). Full live run token baseline: Stage 1 ~2,310 tokens, Stage 2 ~5,278, Stage 3 ~23,914.

**Learned:** Model size does not predict output quality. CPU inference dominated by output token generation (sequential), not input processing (parallel). Gemma4 E4B thinking mode competes with response tokens — minimum viable budget 1200 tokens. MoE architecture activates subset of parameters per token. Benchmark design is itself an engineering discipline — must measure at actual operating token count. Shadow costs preserve prompt discipline when SLM inference is free.

**Lessons:** Cannot benchmark at proxy sizes. All 22 feed sources active from Day 1 — artificial restriction produces unrepresentative token sizing.

---

### Day 17 — Feed Stage 1
**Built:** feedparser installed (v6.0.12). feeds table added to database.py — UNIQUE constraint on URL for deduplication, relevance_score, tickers_matched, injected columns. feeds.py created — fetch_and_store_feeds(), get_relevant_headlines(), build_feed_injection(). Feed config block in config.py: FEED_SOURCES (22 entries, 6 domains), FEED_KEYWORDS, FEED_MAX_HEADLINES_PER_DOMAIN=5, FEED_RELEVANCE_THRESHOLD=1, FEED_MAX_TOTAL_HEADLINES=30. stock_monitor.py wired — fetch on live runs, injection per ticker in build_data_package(). Run summary extended with feed status and truncation detail. tools/feeds_audit.py created. Full live run with feeds: 820 headlines first fetch, 20 OK / 2 WARN / 0 FAILED after URL triage. Token baseline updated: Stage 1 ~3,646, Stage 2 ~6,469, Stage 3 ~23,709. Total run cost $0.3584. pull_models.ps1 created for unattended overnight model pull.

**Learned:** RSS is a standardised XML file — no subscription mechanism, just GET it periodically. feedparser bozo flag means XML spec violation, not necessarily unusable — check bozo=True AND entries=0 to declare failure. Three failure categories: HTML returned instead of RSS (wrong URL), malformed XML, DNS failure (network block). Stage 3 token count barely moved with feeds active because injection is per-ticker in the data package, not in the compressed Meta-Agent input — architecture already isolates token cost at Stage 1/2 where it belongs.

**Lessons:** Bozo is not binary failure — always check entry count. DNS failure is a network block, not a URL problem. Feed URL rot is real — feeds_audit.py should run monthly.

---

### Day 18 — HDB Buyer Type, Dual Mandate, Translator Rewrite
**Built:** buyer_type promoted to first-class profile field in hdb_analyser.py — replaces boolean first_time_buyer as the routing key. Five buyer types defined: first_timer, second_timer, upgrader, downgrader, private_downgrader. BUYER_TYPES registry added to hdb-analyser/config.py — each type carries: description, ehg_eligible, resale_levy, wait_period_months, ltv_standard, notes. format_for_claude() extended to inject applicable rules block as third layer (transaction data + buyer profile + rules). HDB_ANALYST_SYSTEM_PROMPT updated — BUYER PROFILE RULES section routes by buyer_type, never assumes first-timer. Dual mandate output schema: top_picks gains purchase_rationale (max 50 words) and opportunity_flag (relative value vs. comparables, or "No material opportunity identified", max 40 words), replacing single reason field. HDB_TRANSLATOR_SYSTEM_PROMPT fully rewritten — plain text only, term definition format prescribed, beginner concepts layer, length caps. reset_db.py auto-backup added.

**Learned:** buyer_type as a routing key vs. a boolean — same pattern as instrument_type in TICKERS dict. A boolean answers one question; a typed field routes to an entire rule set. BUYER_TYPES is Layer 1 scaffolding — the routing key is permanent, the hardcoded values are temporary until RAG (Day 20 scope). Prompt precision controls output determinism — "plain English" is not specific enough; "plain text only, no asterisks, no bold, no markdown of any kind" is. The dual mandate separates two analytical lenses: purchase rationale (is this a sound purchase?) vs. opportunity flag (is this underpriced?). A field that returns "No material opportunity identified" when none exists is more trustworthy than one that manufactures value.

**Lessons:** Prompt vagueness is the root cause of output drift. "Smart" in a prompt instruction is vague and patronising — "write conversationally, do not talk down to the reader" is specific and respectful. Hardcoded rule registries are honest scaffolding, not technical debt, when the migration path is explicit and scheduled.

---

### Day 19 — SLM Honest Benchmarking, num_ctx Truncation Discovery
**Built:** prompt_text TEXT column added to llm_calls — OQ-004 Gap 1 closed properly (not the print()-capture shortcut). write_llm_call() extended with prompt_text parameter. All four pipeline call sites (run_stage1_agent, run_contrarian, run_meta_agent, run_translator) pass it through. call_llm() returns prompt_text in all five return paths (fixture, SLM success, SLM error, Anthropic success, Anthropic error) — config-free. Database reset and 5-year backfill re-run (10,031 rows). Live capture run (Haiku, $0.3717, zero errors) — Stage 3 Meta-Agent prompt captured at 24,740 input tokens / 93,143 characters. tools/slm_benchmark.py rewired — load_captured_prompt() reads real prompts from llm_calls.prompt_text; xl loads largest stage1_pragmatist, xxl loads stage3_meta_agent; prompt_mode logged as realistic. Two pre-existing bugs fixed: PROMPT_SIZES NameError, size_priority recommendation logic excluding xl/xxl. num_ctx silent-truncation bug discovered and fixed — Ollama's default ~2048-token context was truncating large prompts with zero warning, producing confident wrong output (JSON=NO, Dir=NO, Halluc=YES). Fix: three-way cap formula — min(estimated_input + max_tokens + safety_margin, model_real_ceiling, hardware_cap). Five new config constants. phi4-mini confirmed non-viable for Stage 3 xxl — three consistent 602s timeouts post-fix. Heavy tier benchmark (qwen3.6:35b-a3b, gemma4:26b at xl/xxl) deferred — commands ready.

**Learned:** A model returning fast valid-looking JSON is not evidence of correctness — speed and confidence are not quality signals. num_ctx is total budget (input + output combined), never output-only headroom. A model's documented context length is necessary but not sufficient — RAM capacity is an independent constraint. When propagating a parameter rename across a function chain, verify every file in the chain individually — three separate drift bugs were caught only this way.

**Lessons:** Honest benchmark failure (timeout) is strictly more valuable than dishonest benchmark success (fast, wrong output). PowerShell multi-line scripts must be authored in VS Code, never built line-by-line via redirection. Session context rot is real — clean stop strictly better than pushing through fatigued context.

---

### Day 20 — Re-baseline
**Built:** No code changed. Session deliverable was alignment and planning: AI concept ranking, goal-state criteria (replacing Day 30 hard milestone), confirmed agent design decisions (Arbitrator/Stage 2.5, Contrarian epistemic audit expansion, Stage 1 multi-model diversity, HDB Devil's Advocate on local SLM), document consolidation plan (5 PK documents, all markdown), and Master Plan v1.2. OPEN_QUESTIONS.md, Intelligence_Feed_Architecture.docx, and Mack_Stock_Monitor_Universe.docx retired into Master Plan. READMEs relocated out of PK. Forward queue established — no day number pre-assigned to any future deliverable.

**Learned:** Drift traced to a specific, repeatable cause: binding specific content to a specific future day number in advance, then using the static plan rather than the most recent Day Summary to orient at session start. The fix is structural — the forward queue holds no day numbers, and the most recent Day Summary is the first thing checked at session open, before any document or plan.

**Lessons:** The precedence rule (most recent Day Summary wins on conflict with the Master Plan) must be applied at the first message of every session, not just when a conflict is noticed mid-session. A polished artifact carries its own credibility risk — a wrong state presented beautifully is harder to catch than a wrong state in plain text.

---

*Policy: only the most recent Day Summary lives in Project Knowledge — older ones in Git. This file is updated at session close alongside the Day N Summary and the four other living documents.*
