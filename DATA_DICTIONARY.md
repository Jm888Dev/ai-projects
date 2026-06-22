# DATA_DICTIONARY.md
**Stock Monitor + HDB Analyser — Cumulative Data Dictionary**
Verified against actual database.py, config.py, hdb-analyser/config.py as of Day 20. This file describes current reality — never history. When this conflicts with a Day Summary, this document wins on schema/constant facts; the Day Summary wins on decisions and sequencing.

---

## 1. Stock Monitor — prices.db Tables

### models
Reference table. Seeded at initialise_db(). Never updated mid-run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Autoincrement |
| model_id | TEXT UNIQUE | e.g. claude-haiku-4-5-20251001 |
| alias | TEXT | e.g. haiku-4-5 |
| provider | TEXT DEFAULT anthropic | anthropic / ollama |
| tier | TEXT | haiku / sonnet / opus / slm |

Seeded: claude-haiku-4-5-20251001, claude-sonnet-4-6, claude-opus-4-8, phi4-mini, gemma4:e4b, qwen3.6:35b-a3b, gemma4:26b

---

### prices
One row per ticker per run. What each agent saw at moment of reasoning. Separate from market_history (canonical daily close record).

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT NOT NULL | JOIN key |
| timestamp | TEXT NOT NULL | ISO datetime |
| ticker | TEXT NOT NULL | |
| instrument_type | TEXT | equity / etf / index |
| price | REAL | Price at capture |
| prev_close | REAL | Previous session close |
| pct_change | REAL | (price - prev_close) / prev_close * 100 |
| capture_context | TEXT DEFAULT unclassified | market_open_normal / market_closed_after_hours / etc |
| intraday_position | REAL | 0.0=day low, 1.0=day high, NULL if closed |
| reconciliation | TEXT DEFAULT unresolved | close_matched / intraday_capture / unresolved |

---

### market_history
Canonical OHLCV per ticker per trading day. 5-year backfill on first run, delta pull each session. This is market truth — prices table is agent context.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| ticker | TEXT NOT NULL | |
| trade_date | TEXT NOT NULL | YYYY-MM-DD |
| open / high / low / close | REAL | OHLC — close is canonical |
| volume | INTEGER | |
| pct_change | REAL | Daily % change |
| source | TEXT DEFAULT yfinance | yfinance / fixture |
| inserted_at | TEXT NOT NULL | ISO datetime |

UNIQUE on (ticker, trade_date) — INSERT OR IGNORE prevents duplicates.

---

### analysis
Raw Claude outputs. One row per agent call per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT NOT NULL | |
| timestamp | TEXT NOT NULL | |
| analysis_type | TEXT NOT NULL | bull / bear / black_swan / pragmatist / contrarian / meta_agent / translator |
| ticker | TEXT | NULL for portfolio-level calls |
| source | TEXT NOT NULL | stock_monitor |
| output | TEXT NOT NULL | Raw Claude response |
| truncated | INTEGER DEFAULT 0 | 1 if hit token limit |

---

### signals
Derived signals. One row per flagged condition per run. Decision history of the pipeline.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT NOT NULL | |
| timestamp | TEXT NOT NULL | |
| ticker | TEXT NOT NULL | |
| signal_type | TEXT NOT NULL | kill_trigger / meta_decision / portfolio_relationship_alert / divergence / premortem / persistent_divergence |
| value | REAL | Measured value (e.g. correlation coefficient) |
| threshold | REAL | Comparison threshold |
| triggered | INTEGER DEFAULT 0 | 1=fired, 0=evaluated but not triggered |
| direction | TEXT | ACCUMULATE / HOLD / REDUCE / EXIT |
| persona | TEXT | Which agent raised the signal |
| entity_a / relationship / entity_b | TEXT | Reserved for knowledge graph (Day 38+) |
| notes | TEXT | Human-readable explanation |
| outcome | TEXT | correct / incorrect / partial / void |
| resolved_by_run_id | TEXT | Run that scored the outcome |
| human_override | INTEGER DEFAULT 0 | 1 if manually overridden |
| divergence_score | INTEGER | 1=magnitude only, 2–3=directional disagreement |

---

### run_log
Pipeline health. One row per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT UNIQUE | YYYY-MM-DD_HH:MM:SS — primary JOIN key |
| started_at | TEXT NOT NULL | |
| completed_at | TEXT | NULL if crashed |
| status | TEXT DEFAULT running | running / complete / failed |
| data_mode | TEXT DEFAULT fixture | live / fixture |
| tickers_attempted / succeeded / failed | INTEGER | |
| analyst_input_tokens / output_tokens | INTEGER | Stage 1–3 totals |
| translator_input_tokens / output_tokens | INTEGER | |
| analyst_duration_secs / translator_duration_secs | REAL | Wall clock |
| fallback_used | INTEGER | 1 if fallback model used |
| error_count | INTEGER | |
| total_cost_usd | REAL | Sum of llm_calls.cost_usd |
| notes | TEXT | |
| slm_model | TEXT | Active SLM model for this run. NULL when USE_SLM=False. |

---

### llm_calls
Full LLM audit trail. One row per call_llm() invocation.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT NOT NULL | |
| timestamp | TEXT NOT NULL | |
| call_type | TEXT NOT NULL | stage1_bull / stage1_bear / stage1_black_swan / stage1_pragmatist / stage2_contrarian / stage3_meta_agent / translator |
| model_requested | TEXT NOT NULL | From config |
| model_used | TEXT | Actual model (may be fallback or fixture:call_type) |
| fallback_used | INTEGER DEFAULT 0 | |
| input_tokens / output_tokens | INTEGER | |
| duration_secs | REAL | |
| cost_usd | REAL | Computed from MODEL_PRICING at insert time |
| status | TEXT DEFAULT success | success / fallback / error |
| error_message | TEXT | |
| retried | INTEGER DEFAULT 0 | 1 if truncation retry triggered |
| truncated | INTEGER DEFAULT 0 | 1 if still truncated after retry |
| retry_budget | INTEGER | Token budget used on retry |
| thinking_tokens | INTEGER DEFAULT 0 | CoT tokens from Gemma4 thinking mode |
| shadow_cost_haiku_usd | REAL | Hypothetical Haiku cost on SLM token counts. NULL for non-SLM calls. |
| shadow_cost_sonnet_usd | REAL | Hypothetical Sonnet cost on SLM token counts. NULL for non-SLM calls. |
| prompt_text | TEXT | Full prompt sent to model. Added Day 19 (OQ-004 Gap 1). NULL for pre-Day-19 rows. |

---

### persona_calls
Voting ledger for outcome calibration. One row per persona per ticker per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id / timestamp | TEXT NOT NULL | |
| persona | TEXT NOT NULL | bull / bear / black_swan / pragmatist / contrarian |
| ticker | TEXT NOT NULL | |
| direction | TEXT | ACCUMULATE / HOLD / REDUCE / EXIT |
| confidence_score | INTEGER | 1–5 self-reported |
| regime_tag | TEXT | low_vix / normal / high_vix / crisis |
| vix_level | REAL | VIX at call time |
| rationale_summary | TEXT | First 200 chars of primary argument |
| price_at_signal | REAL | Immutable baseline price at call time |
| outcome_5d | TEXT | correct / incorrect / partial / void — scored at +5 trading days |
| outcome_20d | TEXT | correct / incorrect / partial / void — scored at +20 trading days |

---

### feeds
Intelligence feed headlines. Stage 1 storage — no model reads this content in Stage 1.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| fetched_at | TEXT NOT NULL | |
| source | TEXT NOT NULL | e.g. "arXiv cs.AI" |
| domain | TEXT NOT NULL | ai / quantum / geopolitics / current_affairs / social / tech |
| title | TEXT NOT NULL | |
| url | TEXT NOT NULL UNIQUE | UNIQUE drives deduplication |
| published | TEXT | From feed (may be None) |
| summary | TEXT | First 500 chars |
| relevance_score | INTEGER DEFAULT 0 | Max keyword match count across all tickers |
| tickers_matched | TEXT | Comma-separated tickers matched |
| injected | INTEGER DEFAULT 0 | 1 if included in a data package this run |

---

### Other tables

| Table | Rows/Run | Purpose |
|---|---|---|
| balance_ledger | Manual only | API credit topup tracking — amount_usd, notes |
| thesis_drafts | 0 (populated Day 27+) | AI-generated thesis drafts: ticker, section, draft_text, trigger_source, status |
| thesis_reviews | 0 (populated Day 27+) | Human decisions on drafts: action (approved/rejected/modified), modified_text, reason |
| sentences | 0 (future) | Per-sentence RAG source from analysis output |
| slm_benchmarks | Test runs only | SLM benchmark results — see §8 |

---

## 2. Stock Monitor — config.py Constants

### Mode flags
| Constant | Default | Description |
|---|---|---|
| USE_LIVE_DATA | False | True=yfinance fetch |
| USE_LIVE_AGENTS | False | True=Claude API |
| CAPTURE_LIVE_DATA_FOR_FIXTURES | True | Overwrites normal_day.json when USE_LIVE_DATA=True |
| CAPTURE_LIVE_AGENTS_FOR_FIXTURES | True | Overwrites fixtures/agents/ when USE_LIVE_AGENTS=True |
| DEV_MODE | True | True=all Haiku (~$0.05/run), False=Haiku+Sonnet (~$0.50) |
| USE_SLM | False | Routes all agent calls to local Ollama when True |

### Model routing
| Constant | Value | Description |
|---|---|---|
| STAGE_1_MODEL | claude-haiku-4-5-20251001 | Always Haiku |
| STAGE_2_MODEL | Haiku if DEV_MODE else Sonnet | |
| STAGE_3_MODEL | Haiku if DEV_MODE else Sonnet | |
| TRANSLATOR_MODEL | claude-haiku-4-5-20251001 | Always Haiku |
| FALLBACK_MODEL | claude-haiku-4-5-20251001 | Always Haiku |

### SLM config
| Constant | Value | Description |
|---|---|---|
| SLM_FAST_MODEL | phi4-mini | Fast tier |
| SLM_HEAVY_MODEL | qwen3.6:35b-a3b | Heavy tier Stage 2 |
| SLM_HEAVY_MODEL_STAGE3 | gemma4:26b | Heavy tier Stage 3 |
| SLM_STAGE_MODELS | dict | Per-stage tier assignment — pending heavy-tier benchmark results |
| OLLAMA_BASE_URL | http://localhost:11434/api/chat | Sovereignty rule: always localhost |
| OLLAMA_TIMEOUT | 600 | Seconds |
| OLLAMA_MODEL_MAX_CTX | dict | Real ceilings per model (verified via ollama show): phi4-mini/gemma4:e4b=131072, qwen3.6:35b-a3b/gemma4:26b=262144 |
| OLLAMA_CHARS_PER_TOKEN_ESTIMATE | 4 | Heuristic for pre-call input size estimation |
| OLLAMA_NUM_CTX_SAFETY_MARGIN | 2048 | Added to (estimated_input + max_tokens) |
| OLLAMA_NUM_CTX_FALLBACK_MAX | 8192 | Used if model not in OLLAMA_MODEL_MAX_CTX |
| OLLAMA_NUM_CTX_HARDWARE_CAP | 32000 | Independent hardware limit — judgement-set, not yet stress-tested against heavy tier |

### Token budgets
| Constant | Value | Description |
|---|---|---|
| STAGE_1_MAX_TOKENS | 1200 | |
| STAGE_2_MAX_TOKENS | 2000 | |
| STAGE_3_MAX_TOKENS | 4000 | Auto-retried at 6000 when truncated — tight, flagged for Day 28 review |
| TRANSLATOR_MAX_TOKENS | 2500 | |

### Intelligence feeds
| Constant | Value | Description |
|---|---|---|
| FEED_SOURCES | list (22) | RSS sources, 6 domains — source of truth is config.py, not this file |
| FEED_KEYWORDS | dict | Per-ticker keyword lists for relevance scoring |
| FEED_MAX_HEADLINES_PER_DOMAIN | 5 | |
| FEED_RELEVANCE_THRESHOLD | 1 | Min keyword match count |
| FEED_MAX_TOTAL_HEADLINES | 30 | Hard cap |

### Other constants
| Constant | Type | Description |
|---|---|---|
| DB_PATH | str | prices.db — known bare-relative-path issue, not yet fixed |
| MODEL_PRICING | dict | Per-million-token USD pricing — Haiku 4.5 $1/$5, Sonnet 4.6 $3/$15, Opus 4.8 $5/$25 (input/output) |
| TICKER_THESIS | dict | Per-ticker structural thesis — 8 entries |
| PORTFOLIO_RELATIONSHIPS | str | Causal chain, ETF layer, concentration risks |
| CORRELATION_PAIRS | list of dicts | Ticker pairs for rolling 30-day Pearson checks |
| SCHEDULE_TIME | '12:00' | Daily Task Scheduler trigger |
| MAX_RUN_MINUTES | 30 | Timeout guard |
| STUCK_RUN_THRESHOLD_MINUTES | 60 | Runs older than this marked failed |
| FIXTURE_DIR | Path | stock-monitor/fixtures/agents/ |
| PRICE_FIXTURE_PATH | Path | stock-monitor/fixtures/normal_day.json |
| ENV_PATH | Path | stock-monitor/.env |

---

## 3. HDB Analyser — config.py Constants

| Constant | Value | Description |
|---|---|---|
| ANALYST_MODEL | claude-sonnet-4-5 | Complex buyer reasoning |
| TRANSLATOR_MODEL | claude-haiku-4-5-20251001 | Plain English rewrite |
| ANALYST_MAX_TOKENS | 1000 | Per-section |
| TRANSLATOR_MAX_TOKENS | 600 | Default |
| TRANSLATOR_SECTION_TOKENS | dict | Per-section budgets: summary=400, what_its_worth/lease_explained/location_and_floor/watch_out_for/before_you_decide/next_steps=900, grant_and_financing=1200 |
| ANALYST_TEMPERATURE | 0.2 | Factual |
| TRANSLATOR_TEMPERATURE | 0.5 | Natural language |
| API_BASE_URL | https://data.gov.sg/api/action/datastore_search | |
| HDB_RESOURCE_ID | d_8b84c4ee58e3cfc0ece0d773c8ca6abc | Resale flat prices from Jan 2017 |
| FETCH_LIMIT | 500 | Raw records from API |
| SAMPLE_SIZE | 20 | Records passed to Claude |
| REQUEST_TIMEOUT | 15 | Seconds |
| DEFAULT_TOWN | SENGKANG | |
| DEFAULT_FLAT_TYPE | 4 ROOM | |
| ANALYST_SECTIONS | list (7) | value_assessment, lease_flag, financing_assessment, upfront_costs, location_signal, red_flags, top_picks |
| TRANSLATOR_SECTIONS | list (8) | summary, what_its_worth, lease_explained, location_and_floor, watch_out_for, grant_and_financing, before_you_decide, next_steps |
| ANALYST_SECTION_DEPENDENCIES | dict | Which prior sections each analyst section receives |

### BUYER_TYPES registry — Layer 1 scaffolding (superseded by RAG when live)

| buyer_type | ehg_eligible | resale_levy | wait_period_months | notes |
|---|---|---|---|---|
| first_timer | True | False | 0 | EHG up to $120,000 |
| second_timer | False | True | 0 | Resale levy $15K–$30K by prior flat size |
| upgrader | False | True | 0 | Levy if first flat was subsidised |
| downgrader | False | True | 0 | Silver Housing Bonus if 55+ |
| private_downgrader | False | False | 15 | 15-month wait from disposal of private property |

All figures indicative — confirm via HFE letter.

---

## 4. Key Functions

### shared/utils.py
**NON-NEGOTIABLE: this module never imports either project's config.py.**
**SOVEREIGNTY RULE: _call_ollama() only ever POSTs to localhost or 127.0.0.1.**

| Function | Returns | Description |
|---|---|---|
| format_warning(severity, file, function, description, fix) | str | Pipe-delimited warning — three questions answered: what / where / fix |
| _call_ollama(prompt, system, model, max_tokens, temperature, base_url, timeout) | (str, dict) | raw requests.post() to Ollama. Raises ValueError if not localhost. |
| call_llm(...) | (str, dict) | Universal Claude/Ollama wrapper. Returns prompt_text in usage dict on all paths. |
| extract_json(raw) | (dict, None) or (None, str) | Extracts clean JSON from model response |
| update_market_history(tickers, use_live) | None | Delta pull from yfinance |
| save_price_fixtures(price_data, fixture_path, capture) | None | Updates fixture JSON |
| send_email_alert(subject, body, env_path, project_tag) | bool | SMTP via Gmail |

### stock_monitor.py — project wrappers (config injection points)
| Wrapper | Injects |
|---|---|
| sm_call_llm(**kwargs) | USE_LIVE_AGENTS, CAPTURE_LIVE_AGENTS_FOR_FIXTURES, FIXTURE_DIR, SLM model resolution, shadow costs |
| sm_save_price_fixtures(price_data) | PRICE_FIXTURE_PATH, CAPTURE_LIVE_DATA_FOR_FIXTURES |
| sm_send_email_alert(subject, body) | ENV_PATH, project_tag='Stock Monitor' |

### feeds.py
| Function | Returns | Description |
|---|---|---|
| fetch_and_store_feeds() | dict | Fetches all 22 sources, scores, stores. Returns summary. |
| get_relevant_headlines(ticker, limit_per_domain, threshold) | list | Top N per domain, capped at FEED_MAX_TOTAL_HEADLINES |
| build_feed_injection(ticker) | str | Formats headlines+summaries for data package |

### database.py — key functions
| Function | Description |
|---|---|
| initialise_db() | Creates all tables, seeds models |
| start_run(run_id, data_mode, slm_model) | Opens run_log entry |
| finish_run(run_id, status, stats) | Closes run_log entry |
| write_prices / write_analysis / write_signal / write_persona_call | Standard write functions |
| write_llm_call(..., prompt_text) | Full LLM audit row — prompt_text param added Day 19 |
| score_persona_call_outcomes() | Scores outcome_5d / outcome_20d against market_history |
| compute_call_cost(model_used, input_tokens, output_tokens) | Returns USD from MODEL_PRICING |

### hdb_analyser.py — key functions
| Function | Description |
|---|---|
| format_for_claude(sample, town, flat_type, buyer_profile) | Injects applicable BUYER_TYPES rules block as third layer |
| run_analyst_section(client, formatted_data, system_prompt) | Runs 7 sections. top_picks returns purchase_rationale + opportunity_flag per pick. |
| run_translator_briefing(...) | Full briefing — returns briefing_dict, text, tokens, duration |

---

## 5. HDB top_picks Output Schema (Day 18)

| Field | Type | Description |
|---|---|---|
| rank | int | 1, 2, or 3 |
| transaction | str | month + storey_range + floor_area_sqm + resale_price + remaining_lease |
| purchase_rationale | str | Why this is a sound purchase for this buyer. Max 50 words. |
| opportunity_flag | str | Value relative to comparables. Or: "No material opportunity identified". Max 40 words. |

---

## 6. Warning Format

```
SEVERITY | file | function() | what happened with variable values | fix action
```

Severity: `ERROR` or `WARN ` (padded to 5 chars). Built via format_warning() in shared/utils.py — never free-form strings.

---

## 7. Mode Flag Matrix

| USE_LIVE_DATA | USE_LIVE_AGENTS | DEV_MODE | Scenario | Cost |
|---|---|---|---|---|
| False | False | True | Full fixture | $0.00 |
| True | False | True | Live prices + fixture agents | $0.00 |
| False | True | True | Fixture prices + live Haiku | ~$0.05 |
| False | True | False | Fixture prices + live Sonnet | ~$0.30 |
| True | True | True | Full live — Haiku | ~$0.05 |
| True | True | False | Full live — Sonnet/demo | ~$0.50 |

---

## 8. SLM Benchmark Results

### Day 19 — real captured prompts
- xl = largest stage1_pragmatist call: 4,559 Anthropic input tokens
- xxl = stage3_meta_agent call: 24,740 Anthropic input tokens / 93,143 characters

**Critical finding:** Ollama's default ~2048-token context silently truncated xxl prompts. phi4-mini post-truncation returned JSON=NO/Dir=NO/Halluc=YES. After num_ctx fix, phi4-mini timed out at 602s × 3 runs. Settled finding — not re-testing without new evidence.

| Model | Size | Result |
|---|---|---|
| phi4-mini | xl | 1.1–1.4 tok/s, JSON=YES, Dir=YES, Halluc=NO |
| phi4-mini | xxl | TIMEOUT 602s (post-fix) × 3 — non-viable for Stage 3 |
| qwen3.6:35b-a3b | xl/xxl | NOT YET BENCHMARKED |
| gemma4:26b | xl/xxl | NOT YET BENCHMARKED |

**Note from Day 17:** gemma4:26b was faster than phi4-mini and gemma4:e4b at Stage 2 xl — model size does not predict speed, especially for MoE architectures. Always benchmark, never assume.

### num_ctx formula (implemented in _call_ollama())
```
required_ctx = min(
    estimated_input_tokens + max_tokens + OLLAMA_NUM_CTX_SAFETY_MARGIN,
    OLLAMA_MODEL_MAX_CTX[model],
    OLLAMA_NUM_CTX_HARDWARE_CAP
)
```
estimated_input_tokens = len(prompt_chars) / OLLAMA_CHARS_PER_TOKEN_ESTIMATE

---

## 9. Live Run Token Baselines

### Day 17 — Stock Monitor (22 feeds active, Haiku)
Run: 2026-06-15_13:23:31

| Call Type | Input Tokens | Output Tokens | Cost |
|---|---|---|---|
| stage1 agents (avg per call) | ~3,646 | ~674 | ~$0.005 |
| stage2_contrarian | ~6,469 | ~1,532 | ~$0.099 |
| stage3_meta_agent | 23,709 | 4,791 | ~$0.048 |
| translator | 5,656 | 1,713 | ~$0.014 |
| TOTAL | 177,881 | 36,109 | $0.3584 |

### Day 18 — HDB Analyser (Sonnet analyst + Haiku translator)

| Stage | Input Tokens | Output Tokens | Duration |
|---|---|---|---|
| Analyst (7 sections, Sonnet) | ~22,400 | ~2,200 | ~60s |
| Translator (8 sections, Haiku) | ~26,100 | ~1,950 | ~33s |
| TOTAL | ~48,500 | ~4,150 | ~93s |

### Day 19 — Stock Monitor live capture run
Run: 2026-06-16_19:41:21 | Cost: $0.3717 | Errors: 0 | Warnings: 0
Stage 3 Meta-Agent prompt captured at 24,740 input tokens / 93,143 chars.
Stage 3 hit STAGE_3_MAX_TOKENS=4000 once, retried at 6000 — flagged for review.

---

## 10. Feed Source Health (Day 17)

| Status | Count | Notes |
|---|---|---|
| OK | 20 | Clean XML, delivering entries |
| WARN | 2 | VentureBeat AI, Google DeepMind — bozo=True but entries delivered |
| FAILED | 0 | All failures resolved |

Source of truth for the full 22-source list: config.py:FEED_SOURCES. Run feeds_audit.py monthly.

---

## 11. Resilience State

| Asset | Location | Recovery |
|---|---|---|
| Code | GitHub Jm888Dev/ai-projects | Full recovery |
| prices.db | C:\Users\Mack\ai-projects\stock-monitor\ | Auto-backup to C:\AI_Projects\backups\stock-monitor\ via reset_db.py |
| .env files | Inside project folders, gitignored | Regenerate from API console |
| venv | C:\Users\Mack\ai-projects\stock-monitor\myenv | pip install -r requirements.txt |
| Ollama binary | C:\Users\Mack\AppData\Local\Programs\Ollama\ | Re-download 5 min |
| Model weights | C:\Users\Mack\.ollama\models\ | phi4-mini 2.5GB, gemma4:e4b 9.6GB, qwen3.6:35b-a3b 23GB, gemma4:26b 17GB |

---

*Last updated: Day 20*
