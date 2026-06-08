# database.py
# All database operations for the stock monitor.
# Nine tables total: seven from Day 8 (with schema upgrades),
# plus persona_calls (Day 9) and balance_ledger (cost tracking).
# All schema changes happen here — never in the pipeline scripts.
#
# Schema versioning approach: get the schema right upfront with
# all confirmed decisions baked in. Avoids ALTER TABLE migrations
# across the rest of Phase 2-3.

import sqlite3
from datetime import datetime
import config


# ─────────────────────────────────────────────────────────────
# TABLE DEFINITIONS
# Order matters for readability, not for SQLite — IF NOT EXISTS
# means create-only-if-missing. Listed roughly by lifecycle:
# reference data → raw data → derived data → audit → cost
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
CREATE_PRICES_TABLE = """
CREATE TABLE IF NOT EXISTS prices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    instrument_type  TEXT,
    price            REAL,
    prev_close       REAL,
    pct_change       REAL
)
"""

# Raw Claude outputs — one row per persona or translator call per run
# analysis_type values:
#   Personas: bull, bear, black_swan, pragmatist, contrarian, meta_agent
#   Translator: translator_[section_name]
CREATE_ANALYSIS_TABLE = """
CREATE TABLE IF NOT EXISTS analysis (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    analysis_type    TEXT NOT NULL,
    source           TEXT NOT NULL,
    output           TEXT NOT NULL
)
"""

# Derived signals — one row per flagged condition per run
# triggered = 1 means the condition fired
# triggered = 0 means evaluated but not triggered — stored for near-miss queries
# entity_a / relationship / entity_b are graph edge candidates for Day 30+
# persona tracks which analyst raised the signal
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
# total_cost_usd is the sum of all llm_calls.cost_usd for this run
CREATE_RUN_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS run_log (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                      TEXT NOT NULL UNIQUE,
    started_at                  TEXT NOT NULL,
    completed_at                TEXT,
    status                      TEXT NOT NULL DEFAULT 'running',
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
# cost_usd is computed at insert from config.MODEL_PRICING — not at query time
# Captured per call so per-persona and per-model cost analysis is trivial
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
    error_message   TEXT
)
"""

# Discrete analytical sentences — RAG source from Day 20
# Parsed from analysis output at write time, not at query time
# persona tracks which analyst produced the sentence
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
# outcome starts NULL and gets filled at T+3 sessions or on a 5%+ price move
# regime_tag derived from VIX at run time: low_vix/normal/high_vix/crisis
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
# Anthropic's official Usage API requires Team/Enterprise plan — not available
# on Mack's individual account. This local approach uses MODEL_PRICING in
# config.py plus cost_usd on each llm_calls row, reconciled against actual
# billing periodically.
# entry_type: topup, reconcile, adjustment
# amount_usd: positive for topup, can be negative for adjustment
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


# ─────────────────────────────────────────────────────────────
# CONNECTION
# ─────────────────────────────────────────────────────────────

def get_connection():
    """
    Opens a SQLite connection with row_factory set.
    row_factory = sqlite3.Row lets you access columns by name
    instead of index — row["ticker"] instead of row[2].
    The database file is created automatically if it does not exist.
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

        # Reference & raw data
        cursor.execute(CREATE_MODELS_TABLE)
        cursor.execute(CREATE_PRICES_TABLE)
        cursor.execute(CREATE_ANALYSIS_TABLE)

        # Derived data
        cursor.execute(CREATE_SIGNALS_TABLE)
        cursor.execute(CREATE_PERSONA_CALLS_TABLE)
        cursor.execute(CREATE_SENTENCES_TABLE)

        # Audit & cost
        cursor.execute(CREATE_RUN_LOG_TABLE)
        cursor.execute(CREATE_LLM_CALLS_TABLE)
        cursor.execute(CREATE_BALANCE_LEDGER_TABLE)

        # Seed known models — INSERT OR IGNORE means safe to re-run
        known_models = [
            ("claude-sonnet-4-6",          "sonnet-4-6",  "anthropic", "sonnet"),
            ("claude-haiku-4-5-20251001",  "haiku-4-5",   "anthropic", "haiku"),
            ("claude-opus-4-8",            "opus-4-8",    "anthropic", "opus"),
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
    Generate once at the start of each run and pass to all write functions.
    """
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")


# ─────────────────────────────────────────────────────────────
# COST HELPER
# ─────────────────────────────────────────────────────────────

def compute_call_cost(model_used, input_tokens, output_tokens):
    """
    Computes the USD cost of a single LLM call from config.MODEL_PRICING.
    Returns 0.0 for unknown models — never crashes the pipeline.
    Pricing is per million tokens, so we divide by 1,000,000.
    Called by write_llm_call() at insert time so cost is stored
    permanently with the row — no recomputation needed later.
    """
    pricing = config.MODEL_PRICING.get(model_used)
    if pricing is None:
        # Unknown model — log a warning but don't crash
        # This protects against typos in model_used and new models
        # not yet added to MODEL_PRICING
        print(f"[DB] WARNING: no pricing for model '{model_used}' — cost set to 0")
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)  # 6 dp — sub-cent precision matters at scale


# ─────────────────────────────────────────────────────────────
# WRITE FUNCTIONS
# All writes use the context manager pattern:
#   with get_connection() as conn
# This guarantees commit on success and rollback on failure.
# Every write function re-raises exceptions so the pipeline
# knows a write failed and can record it in run_log.
# ─────────────────────────────────────────────────────────────

def start_run(run_id):
    """
    Opens the run_log entry when a pipeline run begins.
    Status 'running' — updated by finish_run() at the end.
    If the pipeline crashes before finish_run(), status stays
    'running' permanently — a detectable failure mode on Day 26.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO run_log (run_id, started_at, status)
                VALUES (?, ?, 'running')
                """,
                (run_id, datetime.now().isoformat()),
            )
        print(f"[DB] Run started: {run_id}")
    except Exception as e:
        print(f"[DB] start_run failed: {e}")
        raise


def finish_run(run_id, status="complete", stats=None):
    """
    Closes the run_log entry when the pipeline finishes.
    stats is an optional dict of token counts, durations, error counts,
    and total_cost_usd. Pass None if not yet tracking those fields.
    """
    try:
        with get_connection() as conn:
            if stats:
                conn.execute(
                    """
                    UPDATE run_log SET
                        completed_at                = ?,
                        status                      = ?,
                        tickers_attempted           = ?,
                        tickers_succeeded           = ?,
                        tickers_failed              = ?,
                        analyst_input_tokens        = ?,
                        analyst_output_tokens       = ?,
                        translator_input_tokens     = ?,
                        translator_output_tokens    = ?,
                        analyst_duration_secs       = ?,
                        translator_duration_secs    = ?,
                        fallback_used               = ?,
                        error_count                 = ?,
                        total_cost_usd              = ?
                    WHERE run_id = ?
                    """,
                    (
                        datetime.now().isoformat(),
                        status,
                        stats.get("tickers_attempted", 0),
                        stats.get("tickers_succeeded", 0),
                        stats.get("tickers_failed", 0),
                        stats.get("analyst_input_tokens", 0),
                        stats.get("analyst_output_tokens", 0),
                        stats.get("translator_input_tokens", 0),
                        stats.get("translator_output_tokens", 0),
                        stats.get("analyst_duration_secs"),
                        stats.get("translator_duration_secs"),
                        stats.get("fallback_used", 0),
                        stats.get("error_count", 0),
                        stats.get("total_cost_usd", 0),
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


def write_prices(run_id, price_data):
    """
    Writes one row per ticker into the prices table.
    price_data is the list of dicts built by the fetch pipeline.
    Each dict needs: ticker, instrument_type, price, prev_close, pct_change.
    Skips tickers where price is None — failed fetches not stored.
    All rows for a run write in one transaction — partial writes roll back.
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
                         price, prev_close, pct_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        timestamp,
                        row["ticker"],
                        row.get("instrument_type"),
                        row["price"],
                        row["prev_close"],
                        row["pct_change"],
                    ),
                )
                rows_written += 1
        print(f"[DB] Prices written: {rows_written} rows for run {run_id}")
    except Exception as e:
        print(f"[DB] write_prices failed, rolled back: {e}")
        raise


def write_analysis(run_id, output_text, analysis_type, source="stock_monitor"):
    """
    Writes one row into the analysis table per persona or translator call.
    analysis_type identifies the source — bull, bear, black_swan, pragmatist,
    contrarian, meta_agent, or translator_[section].
    Returns the inserted row id — needed by write_sentences() to link back.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis
                    (run_id, timestamp, analysis_type, source, output)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    datetime.now().isoformat(),
                    analysis_type,
                    source,
                    output_text,
                ),
            )
            row_id = cursor.lastrowid
        print(f"[DB] Analysis written: {analysis_type} for run {run_id}")
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
    outcome / resolved_by_run_id / human_override start NULL and are filled
    by the scoring pass at T+3 sessions or on a 5%+ move.
    Called by threshold logic on Day 10. Read by the agent on Day 21.
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
    Called once per persona per ticker per run from stock_monitor.py.
    outcome and resolved_by_run_id start NULL and are filled by the
    scoring pass at T+3 sessions or on a 5%+ move.
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
                   duration_secs, status="success", error_message=None):
    """
    Writes one audit row per call_llm() invocation.
    cost_usd is computed here from config.MODEL_PRICING and stored
    permanently — no recomputation at query time.
    model_requested vs model_used captures fallback events.
    On Day 26 this table becomes the primary observability source.
    """
    try:
        # Compute cost at insert time — locks in pricing as of this run
        # If pricing changes later, historical cost data is still accurate
        cost_usd = compute_call_cost(model_used, input_tokens, output_tokens)

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_calls
                    (run_id, timestamp, call_type, model_requested, model_used,
                     fallback_used, input_tokens, output_tokens, duration_secs,
                     cost_usd, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, datetime.now().isoformat(), call_type,
                    model_requested, model_used, int(fallback_used),
                    input_tokens, output_tokens, duration_secs,
                    cost_usd, status, error_message,
                ),
            )
    except Exception as e:
        print(f"[DB] write_llm_call failed, rolled back: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# READ FUNCTIONS
# Existing reads kept intact. balance_ledger reads deferred until
# reconciliation logic is built — table exists, no read function yet.
# ─────────────────────────────────────────────────────────────

def read_recent_prices(ticker, limit=5):
    """
    Returns the most recent N price rows for a given ticker.
    Used to verify storage after first run.
    On Day 10 becomes the basis for threshold alert comparisons.
    Returns list of Row objects — access by column name: row["price"]
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT run_id, timestamp, price, pct_change
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
                SELECT run_id, started_at, completed_at, status,
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