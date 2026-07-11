# AI Builder Master Plan
**Stock Monitor + HDB Analyser — Stagnant Reference**
Diff-edited only, touched rarely. Forward Queue, Backlog/Open Questions, and Change Log live in Forward_Queue.md — that document carries all regular churn. This document holds the content that defines the project rather than tracks its progress.

---

## 1. Builder Context

Enterprise IT engineer at a global bank (engineering, not ops), Singapore. Advanced SQL; returning Python builder. Won an internal prompt engineering competition; an AI ops opportunity is on the horizon. Three concurrent aims: become a credible AI builder (primary), become the AI SME within IT infrastructure, keep entrepreneurial optionality open. Learns by building; uses pushback and challenge as a design tool; thinks systemically and across domains.

---

## 2. Two Products

**Stock Monitor** — multi-agent adversarial pipeline over a semiconductor supply-chain thesis (NVDA, AVGO, LITE, TSM, QQQ, SMH, G3B.SI, ^VIX). Agent roster: §6.

**HDB Analyser** — Singapore public housing resale buyer intelligence. National coverage (pending), buyer_type-conditioned analysis. Agent roster: §6.

Both products must be personally usable for real decisions — that's the actual test, not a calendar date.

---

## 3. Goal-State Criteria (replaces day-bound milestones)

A product is "done" for this phase when its list below is true — not on a specific day.

**Stock Monitor:**
- 3-stage-plus workflow firmed up: Arbitrator built, grounding pass applied (cite-only-provided-data, "insufficient data" is a valid answer), Contrarian's epistemic audit live, eval harness passing consistency checks
- Multi-model agents live across Stage 1
- Proper intelligence feeds: full article extraction, Layer 7 event/entity classification, selective persona routing, EDGAR + BIS feeds live
- Schema-guided decoding wired into production (_call_ollama() — DONE Day 25; Anthropic tool-use path — DONE Day 27)
- Streamlit UI v0 live: signals, paper-trade P&L vs. holdings benchmark, feed reading pane, thesis review screen

**HDB Analyser:**
- National feed live (cross-town, not town-relative only)
- Buyer modes conditioned via RAG against `buyer_type` (BTO explicitly out of scope)
- Regulatory RAG live (ChromaDB), indicative-pending-HFE caveat retained for every buyer_type
- Streamlit UI v0 live: buyer workflows, national shortlist, RAG Q&A

**Long-horizon, no day attached:** both products in continued real use with classical ML baselines alongside agents; one product Dockerized as a FastAPI service; both pipelines observable with versioned prompts and regression evals; an MCP server built, red-teamed, and hardened; Feed Stage 2 live with injection defenses; local SLM serving as a documented, genuine offline-fallback tier — not just a manual switch; three written artifacts (LLM-vs-ML judgment, Hermes "what I'd steal" note, AI governance crib sheet); G3B.SI false-diversifier thesis formally re-evaluated; hardware evaluation (DGX Spark / AMD Ryzen AI Max) after knowledge graph is built and real workload is understood.

---

## 4. Operating Rules

1. **Sessions, not days, never pre-bound.** A Day is a session, not a calendar date, and never a content commitment made in advance. The Forward Queue (Forward_Queue.md) holds no day numbers, only order. Whatever a session actually delivers becomes that Day's entry, logged retrospectively in SESSION_LEDGER.md.
2. **Nothing is cut, only rolled or resequenced.** No pre-committed cut order; the builder manages catch-up via double sessions.
3. **Scope freeze per session.** New ideas go to Forward_Queue.md's Backlog or wait for next session — never injected mid-session.
4. **Fix outstanding before building new**, within each project's own queue. New-capability sequencing across both projects follows the AI concept ranking (§5).
5. **One project per session.** A single multi-step thread may span consecutive sessions of the same project without breaking this rule.
6. **Every session has a micro-fallback** for sub-hour windows.
7. **15-minute cap on design decisions.** Overflow goes to Forward_Queue.md's Backlog.
8. **Sequencing gates, non-negotiable:** no real money before written graduation criteria are met on forward paper-trading data; Feed Stage 2 never starts before red-teaming/injection-defense work is done (Feed Stage 1 plumbing is exempt); every HDB shortlisted flat is manually verified against official sources before any real-world action.
9. **Ambiguity → precedence hierarchy:** this document + Forward_Queue.md (together, "the plan") → most recent Day Summary (wins on conflict, forces a changelog revision next session) → earlier summaries. No other document is ever authority.
10. **Version freeze on publication.** Any post-publication change to this document bumps no version number — it is diff-edited in place, since it is stable reference content, not a chronologically-versioned narrative. Forward_Queue.md, being fully regenerated each close, retains its own Change Log for that purpose.
11. **Document governance** — see §17.

---

## 5. AI Concept Ranking

| Rank | Concept | Why | Where it lives |
|---|---|---|---|
| 1 | Agentic AI / multi-agent orchestration | Biggest existing investment; everything else depends on this being trustworthy | Stock: Arbitrator, grounding pass, Contrarian audit. HDB: Devil's Advocate |
| 2 | RAG | Core anti-hallucination lever; directly serves HDB's regulatory goal | HDB Regulatory RAG |
| 3 | SLM / local inference | Mostly built; mainly needs closing out, not new design | Stock heavy-tier test plan, routing decision, real fallback wiring |
| 4 | Multi-model agents | Genuine model-family diversity, not same-model-different-prompt | Stock Stage 1 diversity; HDB Devil's Advocate on a different model than the Analyst |
| 5 | Evals & Observability | The measurement layer underneath the "firmed up" claim | Stock eval harness, audit lineage Gaps 2–3 |
| 6 | AI Security / prompt injection defense | Already gated explicitly on Feed Stage 2 in this plan | Concrete once feed enrichment + Stage 2 exist |
| 7 | MCP | Interop/credibility value; doesn't change either product's reasoning quality | Expose Stock's get_prices/get_signals/run_analysis |
| 8 | Classical ML / LLM-vs-ML judgment | Knowing when *not* to use an LLM is the more sophisticated signal | Unscheduled — follows HDB national feed + a Stock ML baseline |
| 9 | Memory / statefulness | Distinct from RAG and orchestration — cross-run thesis revision history | Stock stateful memory + AI thesis drafting |
| 10 | Knowledge Graph | Capstone — depends on entity/event extraction maturing first | Stock six-layer graph |
| — | Explainability / Governance | Reading track, not a build item — highest direct relevance to "AI SME at a bank" on this list | Governance Thread (§10), ongoing |

---

## 6. Agent Roster

### Stock Monitor

| Agent | Stage | Nature | Status |
|---|---|---|---|
| Bull / Bear / Black Swan / Pragmatist | 1 | Deliberately one-dimensional, extreme bias by design — extremity prevents middle-of-the-road synthesis (locked Day 9). Parallel, isolated, no cross-talk. Output contracts: BullOutput, BearOutput, BlackSwanOutput, PragmatistOutput schemas in prompts/schemas.py. Direction constraints encoded at type level. | Built. Schemas added Day 21, updated to v1.1 Day 25. |
| Contrarian | 2 | Structured epistemic audit: consensus, contradictions, unique insights, blind spots — not just "critique the consensus." Output contract: ContrarianOutput schema. | Expanded role confirmed; prompt-only change not yet written. Schema built. SLM routing: qwen3.6 primary, no fallback (Day 25 sovereignty decision — no SLM currently resists contrarian drift besides qwen3.6, and a cloud fallback was deliberately not substituted in its place). |
| Arbitrator | 2.5 | Neutral. Reads the same compressed inputs Meta reads, ranks arguments independently, names the strongest case per side, decisive evidence, verdict-flip conditions. Never decides. | New, confirmed; fixes the current maker-checker violation (Meta self-arbitrates). |
| Meta-Agent / Portfolio Manager | 3 | Portfolio-level synthesis across all tickers; ACCUMULATE/HOLD/REDUCE/EXIT + kill triggers — target state decides from the Arbitrator's pre-weighed record. Output contract: MetaAgentOutput schema with nested TickerDecision per ticker. | Built (self-arbitrating version); target version pending. Schema built Day 21, updated v1.1 Day 25. |
| Translator | 4 | Plain English briefing from Meta-Agent output. Plain text only — schema-guided decoding does not apply. | Built. SLM routing added Day 25 (qwen3.6/gpt-oss) — UNTESTED, no benchmark exists for Translator specifically; it was missed by the Days 21-24 benchmark grid entirely. |
| Narrator | Layer 1 | Weekly storyline, Magnifica Humanitas register — connects AI research, geopolitics, human meaning. Reads feed content directly. | Stubbed since Day 10; gated on Feed Stage 2 injection defenses before activation. |

### Output Schema Architecture (prompts/schemas.py — added Day 21, v1.1 Day 25)

Six Pydantic models defining the formal output contract for each agent. Field order: **identity → reasoning_raw_text → evidence → reason → conclude** (v1.1, Day 25 — `reasoning_trace` renamed to `reasoning_raw_text` and moved to first reasoning-phase field, immediately after persona/ticker identity, so the model reasons on paper before the constrained-decoding FSM locks it into a conclusion). Optional fields on all: `reasoning_raw_text` (scratchpad, now first), `raw_data_citations` (verbatim numeric citations, soft-enforced via prompt instruction rather than a schema minimum, added v1.1 — a hard-required minimum would force fabrication when input data is genuinely thin), `data_quality_flag` (graceful failure when data — or citations — are insufficient). Adversarial direction constraints encoded at type level — Bull cannot produce REDUCE, Black Swan confidence capped at 3. Used for schema-guided decoding via Ollama `format` parameter (SLM path, correctly wired into sm_call_llm() Day 25 after a bug fix — see DATA_DICTIONARY §8) and Anthropic tool_use wiring (LLM path — wired Day 27 via _resolve_schema() in stock_monitor.py + output_schema param in call_llm()).

### HDB Analyser

| Agent | Nature | Status |
|---|---|---|
| Analyst | Technical/factual, 7 sections, rules routed by `buyer_type` — never assumes first-timer | Built |
| Devil's Advocate | Adversarial review of the Analyst's purchase_rationale/opportunity_flag. Runs on a local SLM — deliberate model-family isolation from the Analyst. | New, confirmed |
| Translator | Complete-beginner audience, plain text only, term-definition format prescribed | Built |

---

## 7. Intelligence Feed Roadmap

**Live:** 22 RSS sources across AI, Quantum, Geopolitics, Current Affairs (SG/JP/EU/US/CN lenses), Social, and Tech domains — full list is `config.py:FEED_SOURCES`, the source of truth. Manual-only, never automated: The Rundown, TLDR, Professor Casey AI Ethics.

**Phase 1 — Article → Event → Impact:**

| Item | What it does | Why |
|---|---|---|
| Full article body extraction | web_fetch on every RSS URL, stores full text | Prerequisite for everything below |
| Dedicated summarisation layer | One Haiku call per document → 200-400 token structured output. Applies to RSS articles, EDGAR 8-K filings, earnings transcripts, BIS notices | Raw injection of long documents is not viable at any model tier — a 15,000-word earnings transcript would consume the entire Stage 1 context budget |
| Entity + event extraction (Layer 7: AI_GPU_DEMAND, EXPORT_CONTROL, HBM_SHORTAGE, FOUNDRY_EXPANSION, POWER_CONSTRAINT, OPTICAL_NETWORKING, QUANTUM_BREAKTHROUGH) | One Haiku call per article | Lets agents reason over classified events, not raw headlines |
| EDGAR 8-K + BIS export control feeds | Primary-source legal/regulatory disclosures | A single export restriction can permanently shift a thesis overnight |
| Earnings transcripts | Quarterly input stream, all eight tickers | CapEx guidance, demand commentary, supply constraints — the most signal-dense document per ticker per quarter |
| Selective persona routing | Event type determines which personas receive which content | Without routing, full article extraction is a firehose into every agent. Full article extraction and selective routing are a single architectural unit — see Forward_Queue.md for build sequencing. |

**Event-type-to-persona routing map (draft):**

| Event type | Personas |
|---|---|
| EXPORT_CONTROL | Bear, Black Swan |
| AI_GPU_DEMAND | Bull, Pragmatist |
| FOUNDRY_EXPANSION | Bull, Pragmatist |
| HBM_SHORTAGE | Bear, Black Swan |
| POWER_CONSTRAINT | Bear, Contrarian |
| OPTICAL_NETWORKING | Bull (LITE-relevant) |
| QUANTUM_BREAKTHROUGH | Black Swan |

**Phase 2 — Where the edge begins:** earnings transcripts (Bull/Pragmatist); practitioner Reddit + Hacker News → Narrator/Contrarian baseline only, never Stage 1 input; supply chain relationship map; selective persona routing by event type.

**Permanent exclusions:**

| Excluded | Why |
|---|---|
| Options flow | Day-trading infrastructure, wrong horizon |
| Satellite imagery / shipping data | Hedge-fund infrastructure, not feasible solo |
| Composite alpha score (weighted formula) | Arbitrary weights produce confident wrong answers — defer until 50+ sessions of outcome-scoring data exist |
| Retail social sentiment as agent input | Noise at this horizon — Narrator human texture only |

---

## 8. Investment Universe Rationale

| Instrument | Role | Note |
|---|---|---|
| G3B.SI | Core stability, SG dividend ETF | Flagged false-diversifier — correlates 0.831 with SMH (Day 12), formal re-evaluation in long-horizon goals |
| QQQ, SMH | Core stability / thematic growth | SMH structurally overlaps NVDA + TSM — concentration risk to flag explicitly in commentary |
| NVDA, AVGO, LITE, TSM | Tracking only, no capital deployed | Reasoned as a connected supply chain — demand anchor → network gatekeeper → photonics → production floor |
| ^VIX, ^TNX, USDSGD=X | Macro context | Distinguishes fear-driven vs. rate-driven vs. FX-driven price moves |

Full per-ticker thesis and portfolio relationships: `config.py:TICKER_THESIS`, `config.py:PORTFOLIO_RELATIONSHIPS`.

---

## 9. Document Register

| Document | Class | Read at session start? | Role |
|---|---|---|---|
| Master_Plan.md (this document) | Authority — stagnant reference | Yes | The project's definition: context, products, goals, rules, roster, feed roadmap, investment rationale, governance. First in the precedence hierarchy alongside Forward_Queue.md. |
| Forward_Queue.md | Authority — active tracking | Yes | Forward Queue, Backlog/Open Questions, Change Log. Carries all regular churn. |
| Day N Summary (.md) | Historical record | Yes, most recent only | New file each session, no dependency on prior versions. Second in the precedence hierarchy. |
| SESSION_LEDGER.md | Living | Yes | One row per session — what was built, learned, the lessons. |
| DATA_DICTIONARY.md | Living | Yes | Cumulative schema, config, and function reference — current state, never history. Diff-edited. |
| CODEBASE_MAP.md | Living | No — reference-on-demand only | File inventory, call chains, the config-injection non-negotiable rule. |
| SESSION_LEDGER_ARCHIVE.md | Historical | No — reference-on-demand only | Verbatim old session rows, no ceiling. |
| CHANGELOG_ARCHIVE.md | Historical | No — reference-on-demand only | Verbatim old changelog entries, no ceiling. |
| FORWARD_QUEUE_ARCHIVE.md | Historical | No — reference-on-demand only | Verbatim fully-resolved open questions and shipped backlog items, no ceiling. |
| Day N Handover | Historical, Git-only | N/A | Not in Project Knowledge — pasted directly in chat each close since Claude cannot reach Git. Max 40 lines. |

---

## 10. Honest Constraints (carried forward, unchanged)

Paper trading until graduation criteria are met on real forward data — however long that takes. Holdings data is local-only, gitignored, never captured into fixtures or commits. HDB shortlists; it does not decide — every flat gets manual verification before any real-world action, and every regulatory figure is indicative pending HFE confirmation. Nothing from the bank's environment touches personal projects.

---

## 11. Governance Thread (parallel, ongoing)

One sub-hour reading session per week: Model Risk Management basics, audit trails as governance artifacts, explainability for compliance, data governance/DLP awareness. Output: a one-page AI governance crib sheet, no day attached.

---

## 12. Document Governance

Locked Day 25, following a real data-loss incident where this document and DATA_DICTIONARY both contained "unchanged from prior version" pointers to content in files about to be deleted. Full detail of the incident and reasoning lives in the Day 25 Summary (Git).

### a. Complete File Registry

See §9 above for the full table (document class, session-start read status, role). This subsection restates write-mode and ceiling behavior specifically:

| File | Write mode | Ceiling behavior |
|---|---|---|
| Master_Plan.md | Diff-only — exact edits given, never rewritten wholesale | Stable reference content; touched rarely |
| Forward_Queue.md | Full regeneration each close | Approaching ceiling = signal to resolve outstanding items, not to shrink or archive prematurely |
| SESSION_LEDGER.md | Full regeneration each close (new row added) | Same — ceiling pressure means close sessions out faster, not compress history |
| DATA_DICTIONARY.md | Diff-only — exact edits given, never rewritten wholesale | Should rarely approach ceiling now that it's diff-only |
| Day N Summary.md | New file each session, no dependency on prior versions | 80 lines — genuinely new content each time |
| CODEBASE_MAP.md | Refreshed at dedicated review sessions or after major refactors | N/A |
| SESSION_LEDGER_ARCHIVE.md | Appended verbatim, only when a row is genuinely historical | None — permanent record |
| CHANGELOG_ARCHIVE.md | Appended verbatim, only when a changelog entry is genuinely closed | None — permanent record |
| FORWARD_QUEUE_ARCHIVE.md | Appended verbatim, only when an open question is fully resolved or a backlog item ships | None — permanent record |
| Day N Handover | Fresh each session, pasted directly in conversation | 40 lines |

### b. Governing Principles

1. **Write clearly and without padding — length follows the content, not a target.** Every fact stays, explained as fully as it needs to be understood, never restated redundantly elsewhere in the same document. No word-count discipline, no forced brevity.
2. **Ceilings are a health signal, not a shrink-to-fit trigger.** Approaching one means slow down and resolve outstanding items for real. Archiving only happens to content that's genuinely done — never as pressure relief for content still active. Compression-for-space and silent summarization are banned outright.

### c. Archiving Criteria (added Day 25)

Different content types archive on different tests — none of them are age-based alone:

- **SESSION_LEDGER_ARCHIVE:** a row archives when (a) it is not referenced by any currently-open Forward_Queue.md item or open question, AND (b) it is not one of the most recent ~10 sessions (a rough continuity buffer, not a rule). Condition (a) overrides (b) — an old row still cited by an open item stays active regardless of age.
- **FORWARD_QUEUE_ARCHIVE:** purely resolution-based, no age component. An open question or backlog item archives only when genuinely and fully resolved — "partially resolved" stays active.
- **CHANGELOG_ARCHIVE:** an entry archives when its substantive content is already fully reflected in a current active document (this document, Forward_Queue.md, or DATA_DICTIONARY.md). Test: does reading only current docs plus the most recent 1-2 changelog entries give complete understanding of why the system is the way it is? If yes, older entries are provenance trivia, not needed context. Applied Day 25 — the entire pre-restructure changelog (v1.0–v1.5) qualified and was archived; nothing in it was unique.

### d. CODEBASE_MAP Refresh Triggers

CODEBASE_MAP.md is refreshed only when a trigger fires (full list lives in CODEBASE_MAP.md §9, not duplicated here to avoid two sources of truth on the same list). At every session close, explicitly check whether this session's work matches a trigger and call it out — do not assume it wasn't touched, and do not silently refresh without naming why. Day 25 fired two triggers (config structure shape change, function call chain change) and was called out explicitly rather than skipped or assumed.

### e. Session Close — Step-by-Step

1. Determine what actually changed this session — new session row, schema/config deltas, forward queue movement, any genuinely stagnant-section edits.
2. SESSION_LEDGER.md — add new row, full regeneration. Only move a row to SESSION_LEDGER_ARCHIVE.md if it's genuinely historical, never to relieve ceiling pressure.
3. Day N Summary — new file, full write, check against 80-line ceiling.
4. DATA_DICTIONARY.md — diff only. Identify exact changed rows/sections, give precise edit instructions to apply directly. Never rewritten wholesale.
5. Forward_Queue.md — full regeneration: Forward Queue, Backlog/Open Questions, Change Log. Only fully-resolved OQs and shipped/closed backlog items move to FORWARD_QUEUE_ARCHIVE.md; only genuinely closed changelog entries move to CHANGELOG_ARCHIVE.md.
6. Master_Plan.md — diff only, touched rarely (only when this document's content genuinely changes).
7. Day N Handover — Git-only, pasted in chat, max 40 lines, JSON state block at top.
8. Self-check before presenting anything — read every file about to be presented, search for "unchanged," "see prior version," "(compressed)," or any phrase pointing at content in a file being deleted/replaced. If found, fix before presenting — that's data loss, not brevity.
9. Revert session-only test edits — confirm config.py or other working files are back to real defaults before anything is committed.
10. Present files, remind about Git commit — confirm PK uploads, remind to commit code and paste the Handover into Git.
