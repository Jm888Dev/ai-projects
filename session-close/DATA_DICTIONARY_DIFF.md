# DATA_DICTIONARY.md — Day 26 Diff Instructions
# Apply these exact edits to DATA_DICTIONARY.md in Project Knowledge.
# Diff-only — do not rewrite the whole document.

---

## EDIT 1 — §1 llm_calls table: add ticker column row

After this row:
| prompt_text | TEXT | Full prompt sent to model. Added Day 19. |

Add:
| ticker | TEXT | Ticker this call reasoned about. NULL for pre-Day-26 rows. 'portfolio' for stage3_meta_agent and translator. Added Day 26. |

---

## EDIT 2 — §5 shared/utils.py: update extract_json() description

Replace:
| extract_json(raw) | Extracts clean JSON from model response |

With:
| extract_json(raw) | Extracts clean JSON from model response. On JSONDecodeError, attempts json-repair fallback before returning failure — handles missing string-open quotes and other common SLM formatting errors. (json-repair library, Day 26.) |

---

## EDIT 3 — §5 tools/slm_benchmark.py: add load_captured_prompt() row

After the existing EXPECTED_TICKER row in the slm_benchmark.py table, add:
| load_captured_prompt(call_type_prefix, run_id, ticker) | Loads captured prompt from llm_calls. Filters by ticker column (Day 26 fix — previously ORDER BY input_tokens DESC loaded highest-token historical row regardless of ticker). ORDER BY rowid DESC returns most recent. |

---

## EDIT 4 — §8 SLM Routing table: update token budgets

Replace the entire routing table:

| Stage | Primary | Fallback | Mode | Tokens |
|---|---|---|---|---|
| Stage 1 xl | qwen3.6:35b-a3b | gpt-oss:20b | Schema-guided | 2400 / 1800 |
| Stage 2 Contrarian xl | qwen3.6:35b-a3b | **None** — sovereignty decision, Day 25 | Schema-guided | 3600 |
| Stage 3 xxl | gpt-oss:20b | qwen3.6:35b-a3b | Schema-guided | 6000 |
| Translator | qwen3.6:35b-a3b | gpt-oss:20b | Prompt-only | 2400 / 1800 — **UNTESTED, added Day 25** |
| Preprocessing | phi4-mini | — | Prompt-only | 800 — **not called anywhere in live pipeline as of Day 25 audit** |

With:

| Stage | Primary | Fallback | Mode | Tokens |
|---|---|---|---|---|
| Stage 1 xl | qwen3.6:35b-a3b | gpt-oss:20b | Schema-guided | 6000 / 4800 — raised Day 26 (was 2400/1800; v1.1 schema shape raised real floor) |
| Stage 2 Contrarian xl | qwen3.6:35b-a3b | **None** — sovereignty decision, Day 25 | Schema-guided | 6000 — raised Day 26 (was 3600; retried on 2 tickers at 4800) |
| Stage 3 xxl | gpt-oss:20b | qwen3.6:35b-a3b | Schema-guided | 6000 |
| Translator | qwen3.6:35b-a3b | gpt-oss:20b | Prompt-only | 6000 / 4800 — raised Day 26 (was 2400/1800; truncated on 8-ticker run) |
| Preprocessing | phi4-mini | — | Prompt-only | 800 — not called anywhere in live pipeline as of Day 25 audit |

---

## EDIT 5 — §8 OQ-Day25-A: mark partially resolved

Replace:
**OPEN — OQ-Day25-A:** one-ticker live test (NVDA, fixture prices, live SLM agents) truncated 3 of 7 calls even after 1.5x retry...Action: re-run slm_benchmark.py --schema {bull,bear,black_swan,pragmatist,contrarian} at raised max-tokens (3600/4800 candidates) to re-establish real closure floors under the v1.1 schema shape before trusting current SLM_STAGE_MODELS budgets on any live run larger than one ticker.

With:
**PARTIALLY RESOLVED — OQ-Day25-A (Day 26):** Token budgets raised to 6000 primary for Stage 1/2/Translator. Empirically validated by full 8-ticker live run (2026-07-09) — 3 retries fired and resolved, 0 still truncated after retry. Formal benchmark re-run against NVDA captures (slm_benchmark.py --schema) not yet completed but live run confirms stability at current budgets. Formal closure pending next benchmark session.

---

## EDIT 6 — Update footer

Replace:
*Last updated: Day 25*

With:
*Last updated: Day 26*
