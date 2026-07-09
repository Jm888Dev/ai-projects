# Forward_Queue.md
**Stock Monitor + HDB Analyser — Active Tracking**
Full regeneration each session close. Carries the Forward Queue, Backlog/Open Questions, and Change Log — everything that moves regularly. Stagnant project definition (context, goals, rules, roster, feed roadmap, investment rationale, governance) lives in Master_Plan.md.

**Last updated:** Day 26

---

## 1. Forward Queue (ordered, no day numbers attached)

Cleanup precedes new capability, within each project. Concept tags reference Master_Plan.md §5.

1. Stock — **cleanup: remove premature GROUNDING RULE lines from Stage 1 system prompts** — Bull, Bear, Black Swan, Pragmatist system prompts each have a GROUNDING RULE block added Day 26 before root cause of ticker drift was identified. Root cause was a SQL ordering bug in `load_captured_prompt()`, not model anchoring. The prompts already had grounding instructions. These four lines are harmless but unnecessary noise. Low effort. *(Cleanup)*
2. Stock — **Anthropic tool-use wiring for LLM path**: use schemas as tool input_schema definitions. *(SLM)*
3. Stock — **Translator SLM benchmark**: Translator was never benchmarked (Days 21-24 grid covered Stage 1/2/3 schemas only). Currently routed onto Stage 1's models (qwen3.6 primary/gpt-oss fallback, prompt-only, 6000/4800 tokens as of Day 26). Needs its own benchmark pass (model, token budget) before being treated as locked routing. *(SLM)*
4. Stock — **qwen3.6:35b-a3b prompt-only xl re-run at 3600 max-tokens** (hit 1800 ceiling in Day 23) — completeness item, low priority now routing is locked on schema-guided. *(SLM)*
5. Stock — **formal benchmark re-run after token budget raise** (OQ-Day25-A partial): slm_benchmark.py --schema {bull,bear,black_swan,pragmatist,contrarian} against NVDA captures from Day 26 run. Budgets now empirically validated by live run but formal benchmark pass not yet done. *(SLM)*
6. Stock — **dynamic token budgeting** (Gap 3, Day 24 wargame): hard cap on feed injection that tightens when total feed tokens exceed threshold during high-volatility/earnings periods. Option A implementation — count HIGH_IMPACT Layer 7 events, truncate to top N by impact score. Pure Python, builds on existing relevance scoring in feeds.py. Build alongside item 18/19. *(Intelligence)*
7. HDB — **quick hygiene**: translator $ rule, financing section order, drop `first_time_buyer` backward-compat boolean. *(Cleanup)*
8. HDB — **Regulatory RAG**: ChromaDB install, source doc shortlist, chunking, retrieval, buyer_type-conditioned answers, one grounded Q&A test. *(RAG)*
9. Stock — **small hygiene**: shadow cost display, db_inspector.py, fix tickers_succeeded/tickers_attempted mismatch when TICKERS is shrunk for testing (Day 25 — cosmetic only, does not affect real pipeline behavior). *(Cleanup)*
10. Stock — **Contrarian role expansion** (epistemic audit, prompt-only). Review `regime_sensitivity` field guidance in Bear system prompt — QQQ bear inverted the logic (high_vix should strengthen bear thesis; model wrote "weakens"). *(Agentic AI)*
11. HDB — **national feed**: granularity upgrade, recency-weighted aggregates, hdb.db. *(Foundational)*
12. Stock — **Arbitrator / Stage 2.5 build**. *(Agentic AI)*
13. HDB — **Devil's Advocate**, on local SLM. *(Agentic AI + SLM)*
14. Stock — **grounding pass** across Stage 1/2/2.5/3. *(Agentic AI)*
15. Stock — **multi-model diversity** across Stage 1. *(Multi-model agents)*
16. Stock — **eval harness v1**. *(Evals & Observability)*
17. Stock — **audit lineage Gaps 2 & 3** (prompt versioning, compression lineage). *(Evals & Observability)*
18. Stock — **full article extraction + Layer 7 event/entity classification**. *(Intelligence enrichment)*
    **GRAPH-FIRST DESIGN CONSTRAINT (Day 24):** item 18's entity extraction schema IS the knowledge graph node schema. Every extracted event must carry: (a) stable entity ID, (b) typed relationship, (c) source provenance tag, (d) impact score. Built correctly, the KG at item 25 is an accumulation of item 18's output.
    **Scope:** includes dedicated summarisation layer (one Haiku call per document, 200-400 token structured output), EDGAR 8-K parser, earnings transcript parser, BIS export control feed. Event-type-to-persona routing map: see Master_Plan.md §7.
19. Stock — **selective persona routing by event type**. *(Agentic AI, builds on 18)*
    **Must be built with item 18 — not sequentially after. Items 18 and 19 are a single architectural unit.**
20. Stock — **schemas.py: add `additional_context: Optional[str]` overflow field** to Stage 1 schemas as feed-derived insight channel. Build after item 18 is live. Gates on OQ-Day21-B resolution. *(SLM + Intelligence)*
21. Stock — **paper-trading harness + holdings tables**.
22. Both — **Streamlit UI v0** (Stock + HDB).
23. Stock — **MCP exposure** of get_prices/get_signals/run_analysis. *(MCP)*
24. Stock — **stateful memory + AI thesis drafting** with rejection-history awareness. *(Memory)*
25. Stock — **knowledge graph v1**, six layers. *(Knowledge Graph)*
26. Stock — **sovereign Stage 2 SLM fallback hunt**: every non-qwen3.6 model drifted on contrarian xl. Stage 2 currently fails gracefully with no fallback. Goal is a sovereign SLM replacement, not a permanent cloud safety net. *(SLM)*

---

## 2. Backlog & Open Questions

| ID | What it is | Status |
|---|---|---|
| OQ-001 | Arbitrator / Stage 2.5 | Confirmed, queued (item 12) |
| OQ-002 | Self-reflection at Stage 1 | Parked — conflicts with extreme-persona design (Day 9) |
| OQ-003 | Iterative debate loop on deadlock | Backlogged — needs OQ-001 first |
| OQ-004 | Audit lineage | Gap 1 closed Day 19. Gaps 2+3 queued (item 17). Gap 4 ties to Streamlit. |
| OQ-005 | Contrarian epistemic audit expansion | Confirmed, queued (item 10) |
| OQ-006 | Feed Relevance Engine three-layer architecture | Designed Day 16, write-up pending |
| OQ-008 | RUN_MODE single-switch replacing four-flag system | Backlogged |
| OQ-Day21-A | Schema-guided directional bias in calibration data | Open — answer when enough paired runs exist |
| OQ-Day21-B | Fixed schemas limit feed context from 20+ sources | Open — answer when item 18 is live |
| OQ-Day21-C | gemma4:26b collapse — context-size/budget-dependent | Partially resolved Day 23. Not fully closed. |
| OQ-Day23-A | Content drift — ticker field correct, reasoning body about wrong instrument | Open — build after routing confirmed |
| OQ-Day24-A | Why only qwen3.6 resists contrarian drift | Parked post-KG |
| OQ-Day24-B | Does Item A reorder measurably improve mid-context attention | Answer via eval harness (item 16) |
| OQ-Day24-C | Does KG hierarchical retrieval prevent lost-in-the-middle at scale | Answer at item 25 |
| OQ-Day25-A | schemas.py v1.1 raised real schema-closure token floor | PARTIALLY RESOLVED Day 26 — budgets raised to 6000 primary, validated by 8-ticker live run. Formal benchmark re-run pending (item 5). |
| OQ-Day26-A | QQQ bear `regime_sensitivity` inverted — "weakens in high_vix" for a bear thesis (should strengthen). Content quality gap in Bear system prompt guidance. | Open — review Bear prompt regime_sensitivity instruction (item 10) |
| Non-Qwen Stage 2 fallback | Every non-Qwen model drifts on contrarian. No cloud fallback exists or planned as permanent. | Queue item 26 |
| Item C corpus split | Bull/Prag → gpt-oss (Western), Bear/BS → qwen3.6 (Chinese). Directionally agreed. | Parked post-KG |
| Asymmetric debate loop | Pragmatist + Black Swan critique pass before Contrarian. | Queue after Arbitrator (item 12) |
| XML anchoring | Wrap Layer 3/4 in XML tags. Cloud path first. | Queue with item 18 |
| reasoning_raw_text extraction gap | Populated by model but never extracted into its own field/column. | Parked, no urgency yet |
| data_quality_flag fire-rate tracking | Need detection process tracking fire rate per ticker/data source over time. | No queue position yet |
| tickers_succeeded/tickers_attempted cosmetic bug | Nonsensical negative "failed" count when TICKERS shrunk for testing. | Queue item 9 |

---

## 3. Change Log

**v1.0–v1.5 archived** to CHANGELOG_ARCHIVE.md.

- **v1.6 / Day 25 restructure:** schemas.py v1.1. sm_call_llm() bug fixed. Stage 2 fallback None. Translator SLM-routed (untested). Dead two-tier SLM_MODE deleted. One-ticker live SLM test confirmed routing. Document architecture overhaul: Master_Plan.md split from Forward_Queue.md; DATA_DICTIONARY.md diff-only; three archive files introduced. Full governance system written into Master_Plan.md §12.
- **v1.7 / Day 26:** `llm_calls.ticker` column added — ALTER TABLE + database.py + write_llm_call() + 4 call sites in stock_monitor.py. `load_captured_prompt()` fixed: ticker filter replaces input_tokens DESC ordering (root cause of benchmark always loading G3B.SI). Stage 1/2/Translator SLM token ceilings raised to 6000 primary. json-repair fallback in extract_json(). TARGET TICKER framing added to run_stage1_agent() call site. GROUNDING RULE added to Stage 1 prompts (premature — cleanup queued as item 1). Full 8-ticker live SLM run clean: 0 errors, 0 warnings. OQ-Day26-A logged (QQQ bear regime_sensitivity inverted).
