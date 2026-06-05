# database.py
# Handles all database operations for the stock monitor.
# Six tables covering raw data, derived signals, audit trail,
# and RAG-ready sentence storage. One models lookup table.
# All schema changes happen here — never in the pipeline scripts.

import sqlite3
from datetime import datetime
import config


# --- TABLE DEFINITIONS ---

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

# Raw Claude outputs — one row per analyst or translator call per run
# analysis_type: bull, bear, contrarian, translator_bull_case,
#                translator_bear_case, translator_contrarian_take,
#                translator_divergence, translator_synthesis,
#                translator_watch_tomorrow
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
CREATE_SIGNALS_TABLE = """
CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    value           REAL,
    threshold       REAL,
    triggered       INTEGER NOT NULL DEFAULT 0,
    direction       TEXT,
    persona         TEXT,
    entity_a        TEXT,
    relationship    TEXT,
    entity_b        TEXT,
    notes           TEXT
)
"""

# Pipeline health — one row per run
# status stays 'running' if pipeline crashes — detectable failure on Day 26
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
    notes                       TEXT
)
"""

# Full LLM audit trail — one row per call_llm() invocation
# model_requested vs model_used captures fallback events for Day 26 audit
# call_type: bull, bear, contrarian, translator_[section], sentiment, geopolitical
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


# --- CONNECTION ---

def get_connection():
    """
    Opens and returns a SQLite connection with row_factory set.
    row_factory = sqlite3.Row lets you access columns by name
    instead of index — rows["ticker"] instead of rows[2].
    The database file is created automatically if it does not exist.
    """
    conn = sqlite3.connect(config.DB_PATH)
    # Row factory makes query results addressable by column name
    conn.row_factory = sqlite3.Row
    return conn


# --- INITIALISATION ---

def initialise_db():
    """
    Creates all tables and seeds the models lookup on first run.
    Safe to call every run — IF NOT EXISTS prevents data loss.
    Call once at the start of stock_monitor.py before any writes.
    """
    # The with block commits automatically on success
    # and rolls back automatically on any exception
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_MODELS_TABLE)
        cursor.execute(CREATE_PRICES_TABLE)
        cursor.execute(CREATE_ANALYSIS_TABLE)
        cursor.execute(CREATE_SIGNALS_TABLE)
        cursor.execute(CREATE_RUN_LOG_TABLE)
        cursor.execute(CREATE_LLM_CALLS_TABLE)
        cursor.execute(CREATE_SENTENCES_TABLE)

        # Seed known models — INSERT OR IGNORE means safe to re-run
        # Add new models here as Anthropic releases them
        known_models = [
            ("claude-sonnet-4-5",         "sonnet-4-5",  "anthropic", "sonnet"),
            ("claude-haiku-4-5-20251001",  "haiku-4-5",   "anthropic", "haiku"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO models (model_id, alias, provider, tier)
            VALUES (?, ?, ?, ?)
            """,
            known_models,
        )

    print("[DB] All tables initialised.")


# --- RUN ID ---

def generate_run_id():
    """
    Generates a unique run identifier based on the current timestamp.
    Format: YYYY-MM-DD_HH:MM:SS — human readable and sortable.
    Generate once at the start of each run and pass to all write functions.
    This is the key that links prices, analysis, signals, and llm_calls.
    """
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")


# --- WRITE FUNCTIONS ---
# All writes use the context manager pattern:
#   with get_connection() as conn
# This guarantees commit on success and rollback on failure.
# Every write function re-raises exceptions so the pipeline
# knows a write failed and can record it in run_log.

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
    stats is an optional dict of token counts, durations, error counts.
    Pass None if not yet tracking — only completed_at and status update.
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
                        error_count                 = ?
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
    Writes one row into the analysis table per analyst or translator call.
    analysis_type identifies the persona — bull, bear, contrarian,
    or translator_[section] for each translator output.
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
                 entity_a=None, relationship=None, entity_b=None, notes=None):
    """
    Writes one signal row per evaluated condition.
    triggered=1 means the threshold fired.
    triggered=0 means evaluated but not triggered — stored for near-miss queries.
    Called by threshold logic on Day 10. Read by the agent on Day 21.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO signals
                    (run_id, timestamp, ticker, signal_type, value, threshold,
                     triggered, direction, persona, entity_a, relationship,
                     entity_b, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, datetime.now().isoformat(), ticker, signal_type,
                    value, threshold, triggered, direction, persona,
                    entity_a, relationship, entity_b, notes,
                ),
            )
    except Exception as e:
        print(f"[DB] write_signal failed, rolled back: {e}")
        raise


def write_llm_call(run_id, call_type, model_requested, model_used,
                   fallback_used, input_tokens, output_tokens,
                   duration_secs, status="success", error_message=None):
    """
    Writes one audit row per call_llm() invocation.
    model_requested vs model_used captures fallback events.
    On Day 26 this table becomes the primary observability source.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_calls
                    (run_id, timestamp, call_type, model_requested, model_used,
                     fallback_used, input_tokens, output_tokens, duration_secs,
                     status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, datetime.now().isoformat(), call_type,
                    model_requested, model_used, int(fallback_used),
                    input_tokens, output_tokens, duration_secs,
                    status, error_message,
                ),
            )
    except Exception as e:
        print(f"[DB] write_llm_call failed, rolled back: {e}")
        raise


# --- READ FUNCTIONS ---

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
    Returns the most recent N run_log entries.
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
                       fallback_used, error_count
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