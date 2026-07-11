# DATA_DICTIONARY.md
**Stock Monitor + HDB Analyser — Cumulative Data Dictionary**
Verified against actual code as of Day 26. Describes current reality only — never history.
When this conflicts with a Day Summary, this document wins on schema/constant facts; the Day Summary wins on decisions and sequencing.

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

Seeded: claude-haiku-4-5-20251001, claude-sonnet-5, claude-opus-4-8, phi4-mini, gemma4:e4b, qwen3.6:35b-a3b, gemma4:26b

---

### prices
One row per ticker per run. What each agent saw at moment of reasoning.

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
Canonical OHLCV per ticker per trading day. 5-year backfill on first run, delta pull each session.

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
Raw Claude/SLM outputs. One row per agent call per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT NOT NULL | |
| timestamp | TEXT NOT NULL | |
| analysis_type | TEXT NOT NULL | bull / bear / black_swan / pragmatist / contrarian / meta_agent / translator |
| ticker | TEXT | NULL for portfolio-level calls |
| source | TEXT NOT NULL | stock_monitor |
| output | TEXT NOT NULL | Raw model response |
| truncated | INTEGER DEFAULT 0 | 1 if hit token limit |

---

### signals
Derived signals. One row per flagged condition per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| run_id | TEXT NOT NULL | |
| timestamp | TEXT NOT NULL | |
| ticker | TEXT NOT NULL | |
| signal_type | TEXT NOT NULL | kill_trigger / meta_decision / portfolio_relationship_alert / divergence / premortem / persistent_divergence |
| value | REAL | Measured value |
| threshold | REAL | Comparison threshold |
| triggered | INTEGER DEFAULT 0 | 1=fired, 0=evaluated but not triggered |
| direction | TEXT | ACCUMULATE / HOLD / REDUCE / EXIT |
| persona | TEXT | Which agent raised the signal |
| entity_a / relationship / entity_b | TEXT | Reserved for knowledge graph |
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
| tickers_attempted / succeeded / failed | INTEGER | See §11 for a known cosmetic bug in this field when TICKERS is shrunk |
| analyst_input_tokens / output_tokens | INTEGER | Stage 1–3 totals |
| translator_input_tokens / output_tokens | INTEGER | |
| analyst_duration_secs / translator_duration_secs | REAL | Wall clock |
| fallback_used | INTEGER | 1 if fallback model used |
| error_count | INTEGER | |
| total_cost_usd | REAL | Sum of llm_calls.cost_usd |
| notes | TEXT | |
| slm_model | TEXT | "sovereign (per-stage, see llm_calls table)" when USE_SLM=True (changed Day 25 — was a single wrong model name before the fix), NULL when USE_SLM=False. |

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
| model_used | TEXT | Actual model (may be fallback or fixture:call_type). As of Day 25 this correctly reflects real per-stage SLM model when USE_SLM=True — see §8. |
| fallback_used | INTEGER DEFAULT 0 | |
| input_tokens / output_tokens | INTEGER | |
| duration_secs | REAL | |
| cost_usd | REAL | Computed from MODEL_PRICING at insert time |
| status | TEXT DEFAULT success | success / fallback / error |
| error_message | TEXT | |
| retried | INTEGER DEFAULT 0 | 1 if truncation retry triggered |
| truncated | INTEGER DEFAULT 0 | 1 if still truncated after retry |
| retry_budget | INTEGER | Token budget used on retry |
| thinking_tokens | INTEGER DEFAULT 0 | CoT tokens from thinking mode models |
| shadow_cost_haiku_usd | REAL | Hypothetical Haiku cost on SLM token counts |
| shadow_cost_sonnet_usd | REAL | Hypothetical Sonnet cost on SLM token counts |
| prompt_text | TEXT | Full prompt sent to model. Added Day 19. |
| ticker | TEXT | Ticker this call reasoned about. NULL for pre-Day-26 rows. 'portfolio' for stage3_meta_agent and translator. Added Day 26. |

---

### persona_calls
Voting ledger for outcome calibration.

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
| outcome_5d | TEXT | correct / incorrect / partial / void |
| outcome_20d | TEXT | correct / incorrect / partial / void |

---

### feeds
Intelligence feed headlines. Stage 1 storage.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| fetched_at | TEXT NOT NULL | |
| source | TEXT NOT NULL | |
| domain | TEXT NOT NULL | ai / quantum / geopolitics / current_affairs / social / tech |
| title | TEXT NOT NULL | |
| url | TEXT NOT NULL UNIQUE | UNIQUE drives deduplication |
| published | TEXT | |
| summary | TEXT | First 500 chars |
| relevance_score | INTEGER DEFAULT 0 | Max keyword match count |
| tickers_matched | TEXT | Comma-separated tickers matched |
| injected | INTEGER DEFAULT 0 | 1 if included in a data package this run |

---

### slm_benchmarks
SLM benchmark results. One row per model per prompt size per run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | |
| benchmark_run_id | TEXT NOT NULL | bench_YYYY-MM-DD_HH:MM:SS |
| timestamp | TEXT NOT NULL | |
| model | TEXT NOT NULL | |
| prompt_size | TEXT NOT NULL | small / medium / large / xl / xxl |
| prompt_mode | TEXT NOT NULL | synthetic / realistic |
| decode_mode | TEXT NOT NULL DEFAULT 'prompt_only' | prompt_only / schema_guided |
| input_tokens | INTEGER | |
| output_tokens | INTEGER | |
| duration_secs | REAL | |
| tokens_per_sec | REAL | |
| max_tokens | INTEGER | |
| json_valid | INTEGER DEFAULT 0 | |
| direction_valid | INTEGER DEFAULT 0 | |
| hallucination_flag | INTEGER DEFAULT 0 | |
| ticker_mismatch | INTEGER DEFAULT 0 | 1 if output ticker != EXPECTED_TICKER or absent. Pre-Day-22 rows: 0 = unchecked, NOT verified correct. |
| raw_response | TEXT | First 5000 chars |

**Physical column order note:** ALTER TABLE appends — in prices.db physical order is: ...hallucination_flag, raw_response, decode_mode, ticker_mismatch. INSERTs name columns explicitly so order is irrelevant.

---

### Other tables

| Table | Rows/Run | Purpose |
|---|---|---|
| balance_ledger | Manual only | API credit topup tracking |
| thesis_drafts | 0 (populated later) | AI-generated thesis drafts |
| thesis_reviews | 0 (populated later) | Human decisions on drafts |
| sentences | 0 (future) | Per-sentence RAG source |

---

## 2. Stock Monitor — config.py Constants

### Mode flags
| Constant | Default | Description |
|---|---|---|
| USE_LIVE_DATA | True | True=yfinance fetch (changed to True Day 26 — production default) |
| USE_LIVE_AGENTS | False | True=Claude API |
| CAPTURE_LIVE_DATA_FOR_FIXTURES | True | Overwrites normal_day.json when USE_LIVE_DATA=True |
| CAPTURE_LIVE_AGENTS_FOR_FIXTURES | True | Overwrites fixtures/agents/ when USE_LIVE_AGENTS=True |
| DEV_MODE | True | True=all Haiku (~$0.05/run) |
| USE_SLM | True | Routes all agent calls to local Ollama when True (production default as of Day 26) |

### Model routing
| Constant | Value |
|---|---|
| STAGE_1_MODEL | claude-haiku-4-5-20251001 |
| STAGE_2_MODEL | Haiku if DEV_MODE else Sonnet |
| STAGE_3_MODEL | Haiku if DEV_MODE else Sonnet |
| TRANSLATOR_MODEL | claude-haiku-4-5-20251001 |
| FALLBACK_MODEL | claude-haiku-4-5-20251001 |

### SLM config
| Constant | Value | Description |
|---|---|---|
| SLM_STAGE_MODELS | dict | Per-stage nested primary/fallback dict — SOLE routing source of truth. Correctly wired into sm_call_llm() Day 25 (was present but silently misread since Day 24 — see §8). |
| OLLAMA_BASE_URL | http://localhost:11434/api/chat | Sovereignty rule: always localhost |
| OLLAMA_TIMEOUT | 3600 | Seconds |
| OLLAMA_CHARS_PER_TOKEN_ESTIMATE | 4 | Heuristic for pre-call input size estimation |
| OLLAMA_NUM_CTX_SAFETY_MARGIN | 2048 | Added to (estimated_input + max_tokens) |
| OLLAMA_NUM_CTX_FALLBACK_MAX | 8192 | Used if model not in OLLAMA_MODEL_MAX_CTX |
| OLLAMA_NUM_CTX_HARDWARE_CAP | 32000 | Independent hardware limit |

**REMOVED Day 25:** `SLM_MODE`, `SLM_FAST_MODEL`, `SLM_HEAVY_MODEL`,
`SLM_HEAVY_MODEL_STAGE3` — the old two-tier ("fast"/"heavy") routing
system. Confirmed dead code via full-codebase search (no references
outside the two functions fixed this session). Root of a real bug:
`sm_call_llm()` compared `SLM_STAGE_MODELS[stage_key]` (a nested dict
as of Day 24) against the string `"heavy"` — always False — so every
SLM call silently routed to `SLM_FAST_MODEL` (phi4-mini) regardless
of stage. Dormant since `USE_SLM` stayed False throughout Days 21-24.
Fixed Day 25 — see §8.

### OLLAMA_MODEL_MAX_CTX — current values

| Model | Cap | Notes |
|---|---|---|
| phi4-mini | 131072 | |
| gemma4:e4b | 131072 | |
| qwen3.6:35b-a3b | 262144 | |
| gemma4:26b | 262144 | |
| deepseek-r1:14b | 32000 | Degrades ~20K — capped conservatively |
| magistral:latest | 40000 | Degrades past 40K per Mistral docs |
| mistral-small3.2:latest | 131072 | |
| gpt-oss:20b | 131072 | |
| granite4.1:30b | 32000 | Architectural 131K; reliable to 32K on consumer hardware |
| mistral-nemo:12b | 32000 | Advertised 128K; practical ceiling 32K per community benchmarks |

### EXPECTED_TICKER
`"NVDA"` — lives in slm_benchmark.py. Injected into BENCHMARK_SYSTEM_PROMPT; checked against model output in assess_quality(). One source of truth.

### Token budgets (cloud path)
| Constant | Value |
|---|---|
| STAGE_1_MAX_TOKENS | 2500 |
| STAGE_2_MAX_TOKENS | 4000 |
| STAGE_3_MAX_TOKENS | 6000 |
| TRANSLATOR_MAX_TOKENS | 2500 |

**Note (Day 27):** these govern the cloud (Anthropic) path only. Raised Day 27 from live run data: Stage 1 Black Swan failed at 1800, Contrarian failed at 3000, Stage 3 resolved at 6000.
When USE_SLM=True, sm_call_llm() overrides max_tokens entirely with
the per-stage SLM_STAGE_MODELS value — never these cloud-sized numbers.

### Model pricing (June 2026, per million tokens)
| Model | Input | Output |
|---|---|---|
| claude-haiku-4-5-20251001 | $1.00 | $5.00 |
| claude-sonnet-5 | $3.00 | $15.00 |
| claude-opus-4-8 | $5.00 | $25.00 |
| All Ollama SLMs | $0.00 | $0.00 |
Computed at insert time via compute_call_cost() — stored permanently in llm_calls.cost_usd so historical data stays accurate even if pricing changes.

### Intelligence feeds
| Constant | Value |
|---|---|
| FEED_SOURCES | list (22) — source of truth in config.py |
| FEED_MAX_HEADLINES_PER_DOMAIN | 5 |
| FEED_RELEVANCE_THRESHOLD | 1 |
| FEED_MAX_TOTAL_HEADLINES | 30 |

---

## 3. HDB Analyser — config.py Constants

| Constant | Value |
|---|---|
| ANALYST_MODEL | claude-sonnet-4-5 |
| TRANSLATOR_MODEL | claude-haiku-4-5-20251001 |
| ANALYST_MAX_TOKENS | 1000 |
| DEFAULT_TOWN | SENGKANG |
| DEFAULT_FLAT_TYPE | 4 ROOM |
| ANALYST_SECTIONS | 7: value_assessment, lease_flag, financing_assessment, upfront_costs, location_signal, red_flags, top_picks |
| TRANSLATOR_SECTIONS | 8: summary, what_its_worth, lease_explained, location_and_floor, watch_out_for, grant_and_financing, before_you_decide, next_steps |

### BUYER_TYPES registry

| buyer_type | ehg_eligible | resale_levy | wait_period_months |
|---|---|---|---|
| first_timer | True | False | 0 |
| second_timer | False | True | 0 |
| upgrader | False | True | 0 |
| downgrader | False | True | 0 |
| private_downgrader | False | False | 15 |

All figures indicative — confirm via HFE letter.

---

## 4. Pydantic Output Schemas — prompts/schemas.py — v1.1 (Day 25)

Six production Pydantic models. Field order: **identity → reasoning_raw_text
→ evidence → reason → conclude** (changed from v1.0's evidence-first order).

**v1.1 changes, built Day 25:**
- `reasoning_trace` renamed to `reasoning_raw_text`, moved to first
  reasoning-phase field (immediately after persona/ticker identity,
  before any evidence field) in all six schemas.
- `raw_data_citations: Optional[List[str]] = None` added to all six
  schemas. Soft-enforced via prompt instruction (2+ citations, 1+ from
  middle-layer data), NOT via Pydantic `min_length`.
- `TickerDecision` (Stage 3 sub-model) has no persona/ticker identity
  block, so `reasoning_raw_text` is its true first field.
- Rename verified safe: full-codebase search found zero live references
  to `reasoning_trace` outside one comment in config.py (updated).

| Schema | Stage | Direction constraint | Key unique fields |
|---|---|---|---|
| BullOutput | 1 | ACCUMULATE / HOLD only | supporting_evidence, key_assumption, regime_sensitivity, primary_argument, watch_items[2] |
| BearOutput | 1 | REDUCE / EXIT only | supporting_evidence, key_assumption, regime_sensitivity, primary_argument, watch_items[2] |
| BlackSwanOutput | 1 | REDUCE / EXIT only, confidence 1-3 only | structural_fragility, underweighted_risk, contagion_path, unmapped_risk, watch_items[2] |
| PragmatistOutput | 1 | Any of four | volume_assessment, trend_assessment, regime_context, statistical_anchor, watch_items[2] |
| ContrarianOutput | 2 | Any of four | hidden_consensus, shared_blind_spot, unasked_question, strongest_challenge, contrarian_rationale |
| MetaAgentOutput | 3 | N/A portfolio level | portfolio_session, vix_regime, tickers: Dict[str, TickerDecision], portfolio_summary, premortem_flag, premortem_scenario |

---

## 5. Key Functions

### shared/utils.py
**NON-NEGOTIABLE: never imports either project's config.py.**
**SOVEREIGNTY RULE: _call_ollama() only POSTs to localhost or 127.0.0.1.**

| Function | Description |
|---|---|
| format_warning(severity, file, function, description, fix) | Pipe-delimited warning |
| _call_ollama(...) | raw requests.post() to Ollama |
| call_llm(..., output_schema=None) | Universal Claude/Ollama wrapper. When output_schema is not None and use_slm=False, uses Anthropic tool_use: adds tools + tool_choice, extracts tool_block.input, serialises to json.dumps() so extract_json() downstream is unchanged. Added Day 27. |
| extract_json(raw) | Extracts clean JSON from model response. On JSONDecodeError attempts json-repair fallback before returning failure — handles missing string-open quotes and other common SLM formatting errors. (json-repair library added Day 26.) |
| update_market_history(tickers, use_live) | Delta pull from yfinance |
| save_price_fixtures(price_data, fixture_path, capture) | Updates fixture JSON |
| send_email_alert(subject, body, env_path, project_tag) | SMTP via Gmail |

### stock_monitor.py — _resolve_schema() — ADDED Day 27

| _resolve_schema(call_type) | Maps call_type prefix to Pydantic schema's .model_json_schema() for Anthropic tool_use. Returns None for Translator and unknowns (plain text path). Lives in stock_monitor.py — not shared/ — to preserve shared/never-imports-project-config rule. |

### stock_monitor.py — sm_call_llm() — REWRITTEN Day 25, UPDATED Day 27
Resolves stage_key from call_type (stage1/stage2/stage3/translator),
reads the nested `SLM_STAGE_MODELS[stage_key]` dict correctly (primary
+ fallback sub-dicts, each with model/mode/max_tokens). Attempts primary,
then fallback only if primary fails AND a fallback is configured for that
stage. No cross-provider (SLM→cloud) fallback exists. max_tokens is always
read from SLM_STAGE_MODELS, never from cloud-sized STAGE_N_MAX_TOKENS,
when USE_SLM=True.

### tools/slm_benchmark.py
| Item | Description |
|---|---|
| EXPECTED_TICKER | "NVDA" — injected into system prompt; checked in assess_quality() |
| --schema {bull,bear,...} | Activates schema-guided decoding |
| assess_quality(text, schema_dict=None) | Schema-aware + ticker_mismatch check |
| load_captured_prompt(call_type_prefix, run_id, ticker) | Loads captured prompt from llm_calls filtered by ticker column (Day 26). ORDER BY rowid DESC — most recent capture. Previously ORDER BY input_tokens DESC caused benchmark to always load highest-token historical row regardless of ticker (root cause of G3B.SI drift in benchmark). |
| print_results_table(results) | Displays Mismatch column |

---

## 6. HDB top_picks Output Schema

| Field | Type | Description |
|---|---|---|
| rank | int | 1, 2, or 3 |
| transaction | str | month + storey_range + floor_area_sqm + resale_price + remaining_lease |
| purchase_rationale | str | Max 50 words |
| opportunity_flag | str | Max 40 words. Or: "No material opportunity identified" |

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

## 8. SLM Routing — LOCKED Day 24, WIRED Day 25, BUDGETS RAISED Day 26

| Stage | Primary | Fallback | Mode | Tokens (primary / fallback) |
|---|---|---|---|---|
| Stage 1 xl | qwen3.6:35b-a3b | gpt-oss:20b | Schema-guided | 6000 / 4800 — raised Day 26 (was 2400/1800; v1.1 schema raised real floor) |
| Stage 2 Contrarian xl | qwen3.6:35b-a3b | **None** — sovereignty decision, Day 25 | Schema-guided | 6000 — raised Day 26 (was 3600; retried on 2/7 tickers at 4800 before raise) |
| Stage 3 xxl | gpt-oss:20b | qwen3.6:35b-a3b | Schema-guided | 6000 / 6000 |
| Translator | qwen3.6:35b-a3b | gpt-oss:20b | Prompt-only | 6000 / 4800 — raised Day 26 (was 2400/1800; truncated on 8-ticker run) |
| Preprocessing | phi4-mini | — | Prompt-only | 800 — not called anywhere in live pipeline as of Day 25 audit |

**Stage 2 fallback = None, explained:** gpt-oss:20b drifted on contrarian xl benchmark.
Sovereignty stance: Stage 2 failure stays inside sovereign tier (fails gracefully),
never substitutes cloud. Long-term goal is a sovereign SLM replacement.

**Translator routing:** never benchmarked in Days 21-24. Day 25 decision: route onto
Stage 1 models (JSON-to-prose synthesis closer to Stage 1 work). Deliberate, pragmatic,
WITHOUT benchmark evidence. Completed 8-ticker run without truncation at 6000 tokens (Day 26).

**Day 25 bug found and fixed:** sm_call_llm() compared SLM_STAGE_MODELS[stage_key]
(a dict since Day 24) against string "heavy" — always False. Every SLM call silently
routed to phi4-mini regardless of stage. Fixed Day 25 — verified via live run.

**PARTIALLY RESOLVED — OQ-Day25-A (Day 26):** Token budgets raised to 6000 primary
for Stage 1/2/Translator. Validated by full 8-ticker live run — 3 retries fired and
resolved, 0 still truncated. Formal benchmark re-run (slm_benchmark.py --schema)
against NVDA captures not yet completed — pending next benchmark session.

### Per-model verdict

| Model | Schema | Routing role | Key findings | Notes |
|---|---|---|---|---|
| qwen3.6:35b-a3b | YES | Stage 1 primary, Stage 2 primary, Stage 3 fallback, Translator primary | Richest schema reasoner at xl. Only model to pass contrarian xl without drift. reasoning_raw_text populated spontaneously. | Thinking mode likely explains drift resistance (OQ-Day24-A, untested). |
| gpt-oss:20b | YES | Stage 1 fallback, Stage 3 primary, Translator fallback | Speed leader across all sizes. 923s at xxl. | Drifted on contrarian xl — excluded from Stage 2. |
| phi4-mini | YES (thin) | Preprocessing only (not currently called) | Fast, thin content. Content drift at xxl. | Never Stage 1+. |
| gemma4:e4b | YES | Not routed | Schema degrades at xl. | Observe in next benchmark session. |
| gemma4:26b | CONDITIONAL | Not routed | FSM collapse at small/medium. Clean at xxl 6000. Drifted on contrarian xl. | Prompt-only only for reliable use. |
| deepseek-r1:14b | YES | Not routed | Solid but slow (~57 min xxl). OOM at contrarian xl 6000. | Re-test only if hardware improves. |
| magistral:latest | NO | RETIRED | Schema constraint never engages. Weakest quality. | Do not route. |
| mistral-small3.2:latest | YES | Not routed | Functional but thin. Drifted on contrarian xl. | Adequate tertiary fallback only. |
| granite4.1:30b | YES | Parked — weekly only | Strong contrarian quality. ~21 min per xl call — too slow for daily runs. | Possible weekly deep-analysis option. |
| mistral-nemo:12b | YES | Not routed | Fast, strong xxl bull. Drifted on contrarian xl. | Not routed. |

### Prompt size reference
- xl = largest stage1_pragmatist call: ~4,559 Anthropic input tokens
- xxl = stage3_meta_agent call: 24,740 Anthropic input tokens / 93,143 characters

### Key benchmark principles (locked)
- Schema-guided decoding changes output token distribution — cannot mix with prompt-only without mode tag (OQ-Day21-A)
- Grounding instructions necessary but not sufficient — only thinking-mode model resisted contrarian drift
- Content drift (OQ-Day23-A): ticker field correct, reasoning body about wrong instrument
- MoE architecture: model size does not predict speed — always benchmark
- A locked routing table means nothing if consumer code doesn't read it correctly — verify with real run (Day 25)
- **Benchmark data-source bug vs model failure are indistinguishable without reading the SQL (Day 26):** ORDER BY input_tokens DESC always loaded highest-token historical row regardless of ticker — looked like G3B.SI anchoring, was deterministic mislabeling

---

## 9. Live Run Token Baselines (Day 26, 8-ticker SLM run, USE_SLM=True)

Note: TICKERS config has 8 entries (NVDA, AVGO, LITE, TSM, QQQ, SMH, G3B.SI, ^VIX). ^VIX is fetched as context data only — it does not receive its own Stage 1 agent pass. Token totals below cover the 7 independently analyzed tickers.

| Call Type | Input Tokens (total, 7 analyzed tickers) | Output Tokens (total) |
|---|---|---|
| stage1_bull | 28,018 | 25,044 |
| stage1_bear | 27,962 | 24,175 |
| stage1_black_swan | 28,340 | 23,798 |
| stage1_pragmatist | 28,711 | 22,700 |
| stage2_contrarian | 40,286 | 29,072 |
| stage3_meta_agent | 12,157 | 4,990 |
| translator | 2,342 | 3,877 |
| TOTAL | 167,816 | 133,656 |

Cost: $0.00 (sovereign SLM). Duration: 15,714s (~4.4 hours). 3 retries resolved, 0 truncated.

---

## 10. Resilience State

| Asset | Location | Recovery |
|---|---|---|
| Code | GitHub Jm888Dev/ai-projects | Full recovery |
| prices.db | C:\Users\Mack\ai-projects\stock-monitor\ | Auto-backup via reset_db.py |
| .env files | Inside project folders, gitignored | Regenerate from API console |
| venv | C:\Users\Mack\ai-projects\stock-monitor\myenv | pip install -r requirements.txt |
| Ollama binary | C:\Users\Mack\AppData\Local\Programs\Ollama\ | Re-download 5 min |
| Model weights | C:\Users\Mack\.ollama\models\ | phi4-mini 2.5GB, gemma4:e4b 9.6GB, qwen3.6:35b-a3b 23GB, gemma4:26b 17GB, deepseek-r1:14b 9.0GB, magistral 14GB, mistral-small3.2 15GB, gpt-oss:20b 13GB, granite4.1:30b ~20GB, mistral-nemo:12b ~7GB |

---

## 11. Known Cosmetic Bug (Day 25, not fixed)

`main()`'s run summary computes `tickers_succeeded` from fixture price data (always
returns all 8 tickers) against `tickers_attempted` (correctly reads `len(config.TICKERS)`).
Shrinking TICKERS produces a nonsensical negative "failed" count. Cosmetic only.
Queued as Forward Queue item 9.

---

*Last updated: Day 27*
