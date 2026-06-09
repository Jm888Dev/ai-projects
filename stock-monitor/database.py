# database.py
# All database operations for the stock monitor.
# Ten tables total — prices, market_history, analysis, signals,
# run_log, llm_calls, sentences, persona_calls, balance_ledger,
# model_registry.
#
# Schema versioning approach: get the schema right upfront with
# all confirmed decisions baked in. Avoids ALTER TABLE migrations
# across the rest of Phase 2-3.
#
# Table lifecycle order:
#   Reference data  → models
#   Raw data        → prices, market_history
#   Derived data    → analysis, signals, persona_calls, sentences
#   Audit           → run_log, llm_calls
#   Cost tracking   → balance_ledger

import sqlite3
from datetime import datetime
import config


# ─────────────────────────────────────────────────────────────
# TABLE DEFINITIONS
# ─────────────────────────────────────────────────────────────

# Models lookup — normalised model registry
# Prevents stale model name strings across runs
# tier values: sonnet, haiku, opus, slm
CREATE_MODELS_TABLE = """
CREATE TABLE IF NOT EXISTS models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id    TEXT NOT NULL UNIQUE,
    alias       TEXT,
    provider    TEXT DEFAULT 'anthropic',
    tier        TEXT
)
"""

# Raw price data — one row per ticker per run
# Purpose: audit trail of exactly what each agent saw at moment of reasoning
# Separate from market_history which is the canonical daily close record
# capture_context: market state at moment of capture
#   values: market_open_normal, market_open_high_volatility,
#           market_closed_after_hours, market_closed_weekend,
#           market_closed_holiday, sgx_closed_us_open, legacy_pre_day9
# intraday_position: 0.0 = at day low, 1.0 = at day high, NULL if closed
# reconciliation: filled next session after market_history has official close
#   values: close_matched, intraday_capture, data_revised,
#           unresolved, not_applicable
CREATE_PRICES_TABLE = """
CREATE TABLE IF NOT EXISTS prices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    instrument_type     TEXT,
    price               REAL,
    prev_close          REAL,
    pct_change          REAL,
    capture_context     TEXT DEFAULT 'unclassified',
    intraday_position   REAL,
    reconciliation      TEXT DEFAULT 'unresolved'
)
"""

# Daily market history — canonical OHLCV record per ticker per trading day
# Purpose: trajectory analysis, moving averages, correlations, volatility
# Separate from prices — this is market truth, prices is agent context
# delta_pull: True means this row was added by a delta pull (not backfill)
# source: yfinance (live), fixture (testing)
# Unique constraint on date+ticker prevents duplicate rows on re-run
CREATE_MARKET_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS market_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          INTEGER,
    pct_change      REAL,
    source          TEXT DEFAULT 'yfinance',
    inserted_at     TEXT NOT NULL,
    UNIQUE(ticker, trade_date)
)
"""

# Raw Claude outputs — one row per persona or translator call per run
# analysis_type values:
#   Stage 1: bull, bear, black_swan, pragmatist
#   Stage 2: contrarian
#   Stage 3: meta_agent
#   Translator: translator_[section_name]
# ticker is NULL for portfolio-level calls (contrarian, meta_agent, translator)
CREATE_ANALYSIS_TABLE = """
CREATE TABLE IF NOT EXISTS analysis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    analysis_type   TEXT NOT NULL,
    ticker          TEXT,
    source          TEXT NOT NULL,
    output          TEXT NOT NULL,
    truncated       INTEGER DEFAULT 0
)
"""

# Derived signals — one row per flagged condition per run
# triggered = 1 means the condition fired
# triggered = 0 means evaluated but not triggered — stored for near-miss queries
# entity_a / relationship / entity_b are graph edge candidates for Day 45+
# persona tracks which analyst raised the signal
# signal_type values include: threshold_alert, kill_trigger, meta_decision,
#   divergence, consensus, premortem, persistent_divergence
# outcome / resolved_by_run_id / human_override scored at T+3 or on 5%+ move
# divergence_score: 1 = magnitude only, 2-3 = directional disagreement
CREATE_SIGNALS_TABLE = """
CREATE TABLE IF NOT EXISTS signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    signal_type         TEXT NOT NULL,
    value               REAL,
    threshold           REAL,
    triggered           INTEGER NOT NULL DEFAULT 0,
    direction           TEXT,
    persona             TEXT,
    entity_a            TEXT,
    relationship        TEXT,
    entity_b            TEXT,
    notes               TEXT,
    outcome             TEXT,
    resolved_by_run_id  TEXT,
    human_override      INTEGER DEFAULT 0,
    divergence_score    INTEGER
)
"""

# Pipeline health — one row per run
# status stays 'running' if pipeline crashes — detectable failure on Day 26
# data_mode: live or fixture — filters out development runs from eval metrics
# total_cost_usd is the sum of all llm_calls.cost_usd for this run
CREATE_RUN_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS run_log (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                      TEXT NOT NULL UNIQUE,
    started_at                  TEXT NOT NULL,
    completed_at                TEXT,
    status                      TEXT NOT NULL DEFAULT 'running',
    data_mode                   TEXT NOT NULL DEFAULT 'fixture',
    tickers_attempted           INTEGER DEFAULT 0,
    tickers_succeeded           INTEGER DEFAULT 0,
    tickers_failed              INTEGER DEFAULT 0,
    analyst_input_tokens        INTEGER DEFAULT 0,
    analyst_output_tokens       INTEGER DEFAULT 0,
    translator_input_tokens     INTEGER DEFAULT 0,
    translator_output_tokens    INTEGER DEFAULT 0,
    analyst_duration_secs       REAL,
    translator_duration_secs    REAL,
    fallback_used               INTEGER DEFAULT 0,
    error_count                 INTEGER DEFAULT 0,
    total_cost_usd              REAL DEFAULT 0,
    notes                       TEXT
)
"""

# Full LLM audit trail — one row per call_llm() invocation
# model_requested vs model_used captures fallback events
# cost_usd computed at insert from config.MODEL_PRICING — not at query time
# call_type identifies the stage and persona:
#   stage1_bull, stage1_bear, stage1_black_swan, stage1_pragmatist,
#   stage2_contrarian, stage3_meta_agent, translator
CREATE_LLM_CALLS_TABLE = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    call_type       TEXT NOT NULL,
    model_requested TEXT NOT NULL,
    model_used      TEXT,
    fallback_used   INTEGER DEFAULT 0,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    duration_secs   REAL,
    cost_usd        REAL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'success',
    error_message   TEXT,
    retried         INTEGER DEFAULT 0,
    truncated       INTEGER DEFAULT 0,
    retry_budget    INTEGER
)
"""

# Discrete analytical sentences — RAG source from Day 20
# Parsed from analysis output at write time, not at query time
# sentence_type and sentiment classified by Haiku call on Day 15
CREATE_SENTENCES_TABLE = """
CREATE TABLE IF NOT EXISTS sentences (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    source_table        TEXT NOT NULL,
    source_id           INTEGER NOT NULL,
    analysis_type       TEXT NOT NULL,
    persona             TEXT,
    section             TEXT NOT NULL,
    sentence            TEXT NOT NULL,
    tickers_mentioned   TEXT,
    sentence_type       TEXT,
    sentiment           TEXT
)
"""

# Persona calls — the voting ledger
# One row per persona per ticker per run
# Meta-Agent does NOT get a persona_calls row — it renders decisions,
# not directional bets. Only Stage 1 agents and Contrarian are scored.
# outcome starts NULL — filled at T+3 sessions or on 5%+ price move
# regime_tag derived from VIX at run time
# direction values: ACCUMULATE / HOLD / REDUCE / EXIT
# confidence_score: 0-100, Claude's self-estimated conviction
CREATE_PERSONA_CALLS_TABLE = """
CREATE TABLE IF NOT EXISTS persona_calls (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL,
    persona             TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    direction           TEXT,
    confidence_score    INTEGER,
    regime_tag          TEXT,
    vix_level           REAL,
    rationale_summary   TEXT,
    outcome             TEXT,
    resolved_by_run_id  TEXT
)
"""

# Balance ledger — manual cost tracking for the Anthropic API account
# Anthropic's official Usage API requires Team/Enterprise plan —
# not available on individual API accounts.
# Local approach: compute cost from MODEL_PRICING at each llm_calls insert,
# accumulate per run, reconcile against actual billing periodically.
# entry_type values: topup, reconcile, adjustment
# amount_usd: positive for topup, negative for adjustment
# balance_after_usd: your best estimate of remaining credit after this entry
CREATE_BALANCE_LEDGER_TABLE = """
CREATE TABLE IF NOT EXISTS balance_ledger (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT NOT NULL,
    entry_type          TEXT NOT NULL,
    amount_usd          REAL NOT NULL,
    balance_after_usd   REAL,
    notes               TEXT
)
"""

# AI-generated proposed thesis updates awaiting human review
# status values: pending / approved / rejected / modified
# trigger_signal: the signal that prompted this draft (e.g. 'portfolio_relationship_alert')
# trigger_source: what detected the change (e.g. 'correlation_check', 'feed_match', 'human')
# confidence: 1-5, how strongly the AI believes this update is warranted
CREATE_THESIS_DRAFTS_TABLE = """
CREATE TABLE IF NOT EXISTS thesis_drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    section         TEXT NOT NULL,
    current_text    TEXT,
    proposed_text   TEXT NOT NULL,
    confidence      INTEGER,
    trigger_signal  TEXT,
    trigger_source  TEXT,
    rationale       TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
)
"""

# Human decisions on thesis drafts — the review ledger
# action values: approved / rejected / modified
# modified_text: only populated when action = 'modified' — the human's version
# reason: why the human accepted, rejected, or changed the draft
# reviewer: who reviewed (defaults to 'human' — future: could be a persona name)
# source: ai_draft (system-generated) or human_initiated (manually triggered)
CREATE_THESIS_REVIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS thesis_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    draft_id        INTEGER NOT NULL,
    ticker          TEXT NOT NULL,
    section         TEXT NOT NULL,
    action          TEXT NOT NULL,
    modified_text   TEXT,
    reason          TEXT,
    reviewer        TEXT DEFAULT 'human',
    source          TEXT DEFAULT 'ai_draft'
)
"""

# ─────────────────────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────────────────────

def get_connection():
    """
    Opens a SQLite connection with row_factory set.
    row_factory = sqlite3.Row lets you access columns by name
    instead of index — row["ticker"] instead of row[2].
    The database file is created automatically if it does not exist.
    Used as a context manager throughout — guarantees commit on
    success and rollback on any exception.
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────
# INITIALISATION
# ─────────────────────────────────────────────────────────────

def initialise_db():
    """
    Creates all tables and seeds the models lookup on first run.
    Safe to call every run — IF NOT EXISTS prevents data loss.
    Call once at the start of stock_monitor.py before any writes.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Reference data
        cursor.execute(CREATE_MODELS_TABLE)

        # Raw data
        cursor.execute(CREATE_PRICES_TABLE)
        cursor.execute(CREATE_MARKET_HISTORY_TABLE)

        # Derived data
        cursor.execute(CREATE_ANALYSIS_TABLE)
        cursor.execute(CREATE_SIGNALS_TABLE)
        cursor.execute(CREATE_PERSONA_CALLS_TABLE)
        cursor.execute(CREATE_SENTENCES_TABLE)

        # Audit and cost
        cursor.execute(CREATE_RUN_LOG_TABLE)
        cursor.execute(CREATE_LLM_CALLS_TABLE)
        cursor.execute(CREATE_BALANCE_LEDGER_TABLE)

        # Thesis maintenance
        cursor.execute(CREATE_THESIS_DRAFTS_TABLE)
        cursor.execute(CREATE_THESIS_REVIEWS_TABLE)

        # Seed known models
        # INSERT OR IGNORE — safe to re-run, never overwrites existing rows
        known_models = [
            ("claude-haiku-4-5-20251001", "haiku-4-5",  "anthropic", "haiku"),
            ("claude-sonnet-4-6",         "sonnet-4-6", "anthropic", "sonnet"),
            ("claude-opus-4-8",           "opus-4-8",   "anthropic", "opus"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO models (model_id, alias, provider, tier)
            VALUES (?, ?, ?, ?)
            """,
            known_models,
        )

    print("[DB] All tables initialised.")


# ─────────────────────────────────────────────────────────────
# RUN ID
# ─────────────────────────────────────────────────────────────

def generate_run_id():
    """
    Generates a unique run identifier based on the current timestamp.
    Format: YYYY-MM-DD_HH:MM:SS — human readable and sortable.
    Generate once at the start of each run and pass to all write
    functions. Used as the JOIN key across all tables.
    """
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")


# ─────────────────────────────────────────────────────────────
# COST HELPERS
# ─────────────────────────────────────────────────────────────

def compute_call_cost(model_used, input_tokens, output_tokens):
    """
    Computes the USD cost of a single LLM call from config.MODEL_PRICING.
    Returns 0.0 for unknown models — never crashes the pipeline.
    Pricing is per million tokens so we divide by 1,000,000.
    Called by write_llm_call() at insert time so cost is stored
    permanently — historical cost data stays accurate even if
    pricing changes later.
    """
    if model_used and model_used.startswith("fixture:"):
        # Fixture calls have no API cost by design — zero is correct, not a warning
        return 0.0

    pricing = config.MODEL_PRICING.get(model_used)
    if pricing is None:
        # Unknown model — cost cannot be computed and will be missing from run summary
        # Action: add this model to MODEL_PRICING in config.py
        # Format: "model-name": {"input": X.XX, "output": X.XX} per million tokens
        print(f"[DB] WARNING: no pricing found for model '{model_used}' "
              f"— cost recorded as $0.00. "
              f"Fix: add '{model_used}' to MODEL_PRICING in config.py.")
        return 0.0

    input_cost  = (input_tokens  / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def get_estimated_balance():
    """
    Estimates remaining Anthropic API credit from local records.
    Formula: sum of all topups and adjustments in balance_ledger
             minus sum of all cost_usd in llm_calls.
    Returns a dict with total_spent, total_topped_up, estimated_remaining.
    Returns None if no balance_ledger entries exist yet — prompts the
    user to log their first topup before the estimate is meaningful.
    Note: this is an estimate. Reconcile against console.anthropic.com
    weekly by writing a 'reconcile' entry to balance_ledger.
    """
    try:
        with get_connection() as conn:
            # Sum all manual entries — topups are positive, adjustments can be negative
            topup_row = conn.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) AS total FROM balance_ledger"
            ).fetchone()

            # Sum all computed costs across every LLM call ever made
            spent_row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM llm_calls"
            ).fetchone()

            # Check whether any balance entries exist
            entry_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM balance_ledger"
            ).fetchone()

            if entry_count["cnt"] == 0:
                return None  # No topup logged yet — estimate not meaningful

            total_topped_up = round(topup_row["total"], 4)
            total_spent     = round(spent_row["total"], 4)
            estimated_remaining = round(total_topped_up - total_spent, 4)

            return {
                "total_topped_up":       total_topped_up,
                "total_spent":           total_spent,
                "estimated_remaining":   estimated_remaining,
            }
    except Exception as e:
        print(f"[DB] get_estimated_balance failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# MARKET HISTORY — WRITE AND UPDATE
# ─────────────────────────────────────────────────────────────

def get_latest_market_history_date(ticker):
    """
    Returns the most recent trade_date stored for a given ticker
    in market_history, or None if no rows exist yet.
    Used by update_market_history() to determine the delta start date.
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT MAX(trade_date) AS latest
                FROM market_history
                WHERE ticker = ?
                """,
                (ticker,),
            ).fetchone()
            return row["latest"]  # None if no rows exist
    except Exception as e:
        print(f"[DB] get_latest_market_history_date failed for {ticker}: {e}")
        return None


def write_market_history_rows(rows):
    """
    Writes a batch of OHLCV rows into market_history.
    rows is a list of dicts — each dict must contain:
        ticker, trade_date, open, high, low, close, volume,
        pct_change, source, inserted_at
    INSERT OR IGNORE on (ticker, trade_date) unique constraint
    means re-running is safe — no duplicate rows, no crashes.
    All rows write in one transaction — partial batch rolls back.
    """
    if not rows:
        return 0

    try:
        with get_connection() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO market_history
                    (ticker, trade_date, open, high, low, close,
                     volume, pct_change, source, inserted_at)
                VALUES
                    (:ticker, :trade_date, :open, :high, :low, :close,
                     :volume, :pct_change, :source, :inserted_at)
                """,
                rows,
            )
        return len(rows)
    except Exception as e:
        print(f"[DB] write_market_history_rows failed, rolled back: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# WRITE FUNCTIONS — PIPELINE DATA
# All writes use the context manager pattern:
#   with get_connection() as conn
# This guarantees commit on success and rollback on failure.
# Every write function re-raises exceptions so the pipeline
# knows a write failed and can update run_log accordingly.
# ─────────────────────────────────────────────────────────────

def start_run(run_id, data_mode="fixture"):
    """
    Opens the run_log entry when a pipeline run begins.
    data_mode: 'live' or 'fixture' — recorded so development runs
    can be filtered out of persona accuracy evaluation on Day 15.
    Status 'running' stays permanently if the pipeline crashes
    before finish_run() — a detectable failure mode on Day 26.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO run_log (run_id, started_at, status, data_mode)
                VALUES (?, ?, 'running', ?)
                """,
                (run_id, datetime.now().isoformat(), data_mode),
            )
        print(f"[DB] Run started: {run_id} — mode: {data_mode}")
    except Exception as e:
        print(f"[DB] start_run failed: {e}")
        raise


def finish_run(run_id, status="complete", stats=None):
    """
    Closes the run_log entry when the pipeline finishes.
    stats is an optional dict of token counts, durations, error counts,
    and total_cost_usd. Pass None if not tracking those fields yet.
    """
    try:
        with get_connection() as conn:
            if stats:
                conn.execute(
                    """
                    UPDATE run_log SET
                        completed_at             = ?,
                        status                   = ?,
                        tickers_attempted        = ?,
                        tickers_succeeded        = ?,
                        tickers_failed           = ?,
                        analyst_input_tokens     = ?,
                        analyst_output_tokens    = ?,
                        translator_input_tokens  = ?,
                        translator_output_tokens = ?,
                        analyst_duration_secs    = ?,
                        translator_duration_secs = ?,
                        fallback_used            = ?,
                        error_count              = ?,
                        total_cost_usd           = ?
                    WHERE run_id = ?
                    """,
                    (
                        datetime.now().isoformat(),
                        status,
                        stats.get("tickers_attempted",        0),
                        stats.get("tickers_succeeded",        0),
                        stats.get("tickers_failed",           0),
                        stats.get("analyst_input_tokens",     0),
                        stats.get("analyst_output_tokens",    0),
                        stats.get("translator_input_tokens",  0),
                        stats.get("translator_output_tokens", 0),
                        stats.get("analyst_duration_secs"),
                        stats.get("translator_duration_secs"),
                        stats.get("fallback_used",            0),
                        stats.get("error_count",              0),
                        stats.get("total_cost_usd",           0),
                        run_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE run_log SET completed_at = ?, status = ?
                    WHERE run_id = ?
                    """,
                    (datetime.now().isoformat(), status, run_id),
                )
        print(f"[DB] Run finished: {run_id} — {status}")
    except Exception as e:
        print(f"[DB] finish_run failed: {e}")
        raise


def write_prices(run_id, price_data, capture_context="unclassified"):
    """
    Writes one row per ticker into the prices table.
    price_data is a list of dicts from the fetch pipeline.
    Each dict needs: ticker, instrument_type, price, prev_close, pct_change.
    capture_context is set by determine_capture_context() in the pipeline
    before this is called — tells the reader what market state this
    price represents (open, closed, high-volatility, etc).
    intraday_position and reconciliation default to NULL / 'unresolved'
    at write time. reconciliation is filled next session by reconcile_prices().
    Skips tickers where price is None — failed fetches not stored.
    """
    try:
        with get_connection() as conn:
            timestamp = datetime.now().isoformat()
            rows_written = 0
            for row in price_data:
                if row.get("price") is None:
                    continue
                conn.execute(
                    """
                    INSERT INTO prices
                        (run_id, timestamp, ticker, instrument_type,
                         price, prev_close, pct_change, capture_context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        timestamp,
                        row["ticker"],
                        row.get("instrument_type"),
                        row["price"],
                        row.get("prev_close"),
                        row.get("pct_change"),
                        capture_context,
                    ),
                )
                rows_written += 1
        print(f"[DB] Prices written: {rows_written} rows for run {run_id}")
    except Exception as e:
        print(f"[DB] write_prices failed, rolled back: {e}")
        raise


def write_analysis(run_id, output_text, analysis_type,
                   ticker=None, source="stock_monitor", truncated=False):
    """
    Writes one row into the analysis table per persona or translator call.
    analysis_type identifies the source:
        Stage 1: bull, bear, black_swan, pragmatist
        Stage 2: contrarian
        Stage 3: meta_agent
        Translator: translator_[section]
    ticker is None for portfolio-level calls (contrarian, meta_agent,
    translator) and set for per-ticker Stage 1 and Stage 2 calls.
    truncated=True flags that output was cut at token limit — signal
    is still stored and passed forward, downstream agents are aware
    via the TRUNCATION_FLAG appended to the text by call_llm().
    Returns the inserted row id — needed by write_sentences() to link back.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis
                    (run_id, timestamp, analysis_type, ticker,
                     source, output, truncated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    datetime.now().isoformat(),
                    analysis_type,
                    ticker,
                    source,
                    output_text,
                    int(truncated),
                ),
            )
            row_id = cursor.lastrowid
        print(f"[DB] Analysis written: {analysis_type}"
              + (f" [{ticker}]" if ticker else " [portfolio]")
              + (f" [TRUNCATED]" if truncated else "")
              + f" for run {run_id}")
        return row_id
    except Exception as e:
        print(f"[DB] write_analysis failed, rolled back: {e}")
        raise


def write_signal(run_id, ticker, signal_type, value=None, threshold=None,
                 triggered=0, direction=None, persona=None,
                 entity_a=None, relationship=None, entity_b=None,
                 notes=None, divergence_score=None):
    """
    Writes one signal row per evaluated condition.
    triggered=1 means the threshold fired.
    triggered=0 means evaluated but not triggered — stored for near-miss queries.
    entity_a / relationship / entity_b are graph edge candidates for Day 45+.
    outcome / resolved_by_run_id / human_override start NULL and are filled
    by the T+3 scoring pass or on a 5%+ move — built on Day 10.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO signals
                    (run_id, timestamp, ticker, signal_type, value, threshold,
                     triggered, direction, persona, entity_a, relationship,
                     entity_b, notes, divergence_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, datetime.now().isoformat(), ticker, signal_type,
                    value, threshold, triggered, direction, persona,
                    entity_a, relationship, entity_b, notes, divergence_score,
                ),
            )
    except Exception as e:
        print(f"[DB] write_signal failed, rolled back: {e}")
        raise


def write_persona_call(run_id, persona, ticker, direction=None,
                       confidence_score=None, regime_tag=None,
                       vix_level=None, rationale_summary=None):
    """
    Writes one row to the persona_calls voting ledger.
    Called once per persona per ticker per run.
    Meta-Agent does NOT get a persona_calls row — it renders decisions,
    not directional bets. Only Stage 1 agents and Contrarian are scored.
    outcome and resolved_by_run_id start NULL — filled at T+3 sessions
    or on a 5%+ move by the scoring pass built on Day 10.
    direction values: ACCUMULATE / HOLD / REDUCE / EXIT
    regime_tag values: low_vix / normal / high_vix / crisis
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO persona_calls
                    (run_id, persona, ticker, direction, confidence_score,
                     regime_tag, vix_level, rationale_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, persona, ticker, direction, confidence_score,
                    regime_tag, vix_level, rationale_summary,
                ),
            )
    except Exception as e:
        print(f"[DB] write_persona_call failed, rolled back: {e}")
        raise


def write_llm_call(run_id, call_type, model_requested, model_used,
                   fallback_used, input_tokens, output_tokens,
                   duration_secs, status="success", error_message=None,
                   retried=False, truncated=False, retry_budget=None):
    """
    Writes one audit row per call_llm() invocation.
    cost_usd computed at insert from config.MODEL_PRICING — stored
    permanently so historical cost data stays accurate even if
    pricing changes later.
    retried: 1 if a retry was triggered due to truncation.
    truncated: 1 if output was still truncated after retry —
               signal is passed through with TRUNCATION_FLAG appended.
    retry_budget: token budget used on retry, NULL if no retry.
    """
    try:
        cost_usd = compute_call_cost(model_used, input_tokens, output_tokens)

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_calls
                    (run_id, timestamp, call_type, model_requested, model_used,
                     fallback_used, input_tokens, output_tokens, duration_secs,
                     cost_usd, status, error_message,
                     retried, truncated, retry_budget)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, datetime.now().isoformat(), call_type,
                    model_requested, model_used, int(fallback_used),
                    input_tokens, output_tokens, duration_secs,
                    cost_usd, status, error_message,
                    int(retried), int(truncated), retry_budget,
                ),
            )
    except Exception as e:
        print(f"[DB] write_llm_call failed, rolled back: {e}")
        raise


def log_balance_topup(amount_usd, notes=None):
    """
    Records a manual credit topup to your Anthropic API account.
    Call this whenever you add credit at console.anthropic.com.
    balance_after_usd is computed from prior entries + this topup.
    Example: log_balance_topup(20.00, "June topup")
    """
    try:
        with get_connection() as conn:
            # Get current estimated balance to compute balance_after
            current = get_estimated_balance()
            current_balance = current["estimated_remaining"] if current else 0.0
            balance_after = round(current_balance + amount_usd, 4)

            conn.execute(
                """
                INSERT INTO balance_ledger
                    (timestamp, entry_type, amount_usd, balance_after_usd, notes)
                VALUES (?, 'topup', ?, ?, ?)
                """,
                (datetime.now().isoformat(), amount_usd, balance_after, notes),
            )
        print(f"[DB] Balance topup logged: ${amount_usd:.2f} — "
              f"estimated remaining: ${balance_after:.2f}")
    except Exception as e:
        print(f"[DB] log_balance_topup failed: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# READ FUNCTIONS
# ─────────────────────────────────────────────────────────────

def read_recent_prices(ticker, limit=5):
    """
    Returns the most recent N price rows for a given ticker.
    Used to verify storage and on Day 10 for threshold comparisons.
    Returns list of Row objects — access by column name: row["price"]
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT run_id, timestamp, price, pct_change, capture_context
                FROM prices
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (ticker, limit),
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"[DB] read_recent_prices failed: {e}")
        return []


def read_market_history(ticker, limit=30):
    """
    Returns the most recent N daily rows from market_history for a ticker.
    Used by build_historical_context() in the data package builder.
    Default 30 days — enough for moving averages and correlations.
    Returns list of Row objects — access by column name: row["close"]
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT trade_date, open, high, low, close, volume, pct_change
                FROM market_history
                WHERE ticker = ?
                ORDER BY trade_date DESC
                LIMIT ?
                """,
                (ticker, limit),
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"[DB] read_market_history failed: {e}")
        return []


def read_recent_signals(triggered_only=True, limit=20):
    """
    Returns recent signal rows, optionally filtered to triggered only.
    On Day 21 the agent reads this to decide what to surface.
    Returns list of Row objects — access by column name: row["signal_type"]
    """
    try:
        with get_connection() as conn:
            where = "WHERE triggered = 1" if triggered_only else ""
            cursor = conn.execute(
                f"""
                SELECT run_id, ticker, signal_type, persona, notes
                FROM signals
                {where}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"[DB] read_recent_signals failed: {e}")
        return []


def read_run_history(limit=10):
    """
    Returns the most recent N run_log entries with cost data.
    Used for Day 26 observability dashboard.
    Returns list of Row objects with full run health data.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT run_id, started_at, completed_at, status, data_mode,
                       tickers_succeeded, tickers_failed,
                       analyst_input_tokens, translator_input_tokens,
                       fallback_used, error_count, total_cost_usd
                FROM run_log
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"[DB] read_run_history failed: {e}")
        return []