# stock_monitor.py — v5
# Day 10: Six-agent adversarial pipeline
# What changed from v4: Single analyst replaced with Bull, Bear,
# Black Swan, Pragmatist (Stage 1), Contrarian (Stage 2),
# Meta-Agent (Stage 3). Translator updated to consume Meta-Agent output.
# Data package builder introduced. Kill trigger checker added.
# persona_calls and signals writes added.

import time
import sqlite3
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf
import anthropic
import sys
from pathlib import Path

# Add ai-projects root to Python's path so shared/ is importable
# parent = stock-monitor/, parent.parent = ai-projects/
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))           # gives access to shared/
sys.path.insert(0, str(_ROOT / "stock-monitor"))  # gives access to config, database

from shared.utils import extract_json, call_llm, update_market_history, save_price_fixtures, send_email_alert, format_warning
from shared.data_sources import get_current_prices, get_intelligence_context


from prompts.analyst_persona import (
    STOCK_BULL_SYSTEM_PROMPT,
    STOCK_BEAR_SYSTEM_PROMPT,
    STOCK_BLACK_SWAN_SYSTEM_PROMPT,
    STOCK_PRAGMATIST_SYSTEM_PROMPT,
    STOCK_CONTRARIAN_SYSTEM_PROMPT,
    STOCK_META_AGENT_SYSTEM_PROMPT,
    TRANSLATOR_SYSTEM_PROMPT,
)
import config
import database

load_dotenv()

# Initialise the Anthropic client once at module level.
# All call_llm() calls share this single client instance.
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def check_stuck_runs():
    """
    Finds run_log rows stuck in 'running' status from crashed sessions
    and marks them failed before the scheduler fires a new run.

    Why this runs first: a crashed run leaves status='running' forever.
    Without this check, stale run_ids contaminate the next run's context.
    Same principle as a settlement system clearing unresolved prior-day
    positions before the next session opens.
    """

    # Calculate the cutoff — any 'running' row older than this is stuck
    cutoff = datetime.now() - timedelta(minutes=config.STUCK_RUN_THRESHOLD_MINUTES)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()

        # Find stuck runs older than the threshold
        cursor.execute("""
            SELECT run_id, started_at
            FROM run_log
            WHERE status = 'running'
            AND started_at < ?
        """, (cutoff_str,))

        stuck = cursor.fetchall()

        if not stuck:
            conn.close()
            return 0  # Nothing stuck — clean slate

        # Mark each stuck run as failed
        for run_id, started_at in stuck:
            cursor.execute("""
                UPDATE run_log
                SET status = 'failed',
                    completed_at = ?,
                    notes = 'Marked failed by stuck-run detection at session start'
                WHERE run_id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), run_id))

            print(format_warning(
                severity="WARN",
                file="stock_monitor.py",
                function="check_stuck_runs()",
                description=f"Stuck run detected — run_id '{run_id}' started at {started_at} had status='running' for more than {STUCK_RUN_THRESHOLD_MINUTES} minutes",
                fix="Run has been marked failed. Check logs for that run_id to diagnose the crash."
            ))

        conn.commit()
        conn.close()
        return len(stuck)  # Return count so main() can include it in run summary

    except Exception as e:
        print(format_warning(
            severity="ERROR",
            file="stock_monitor.py",
            function="check_stuck_runs()",
            description=f"Could not query run_log for stuck runs — {str(e)}",
            fix="Check that prices.db exists and run_log table is intact. Run database.py directly to verify."
        ))
        return 0

# ─────────────────────────────────────────────────────────────
# STEP 1 — KILL TRIGGER CHECKER
# Runs at the top of every session before any agent call.
# Queries the signals table for active unresolved kill triggers.
# Returns a dict keyed by ticker — each value is a list of
# active trigger dicts. Empty list means no active triggers.
# The Meta-Agent receives this and must REDUCE or EXIT if
# any trigger is active — it cannot ACCUMULATE or HOLD.
# ─────────────────────────────────────────────────────────────
def check_kill_triggers():
    """
    Queries signals table for active unresolved kill triggers per ticker.
    Returns dict: { "NVDA": [trigger_dict, ...], "TSM": [], ... }
    Empty list means no active triggers for that ticker.
    Called once at session start — result injected into every data package.
    """
    active_triggers = {ticker: [] for ticker in config.TICKERS}

    try:
        with database.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT ticker, signal_type, entity_a, relationship,
                       entity_b, notes, value, threshold
                FROM signals
                WHERE signal_type = 'kill_trigger'
                  AND triggered = 1
                  AND (outcome IS NULL OR outcome = 'unresolved')
                ORDER BY timestamp DESC
                """
            ).fetchall()

        for row in rows:
            ticker = row["ticker"]
            if ticker in active_triggers:
                active_triggers[ticker].append({
                    "signal_type":   row["signal_type"],
                    "entity_a":      row["entity_a"],
                    "relationship":  row["relationship"],
                    "entity_b":      row["entity_b"],
                    "notes":         row["notes"],
                    "value":         row["value"],
                    "threshold":     row["threshold"],
                })

        triggered_count = sum(
            len(v) for v in active_triggers.values()
        )
        if triggered_count > 0:
            print(f"  [KILL TRIGGERS] {triggered_count} active "
                  f"trigger(s) found — injected into data packages.")
        else:
            print("  [KILL TRIGGERS] No active triggers.")

    except Exception as e:
        print(f"  [KILL TRIGGERS] Check failed: {e} — continuing with empty.")

    return active_triggers

def check_thesis_staleness():
    """
    Checks THESIS_LAST_REVIEWED and PORTFOLIO_SECTIONS_LAST_REVIEWED
    against today's date. Flags any entry not reviewed in 30+ days.

    Runs at session start after check_kill_triggers().
    Non-blocking — prints warnings but never stops the pipeline.
    Returns a list of stale items so the run summary can include them.

    Why 30 days? Markets move fast enough that a thesis unchecked
    for a month may no longer reflect current conditions. The flag
    is a prompt to review, not an automatic action.
    """
    # today as a date object for clean comparison arithmetic
    today = datetime.now().date()

    # 30-day threshold — anything older than this gets flagged
    STALE_THRESHOLD_DAYS = 30

    stale_items = []  # collect all stale entries to return at the end

    print("\n[STALENESS] Checking thesis review dates...")

    # ── Check per-ticker thesis dates ──────────────────────
    for ticker, last_reviewed_str in config.THESIS_LAST_REVIEWED.items():
        # Parse the stored date string into a date object
        # Format is YYYY-MM-DD — matches how we store it in config.py
        last_reviewed = datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()

        # How many days since this thesis was last reviewed?
        days_since = (today - last_reviewed).days

        if days_since > STALE_THRESHOLD_DAYS:
            # Flag it — print to console and add to stale_items list
            print(f"[STALENESS] WARNING: {ticker} thesis not reviewed "
                  f"in {days_since} days (last: {last_reviewed_str})")
            stale_items.append({
                "type":         "ticker_thesis",
                "ticker":       ticker,
                "last_reviewed": last_reviewed_str,
                "days_since":   days_since,
            })
        else:
            # Within threshold — confirm it is current, no action needed
            print(f"[STALENESS] OK: {ticker} — {days_since} days since review")

    # ── Check portfolio section dates ──────────────────────
    for section, last_reviewed_str in config.PORTFOLIO_SECTIONS_LAST_REVIEWED.items():
        last_reviewed = datetime.strptime(last_reviewed_str, "%Y-%m-%d").date()
        days_since = (today - last_reviewed).days

        if days_since > STALE_THRESHOLD_DAYS:
            print(f"[STALENESS] WARNING: portfolio section '{section}' "
                  f"not reviewed in {days_since} days (last: {last_reviewed_str})")
            stale_items.append({
                "type":         "portfolio_section",
                "section":      section,
                "last_reviewed": last_reviewed_str,
                "days_since":   days_since,
            })
        else:
            print(f"[STALENESS] OK: {section} — {days_since} days since review")

    # ── Summary ────────────────────────────────────────────
    if stale_items:
        print(f"\n[STALENESS] {len(stale_items)} item(s) flagged for review.")
    else:
        print("\n[STALENESS] All thesis entries current.")

    # Return the list so the run summary can include stale count
    return stale_items

def check_portfolio_correlations(run_id):
    """
    Computes rolling 30-day Pearson correlation for each pair
    defined in config.CORRELATION_PAIRS.

    What Pearson correlation means in plain English:
      A number from -1 to +1 measuring how closely two price
      series moved together over the last 30 trading days.
      +1 = perfectly in sync. 0 = no relationship.
      Above the threshold = diversification assumption is weak.

    Runs after market history update each session — needs fresh
    data to be meaningful. Pure Python/pandas — no LLM call,
    no API cost.

    Writes a portfolio_relationship_alert signal to the signals
    table when a threshold is breached. The Meta-Agent reads
    active signals so it reasons with this information.

    Returns a list of breach dicts for the run summary.
    """
    import pandas as pd

    print("\n[CORRELATIONS] Checking portfolio correlation pairs...")
    breaches = []  # collect any threshold breaches to return

    for pair in config.CORRELATION_PAIRS:
        ticker_a  = pair["ticker_a"]
        ticker_b  = pair["ticker_b"]
        threshold = pair["threshold"]
        label     = pair["label"]
        rationale = pair["rationale"]

        try:
            # Fetch last 30 daily close prices for each ticker
            # read_market_history returns rows newest-first, so we
            # reverse to get oldest-first for correct time ordering
            rows_a = database.read_market_history(ticker_a, limit=30)
            rows_b = database.read_market_history(ticker_b, limit=30)

            if len(rows_a) < 10 or len(rows_b) < 10:
                # Not enough history to compute a meaningful correlation —
                # need at least 10 data points or the number is unreliable
                print(f"[CORRELATIONS] {label}: insufficient history "
                      f"({len(rows_a)} rows for {ticker_a}, "
                      f"{len(rows_b)} rows for {ticker_b}) — skipping.")
                continue

            # Build a dict of date -> close for each ticker
            # dict comprehension: {trade_date: close} for each row
            prices_a = {row["trade_date"]: row["close"] for row in rows_a}
            prices_b = {row["trade_date"]: row["close"] for row in rows_b}

            # Find dates where both tickers have data
            # set intersection gives us only the common trading days —
            # different markets (SGX vs NYSE) may have different holidays
            common_dates = sorted(
                set(prices_a.keys()) & set(prices_b.keys())
            )

            if len(common_dates) < 10:
                # After intersection, fewer than 10 shared dates —
                # not enough overlap to compute reliable correlation
                print(f"[CORRELATIONS] {label}: only {len(common_dates)} "
                      f"shared dates after intersection — skipping.")
                continue

            # Build aligned price series from the common dates
            # pandas Series gives us the .corr() method for free
            series_a = pd.Series(
                [prices_a[d] for d in common_dates],
                name=ticker_a
            )
            series_b = pd.Series(
                [prices_b[d] for d in common_dates],
                name=ticker_b
            )

            # Compute Pearson correlation — the core calculation
            # .corr() returns a float between -1 and +1
            correlation = round(series_a.corr(series_b), 4)

            if correlation > threshold:
                # Threshold breached — write alert to signals table
                # and record for run summary
                print(f"[CORRELATIONS] ALERT: {label} — "
                      f"correlation {correlation:.3f} exceeds "
                      f"threshold {threshold} over last "
                      f"{len(common_dates)} sessions.")

                database.write_signal(
                    run_id=run_id,
                    ticker=ticker_a,          # primary ticker for the alert
                    signal_type="portfolio_relationship_alert",
                    value=correlation,         # the actual correlation number
                    threshold=threshold,       # the threshold it breached
                    triggered=1,              # 1 = condition fired
                    direction=None,
                    persona="correlation_check",
                    entity_a=ticker_a,
                    relationship="correlated_with",
                    entity_b=ticker_b,
                    notes=(
                        f"{label}. "
                        f"30-day Pearson: {correlation:.3f} "
                        f"(threshold: {threshold}). "
                        f"{rationale}"
                    ),
                )

                breaches.append({
                    "label":       label,
                    "ticker_a":    ticker_a,
                    "ticker_b":    ticker_b,
                    "correlation": correlation,
                    "threshold":   threshold,
                })

            else:
                # Below threshold — thesis assumption currently holding
                print(f"[CORRELATIONS] OK: {label} — "
                      f"correlation {correlation:.3f} "
                      f"(threshold {threshold}, "
                      f"{len(common_dates)} sessions)")

        except Exception as e:
            # Log and continue — one failed pair never stops the pipeline
            print(f"[CORRELATIONS] ERROR: {label} failed in "
                  f"check_portfolio_correlations() — {e}. "
                  f"Fix: check market_history has data for "
                  f"{ticker_a} and {ticker_b}.")
            continue

    if breaches:
        print(f"\n[CORRELATIONS] {len(breaches)} threshold breach(es) "
              f"written to signals table.")
    else:
        print("\n[CORRELATIONS] All pairs within thresholds.")

    return breaches

def score_persona_call_outcomes():
    """
    Scores persona_calls at +5 and +20 trading-day horizons.

    Why two horizons?
    +5 trading days (~1 week) tests short-term momentum calls.
    +20 trading days (~1 month) tests thesis-level directional calls.
    Day 15 calibration uses both to find which horizon each persona
    is actually reliable at — the right horizon varies by persona type.

    Why price_at_signal instead of the run's price record?
    price_at_signal is logged at the exact moment the call is made
    and is immutable. This gives an accurate baseline regardless of
    when during the trading day the pipeline ran.

    Scoring rules (applied at both horizons):
      ACCUMULATE + price up >1%    → correct
      ACCUMULATE + price down >1%  → incorrect
      REDUCE/EXIT + price down >1% → correct
      REDUCE/EXIT + price up >1%   → incorrect
      HOLD (any direction)         → partial
      price move <1% either way    → void (noise, not signal)

    Runs at session start. Non-blocking — never stops the pipeline.
    Skips calls that are already scored or have missing price data.
    """
    import pandas as pd

    print("\n[SCORING] Scoring persona calls at +5 and +20 trading-day horizons...")

    # Void threshold — moves smaller than this are market noise
    VOID_THRESHOLD = 1.0

    # Horizons to score — days from market_history
    HORIZONS = [
        {"days": 5,  "col": "outcome_5d"},
        {"days": 20, "col": "outcome_20d"},
    ]

    try:
        with database.get_connection() as conn:

            # ── Ensure outcome columns exist ──────────────────────
            # Add outcome_5d and outcome_20d columns if not present.
            # This is a safe ALTER TABLE — SQLite ignores if column exists
            # when we catch the error, so no migration script needed.
            for col in ["outcome_5d", "outcome_20d"]:
                try:
                    conn.execute(
                        f"ALTER TABLE persona_calls ADD COLUMN {col} TEXT"
                    )
                except Exception:
                    pass  # Column already exists — safe to ignore

            # ── Fetch all unscored calls that have price_at_signal ──
            # Only score calls where we have the baseline price logged.
            # run_id gives us the session date for horizon calculation.
            calls = conn.execute(
                """
                SELECT pc.id, pc.persona, pc.ticker, pc.direction,
                       pc.price_at_signal, pc.run_id,
                       pc.outcome_5d, pc.outcome_20d,
                       rl.started_at
                FROM persona_calls pc
                JOIN run_log rl ON pc.run_id = rl.run_id
                WHERE pc.price_at_signal IS NOT NULL
                  AND pc.direction IS NOT NULL
                  AND (pc.outcome_5d IS NULL OR pc.outcome_20d IS NULL)
                """
            ).fetchall()

            if not calls:
                print("[SCORING] No unscored calls with price_at_signal — "
                      "nothing to score yet.")
                return

            print(f"[SCORING] Found {len(calls)} call(s) to score...")

            scored_count   = 0
            skipped_count  = 0

            for call in calls:
                call_id         = call["id"]
                ticker          = call["ticker"]
                direction       = call["direction"]
                price_at_signal = call["price_at_signal"]
                started_at      = call["started_at"][:10]  # YYYY-MM-DD
                current_5d      = call["outcome_5d"]
                current_20d     = call["outcome_20d"]

                # Get market_history closes for this ticker ordered oldest first
                # We need dates after the signal date to find +5 and +20 closes
                history = conn.execute(
                    """
                    SELECT trade_date, close
                    FROM market_history
                    WHERE ticker = ?
                      AND trade_date > ?
                    ORDER BY trade_date ASC
                    """,
                    (ticker, started_at)
                ).fetchall()

                if not history:
                    skipped_count += 1
                    continue

                # history[0] is the first trading day after the signal
                # history[4] is +5 trading days, history[19] is +20
                updates = {}

                for horizon in HORIZONS:
                    col      = horizon["col"]
                    idx      = horizon["days"] - 1  # 0-indexed

                    # Skip if already scored at this horizon
                    if col == "outcome_5d"  and current_5d  is not None:
                        continue
                    if col == "outcome_20d" and current_20d is not None:
                        continue

                    # Not enough history yet — skip this horizon
                    if len(history) <= idx:
                        continue

                    future_close = history[idx]["close"]
                    future_date  = history[idx]["trade_date"]

                    if not future_close or price_at_signal == 0:
                        continue

                    # Compute percentage move from signal price to future close
                    pct_move = ((future_close - price_at_signal)
                                / price_at_signal) * 100

                    # Apply scoring rules
                    if abs(pct_move) < VOID_THRESHOLD:
                        outcome = "void"
                    elif direction == "ACCUMULATE":
                        outcome = "correct" if pct_move > 0 else "incorrect"
                    elif direction in ("REDUCE", "EXIT"):
                        outcome = "correct" if pct_move < 0 else "incorrect"
                    elif direction == "HOLD":
                        outcome = "partial"
                    else:
                        continue

                    updates[col] = outcome
                    print(f"[SCORING] {call['persona']:<15} {ticker:<8} "
                          f"{direction:<12} → {horizon['days']}d: {outcome} "
                          f"({pct_move:+.1f}% by {future_date})")

                if updates:
                    # Build dynamic UPDATE for whichever horizons were scored
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    values     = list(updates.values()) + [call_id]
                    conn.execute(
                        f"UPDATE persona_calls SET {set_clause} WHERE id = ?",
                        values
                    )
                    scored_count += 1
                else:
                    skipped_count += 1

            print(f"[SCORING] Complete — {scored_count} scored, "
                  f"{skipped_count} skipped (insufficient history).")

    except Exception as e:
        print(format_warning(
            "WARN", "stock_monitor.py", "score_persona_call_outcomes()",
            f"scoring failed — {e}",
            "check persona_calls and market_history tables have data"
        ))

# ─────────────────────────────────────────────────────────────
# STEP 2 — DATA PACKAGE BUILDER
# Assembles the six-layer input for every Stage 1 agent.
# One package per ticker. Same structure every time.
# The ticker variable changes — everything else is shared context.
# ─────────────────────────────────────────────────────────────

def build_chain_summary(all_price_data):
    """
    Builds a Python-assembled snapshot of all portfolio tickers today.
    NOT an LLM call — pure Python string building from price data.
    Free, deterministic, fast. Every agent gets this as Layer 3.
    Gives each agent live chain context without seeing other agents' outputs.

    Returns a formatted string describing the current state of the chain.
    """
    lines = [f"Chain status today ({datetime.now().strftime('%Y-%m-%d')}):\n"]

    # Map tickers to their chain roles for readable context
    roles = {
        "NVDA":   "demand anchor",
        "AVGO":   "network gatekeeper",
        "LITE":   "photonics",
        "TSM":    "production floor",
        "SMH":    "semiconductor ETF",
        "QQQ":    "nasdaq-100",
        "G3B.SI": "local anchor",
        "^VIX":   "fear gauge",
    }

    for row in all_price_data:
        ticker = row["ticker"]
        role   = roles.get(ticker, row.get("instrument_type", ""))
        price  = row.get("price", "N/A")
        pct    = row.get("pct_change", 0)
        vol    = row.get("volume_signal", "")
        direction = "+" if pct >= 0 else ""

        # VIX gets a regime tag rather than a volume signal
        if ticker == "^VIX":
            vix_val = price if isinstance(price, (int, float)) else 0
            if vix_val < 15:
                regime = "low_vix"
            elif vix_val < 20:
                regime = "normal"
            elif vix_val < 30:
                regime = "high_vix"
            else:
                regime = "crisis"
            lines.append(
                f"  {ticker:<10} ({role})"
                f"  {direction}{pct:.2f}%  ${price}  regime: {regime}"
            )
        else:
            vol_str = f"  vol: {vol}" if vol else ""
            lines.append(
                f"  {ticker:<10} ({role})"
                f"  {direction}{pct:.2f}%  ${price}{vol_str}"
            )

    return "\n".join(lines)


def build_historical_context(ticker):
    """
    Queries market_history for trajectory data on a given ticker.
    Returns a dict of statistical anchors — trend, streak, range
    position, moving averages, volatility regime, correlations.

    Gracefully degrades: only returns fields it can compute honestly
    from available history. Fields requiring insufficient data are
    omitted rather than fabricated.

    This is Layer 5 of the data package — the Pragmatist depends on
    this most heavily. All other agents use it for grounding.
    """
    # In fixture mode skip the real history query — fixture prices
    # are illustrative and will not match real 5-year market_history
    if not config.USE_LIVE_DATA:
        return {
            "sessions_in_db": 0,
            "note": "Historical context unavailable in fixture mode. "
                    "Agents should reason from current price data only."
        }
    
    context = {}

    try:
        rows = database.read_market_history(ticker, limit=60)

        if not rows:
            context["sessions_in_db"] = 0
            context["note"] = "No market history available yet."
            return context

        # Convert to list of dicts for easier processing
        # rows are ordered DESC (newest first) from read_market_history
        history = [dict(r) for r in rows]
        n = len(history)
        context["sessions_in_db"] = n

        # Most recent close is history[0], oldest is history[-1]
        latest_close = history[0]["close"]

        # ── Short-term trend (requires 3+ sessions) ──
        if n >= 3:
            close_3d_ago = history[2]["close"]
            if close_3d_ago and close_3d_ago != 0:
                context["3_day_return"] = round(
                    ((latest_close - close_3d_ago) / close_3d_ago) * 100, 2
                )

        if n >= 5:
            close_5d_ago = history[4]["close"]
            if close_5d_ago and close_5d_ago != 0:
                context["5_day_return"] = round(
                    ((latest_close - close_5d_ago) / close_5d_ago) * 100, 2
                )
            # Trend direction from 3-day and 5-day returns
            r3 = context.get("3_day_return", 0)
            r5 = context.get("5_day_return", 0)
            if r3 > 0 and r5 > 0:
                context["trend_direction"] = "up_short_term"
            elif r3 < 0 and r5 < 0:
                context["trend_direction"] = "down_short_term"
            else:
                context["trend_direction"] = "choppy"

            # Streak — consecutive up or down sessions
            streak = 0
            direction = None
            for i, row in enumerate(history):
                pct = row.get("pct_change")
                if pct is None:
                    break
                if i == 0:
                    direction = "up" if pct >= 0 else "down"
                    streak = 1
                elif (pct >= 0 and direction == "up") or \
                     (pct < 0 and direction == "down"):
                    streak += 1
                else:
                    break
            context["streak"] = streak if direction == "up" else -streak

        # ── Position in recent range (requires 10+ sessions) ──
        if n >= 10:
            closes_10 = [r["close"] for r in history[:10] if r["close"]]
            high_10   = max(closes_10)
            low_10    = min(closes_10)
            if high_10 != low_10:
                context["position_in_range_10d"] = round(
                    (latest_close - low_10) / (high_10 - low_10), 2
                )
            context["10d_high"] = round(high_10, 2)
            context["10d_low"]  = round(low_10, 2)
            context["distance_from_10d_high"] = round(
                ((latest_close - high_10) / high_10) * 100, 2
            )

        # ── Moving averages (requires 50+ sessions — from 5yr backfill) ──
        if n >= 50:
            closes_50 = [r["close"] for r in history[:50] if r["close"]]
            ma_50     = sum(closes_50) / len(closes_50)
            context["ma_50"]         = round(ma_50, 2)
            context["above_ma_50"]   = latest_close > ma_50
            context["pct_vs_ma50"]   = round(
                ((latest_close - ma_50) / ma_50) * 100, 2
            )

        if n >= 200:
            closes_200 = [r["close"] for r in history[:200] if r["close"]]
            ma_200     = sum(closes_200) / len(closes_200)
            context["ma_200"]        = round(ma_200, 2)
            context["above_ma_200"]  = latest_close > ma_200
            context["pct_vs_ma200"]  = round(
                ((latest_close - ma_200) / ma_200) * 100, 2
            )

        # ── Volatility regime (requires 20+ sessions) ──
        if n >= 20:
            # Compute average absolute daily pct change over last 20 sessions
            recent_moves = [
                abs(r["pct_change"])
                for r in history[:20]
                if r["pct_change"] is not None
            ]
            if recent_moves:
                avg_move = sum(recent_moves) / len(recent_moves)
                context["avg_daily_move_20d"] = round(avg_move, 2)
                # Compare to the longer-term average for regime classification
                if n >= 60:
                    all_moves = [
                        abs(r["pct_change"])
                        for r in history
                        if r["pct_change"] is not None
                    ]
                    long_avg = sum(all_moves) / len(all_moves)
                    ratio    = avg_move / long_avg if long_avg > 0 else 1
                    if ratio > 1.5:
                        context["volatility_regime"] = "elevated"
                    elif ratio < 0.7:
                        context["volatility_regime"] = "suppressed"
                    else:
                        context["volatility_regime"] = "normal"

    except Exception as e:
        print(f"  [HISTORICAL CONTEXT] {ticker}: failed — {e}")
        context["error"] = str(e)

    return context


def determine_vix_regime(all_price_data):
    """
    Extracts the current VIX level from the price data and
    classifies it into a regime tag. Returns the regime string.
    Used to tag every persona_calls row with the macro context
    at the time of the call — essential for Day 15 accuracy analysis.

    Regime thresholds:
      low_vix:  below 15  — risk-on, complacency territory
      normal:   15 to 20  — baseline market conditions
      high_vix: 20 to 30  — elevated caution warranted
      crisis:   above 30  — defensive posture, thesis review
    """
    for row in all_price_data:
        if row["ticker"] == "^VIX":
            vix = row.get("price", 20)
            if vix < 15:
                return "low_vix", vix
            elif vix < 20:
                return "normal", vix
            elif vix < 30:
                return "high_vix", vix
            else:
                return "crisis", vix
    # VIX not in data — default to normal
    return "normal", None


def build_data_package(ticker, instrument_type, all_price_data,
                       active_kill_triggers, intelligence_context):
    """
    Assembles the complete six-layer data package for one ticker.
    Called once per ticker before Stage 1 agents run.

    Layer 1: Target ticker live price data (price, pct_change, volume)
    Layer 2: TICKER_THESIS — static structural role in the supply chain
    Layer 3: Chain summary — live state of all tickers today (Python-built)
    Layer 4: PORTFOLIO_RELATIONSHIPS — causal chain description
    Layer 5: Historical context — trajectory from market_history
    Layer 6: Intelligence context — macro, geopolitical, AI, regulatory

    Also injects active kill triggers so every agent — especially the
    Meta-Agent — knows the pre-committed exit conditions before reasoning.

    Returns a formatted string ready to pass as the user prompt to
    each Stage 1 agent call.
    """
    # Find this ticker's price row from the full price data
    ticker_row = next(
        (r for r in all_price_data if r["ticker"] == ticker), {}
    )

    # ── Layer 1: Live price data for this ticker ──
    price_block = f"""
TARGET TICKER: {ticker} ({instrument_type})
Current price:   ${ticker_row.get('price', 'N/A')}
Previous close:  ${ticker_row.get('prev_close', 'N/A')}
Change:          {ticker_row.get('pct_change', 'N/A')}%
Volume:          {ticker_row.get('volume', 'N/A')} shares
Volume signal:   {ticker_row.get('volume_signal', 'unavailable')}
Volume vs avg:   {ticker_row.get('volume_vs_avg', 'N/A')}x 30-day average
""".strip()

    # ── Layer 2: Static thesis context ──
    thesis_block = f"""
THESIS CONTEXT
{config.TICKER_THESIS.get(ticker, 'No thesis defined for this ticker.')}
""".strip()

    # ── Layer 3: Live chain summary (Python-assembled, not LLM) ──
    chain_block = f"""
CHAIN SUMMARY — LIVE STATE TODAY
{build_chain_summary(all_price_data)}
""".strip()

    # ── Layer 4: Portfolio context ──
    portfolio_block = f"""
PORTFOLIO CONTEXT
{config.PORTFOLIO_RELATIONSHIPS}
""".strip()

    # ── Layer 5: Historical context from market_history ──
    hist = build_historical_context(ticker)
    if hist.get("sessions_in_db", 0) == 0:
        hist_block = "HISTORICAL CONTEXT\nNo market history available yet."
    else:
        hist_block = f"""
HISTORICAL CONTEXT
Sessions in database: {hist.get('sessions_in_db', 0)}
3-day return:         {hist.get('3_day_return', 'N/A')}%
5-day return:         {hist.get('5_day_return', 'N/A')}%
Trend direction:      {hist.get('trend_direction', 'N/A')}
Streak:               {hist.get('streak', 'N/A')} sessions
Position in range:    {hist.get('position_in_range_10d', 'N/A')} (0=at low, 1=at high)
10-day high:          ${hist.get('10d_high', 'N/A')}
10-day low:           ${hist.get('10d_low', 'N/A')}
Distance from high:   {hist.get('distance_from_10d_high', 'N/A')}%
50-day MA:            ${hist.get('ma_50', 'N/A')}  (above: {hist.get('above_ma_50', 'N/A')})
200-day MA:           ${hist.get('ma_200', 'N/A')} (above: {hist.get('above_ma_200', 'N/A')})
Volatility regime:    {hist.get('volatility_regime', 'N/A')}
""".strip()

    # ── Layer 6: Intelligence context ──
    macro = intelligence_context.get("macro_regime", {})
    geo   = intelligence_context.get("geopolitical_signals", [])
    ai    = intelligence_context.get("ai_research_signals", [])
    reg   = intelligence_context.get("regulatory_signals", [])
    sent  = intelligence_context.get("sentiment_signals", {})

    intel_block = f"""
INTELLIGENCE CONTEXT
Macro regime:
  Fed stance:        {macro.get('fed_stance', 'N/A')}
  Rate environment:  {macro.get('rate_environment', 'N/A')}
  Dollar strength:   {macro.get('dollar_strength', 'N/A')}
  Key macro signal:  {macro.get('key_macro_signal', 'N/A')}

Geopolitical signals:
{chr(10).join(f'  - {s}' for s in geo)}

AI research signals:
{chr(10).join(f'  - {s}' for s in ai)}

Regulatory signals:
{chr(10).join(f'  - {s}' for s in reg)}

Sentiment:
  Retail positioning:    {sent.get('retail_positioning', 'N/A')}
  Institutional flows:   {sent.get('institutional_flows', 'N/A')}
  Contrarian indicator:  {sent.get('contrarian_indicator', 'N/A')}
""".strip()

    # ── Active kill triggers for this ticker ──
    triggers = active_kill_triggers.get(ticker, [])
    if triggers:
        trigger_lines = [
            f"  - {t.get('entity_b', 'unknown condition')} "
            f"[{t.get('notes', '')}]"
            for t in triggers
        ]
        trigger_block = (
            f"ACTIVE KILL TRIGGERS ({len(triggers)} active)\n"
            + "\n".join(trigger_lines)
            + "\nIMPORTANT: Active kill triggers override normal analysis."
        )
    else:
        trigger_block = "ACTIVE KILL TRIGGERS: None currently active."

    # ── Assemble all layers into the final prompt ──
    return "\n\n".join([
        price_block,
        thesis_block,
        chain_block,
        portfolio_block,
        hist_block,
        intel_block,
        trigger_block,
    ])


# ─────────────────────────────────────────────────────────────
# STEP 3 — STAGE 1: RUN FOUR ISOLATED AGENTS PER TICKER
# Bull, Bear, Black Swan, Pragmatist run sequentially per ticker.
# Each receives the same data package — no agent sees another's output.
# All four outputs stored before Stage 2 Contrarian runs.
# Async parallelisation in Day 17 — sequential is correct for now.
# ─────────────────────────────────────────────────────────────

def run_stage1_agent(agent_name, system_prompt, data_package,
                     ticker, run_id, vix_regime, vix_level):
    """
    Runs one Stage 1 agent call for one ticker.
    Writes output to analysis table and persona_calls table.
    Returns parsed JSON output or None on failure.

    agent_name:    one of 'bull', 'bear', 'black_swan', 'pragmatist'
    system_prompt: the agent's standing brief from analyst_persona.py
    data_package:  the six-layer string assembled by build_data_package()
    ticker:        the ticker this agent is reasoning about
    run_id:        the current run ID for database linkage
    vix_regime:    current VIX regime tag for persona_calls row
    vix_level:     current VIX price for persona_calls row
    """
    start = time.time()
    print(f"    [{agent_name.upper()}] reasoning on {ticker}...")

    text, usage = call_llm(
        prompt=(
            f"Analyse this data package and return your JSON response.\n\n"
            f"{data_package}"
        ),
        system=system_prompt,
        model=config.STAGE_1_MODEL,
        max_tokens=config.STAGE_1_MAX_TOKENS,
        temperature=config.STAGE_1_TEMPERATURE,
        fallback_model=config.FALLBACK_MODEL,
        client=client,
        call_type=f"stage1_{agent_name}_{ticker}",
    )
    duration = round(time.time() - start, 1)

    # Write LLM audit row — one row per call_llm() invocation
    database.write_llm_call(
        run_id=run_id,
        call_type=f"stage1_{agent_name}",
        model_requested=config.STAGE_1_MODEL,
        model_used=usage.get("model_used"),
        fallback_used=usage.get("fallback_used", False),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_secs=duration,
        status="fallback" if usage.get("fallback_used") else "success",
        retried=usage.get("retried", False),
        truncated=usage.get("truncated", False),
        retry_budget=usage.get("retry_budget"),
    )

    # Detect LLM error — graceful degradation, skip this agent
    if text.startswith("[LLM_ERROR]"):
        print(f"    [{agent_name.upper()}] LLM error — skipping.")
        return None, usage.get("warnings", [])

    # Write raw output to analysis table
    database.write_analysis(
        run_id=run_id,
        output_text=text,
        analysis_type=agent_name,
        ticker=ticker,
        source="stock_monitor",
        truncated=usage.get("truncated", False),
    )

    # Parse JSON output — returns None if unparseable
    parsed, error = extract_json(text)
    if not parsed:
        print(f"    [{agent_name.upper()}] JSON parse failed: {error}")
        return None, usage.get("warnings", [])

    # Write persona_calls row — the voting ledger for Day 15 tuning
    # direction and confidence come from the parsed JSON output
    # Extract the current price for this ticker from the data package.
    # Stored as price_at_signal — immutable baseline for +5/+20 day scoring.
    # Pulled from the prices table for the current run rather than passed
    # as a parameter to keep the function signature clean.
    price_at_signal = None
    try:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT price FROM prices WHERE run_id = ? AND ticker = ? LIMIT 1",
                (run_id, ticker)
            ).fetchone()
            if row:
                price_at_signal = row["price"]
    except Exception:
        pass  # Non-fatal — scoring will skip this call if price is missing

    database.write_persona_call(
        run_id=run_id,
        persona=agent_name,
        ticker=ticker,
        direction=parsed.get("direction"),
        confidence_score=parsed.get("confidence"),
        regime_tag=vix_regime,
        vix_level=vix_level,
        rationale_summary=parsed.get("primary_argument")
                          or parsed.get("statistical_anchor")
                          or parsed.get("unmapped_risk", "")[:200],
        price_at_signal=price_at_signal,
    )

    print(f"    [{agent_name.upper()}] {ticker}: "
          f"{parsed.get('direction', '?')} "
          f"(confidence {parsed.get('confidence', '?')}) "
          f"— {duration}s")
    # Return parsed output AND any warnings from call_llm()
    # Caller appends these to run_warnings for the end-of-run summary
    return parsed, usage.get("warnings", [])


# ─────────────────────────────────────────────────────────────
# STEP 4 — STAGE 2: CONTRARIAN PER TICKER
# Runs after all four Stage 1 agents complete for a given ticker.
# Receives the four Stage 1 JSON outputs alongside the data package.
# Identifies shared blind spots and hidden consensus.
# ─────────────────────────────────────────────────────────────

def run_contrarian(stage1_outputs, data_package, ticker,
                   run_id, vix_regime, vix_level):
    """
    Runs the Contrarian agent for one ticker.
    stage1_outputs: dict with keys bull, bear, black_swan, pragmatist —
                    values are the parsed JSON dicts from Stage 1.
    Writes to analysis and persona_calls tables.
    Returns parsed JSON or None on failure.
    """
    start = time.time()
    print(f"    [CONTRARIAN] challenging {ticker}...")

    # Build the Stage 1 context block — Contrarian reads all four outputs
    # This is the only agent that sees other agents' outputs before forming
    # its own view. This is by design — its job is to find what they missed.
    stage1_block = "STAGE 1 AGENT OUTPUTS — READ BEFORE FORMING YOUR VIEW\n"
    for agent_name, output in stage1_outputs.items():
        if output:
            stage1_block += (
                f"\n{agent_name.upper()}:\n"
                f"{json.dumps(output, indent=2)}\n"
            )
        else:
            stage1_block += f"\n{agent_name.upper()}: [output unavailable]\n"

    # Contrarian prompt combines the data package AND the Stage 1 outputs
    contrarian_prompt = (
        f"Here are the four Stage 1 agent outputs for {ticker}.\n"
        f"Read them carefully, then review the data package, then "
        f"return your Contrarian JSON response.\n\n"
        f"{stage1_block}\n\n"
        f"DATA PACKAGE:\n{data_package}"
    )

    text, usage = call_llm(
        prompt=contrarian_prompt,
        system=STOCK_CONTRARIAN_SYSTEM_PROMPT,
        model=config.STAGE_2_MODEL,
        max_tokens=config.STAGE_2_MAX_TOKENS,
        temperature=config.STAGE_2_TEMPERATURE,
        fallback_model=config.FALLBACK_MODEL,
        client=client,
        call_type=f"stage2_contrarian_{ticker}",
    )
    duration = round(time.time() - start, 1)

    database.write_llm_call(
        run_id=run_id,
        call_type="stage2_contrarian",
        model_requested=config.STAGE_2_MODEL,
        model_used=usage.get("model_used"),
        fallback_used=usage.get("fallback_used", False),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_secs=duration,
        status="fallback" if usage.get("fallback_used") else "success",
        retried=usage.get("retried", False),
        truncated=usage.get("truncated", False),
        retry_budget=usage.get("retry_budget"),
    )

    if text.startswith("[LLM_ERROR]"):
        print(f"    [CONTRARIAN] LLM error — skipping.")
        return None, usage.get("warnings", [])

    database.write_analysis(
        run_id=run_id,
        output_text=text,
        analysis_type="contrarian",
        ticker=ticker,
        source="stock_monitor",
        truncated=usage.get("truncated", False),
    )

    parsed, error = extract_json(text)
    if not parsed:
        print(f"    [CONTRARIAN] JSON parse failed: {error}")
        return None, usage.get("warnings", [])

    # Write persona_calls row for the Contrarian
    # Contrarian is scored like Stage 1 agents — its directional call
    # is tracked and outcome-scored at T+3 sessions
    # Same price_at_signal logic as run_stage1_agent() —
    # immutable baseline for +5/+20 trading-day outcome scoring.
    price_at_signal = None
    try:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT price FROM prices WHERE run_id = ? AND ticker = ? LIMIT 1",
                (run_id, ticker)
            ).fetchone()
            if row:
                price_at_signal = row["price"]
    except Exception:
        pass

    database.write_persona_call(
        run_id=run_id,
        persona="contrarian",
        ticker=ticker,
        direction=parsed.get("direction"),
        confidence_score=parsed.get("confidence"),
        regime_tag=vix_regime,
        vix_level=vix_level,
        rationale_summary=parsed.get("strongest_challenge", "")[:200],
        price_at_signal=price_at_signal,
    )

    print(f"    [CONTRARIAN] {ticker}: "
          f"{parsed.get('direction', '?')} "
          f"(confidence {parsed.get('confidence', '?')}) "
          f"— {duration}s")
    # Return parsed output AND any warnings from call_llm()
    # Caller appends these to run_warnings for the end-of-run summary
    return parsed, usage.get("warnings", [])

# ─────────────────────────────────────────────────────────────
# STEP 5 — STAGE 3: META-AGENT (PORTFOLIO MANAGER)
# Runs once after all per-ticker Stage 1+2 calls complete.
# Reads the full ledger across all tickers and produces
# ACCUMULATE/HOLD/REDUCE/EXIT per ticker + 3 kill triggers per ticker.
# Runs at temperature 0.1 — deterministic, auditable.
# Meta-Agent does NOT get a persona_calls row — it renders decisions,
# not directional bets. Its outputs go to signals table instead.
# ─────────────────────────────────────────────────────────────

def run_meta_agent(all_ticker_outputs, all_price_data,
                   intelligence_context, run_id,
                   vix_regime, vix_level):
    """
    Runs the Meta-Agent portfolio manager call.
    all_ticker_outputs: dict keyed by ticker, each value contains
                        the Stage 1+2 agent outputs for that ticker.
    Writes kill triggers to signals table.
    Returns parsed JSON or None on failure.
    """
    start = time.time()
    print("\n  [META-AGENT] rendering portfolio decisions...")

    # Assemble the full portfolio ledger for the Meta-Agent
    # This is the only call that sees all tickers together
    portfolio_ledger = {
        "session_date":         datetime.now().strftime("%Y-%m-%d"),
        "vix_level":            vix_level,
        "vix_regime":           vix_regime,
        "portfolio_context":    config.PORTFOLIO_RELATIONSHIPS,
        "intelligence_context": intelligence_context,
        "per_ticker_analysis":  all_ticker_outputs,
    }

    text, usage = call_llm(
        prompt=(
            f"Here is the complete portfolio ledger for today's session. "
            f"Render your final decisions for each ticker.\n\n"
            f"{json.dumps(portfolio_ledger, indent=2)}"
        ),
        system=STOCK_META_AGENT_SYSTEM_PROMPT,
        model=config.STAGE_3_MODEL,
        max_tokens=config.STAGE_3_MAX_TOKENS,
        temperature=config.STAGE_3_TEMPERATURE,
        fallback_model=config.FALLBACK_MODEL,
        client=client,
        call_type="stage3_meta_agent",
    )
    duration = round(time.time() - start, 1)

    database.write_llm_call(
        run_id=run_id,
        call_type="stage3_meta_agent",
        model_requested=config.STAGE_3_MODEL,
        model_used=usage.get("model_used"),
        fallback_used=usage.get("fallback_used", False),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_secs=duration,
        status="fallback" if usage.get("fallback_used") else "success",
        retried=usage.get("retried", False),
        truncated=usage.get("truncated", False),
        retry_budget=usage.get("retry_budget"),
    )

    if text.startswith("[LLM_ERROR]"):
        print("  [META-AGENT] LLM error — pipeline cannot complete.")
        return None, usage.get("warnings", [])

    database.write_analysis(
        run_id=run_id,
        output_text=text,
        analysis_type="meta_agent",
        ticker=None,   # portfolio-level — no single ticker
        source="stock_monitor",
        truncated=usage.get("truncated", False),
    )

    parsed, error = extract_json(text)
    if not parsed:
        print(f"  [META-AGENT] JSON parse failed: {error}")
        return None, usage.get("warnings", [])

    # ── Write kill triggers to signals table ──
    # Three kill triggers per ticker stored as entity_a/relationship/entity_b
    # rows. check_kill_triggers() reads these at the top of every future session.
    tickers_output = parsed.get("tickers", {})
    for ticker, ticker_decision in tickers_output.items():
        decision = ticker_decision.get("decision", "HOLD")

        # Write the meta decision as a signal row
        database.write_signal(
            run_id=run_id,
            ticker=ticker,
            signal_type="meta_decision",
            direction=decision,
            notes=ticker_decision.get("primary_rationale", ""),
        )

        # Write each kill trigger as a separate signal row
        for i, trigger_key in enumerate(
            ["kill_trigger_1", "kill_trigger_2", "kill_trigger_3"], 1
        ):
            trigger_text = ticker_decision.get(trigger_key)
            if trigger_text:
                # Map trigger number to type for clarity
                trigger_types = {
                    1: "price/technical",
                    2: "thesis_integrity",
                    3: "macro_regime"
                }
                database.write_signal(
                    run_id=run_id,
                    ticker=ticker,
                    signal_type="kill_trigger",
                    triggered=0,   # not yet fired — pre-committed condition
                    entity_a=ticker,
                    relationship="kill_trigger",
                    entity_b=trigger_text,
                    notes=f"Type: {trigger_types[i]}. "
                          f"Decision: {decision}. "
                          f"Horizon: {ticker_decision.get('review_horizon', 'T+3')}",
                )
    # ── Email alerts for high-conviction decisions ────────────
    # Sends an alert when Meta-Agent produces REDUCE or EXIT
    # with confidence >= 4, or when any kill trigger fires.
    # Runs after all signals are written so the email body can
    # reference the full decision set.
    # Only fires on live runs — fixture runs do not send emails
    # because the decisions are pre-captured, not real signals.
    if config.USE_LIVE_DATA:
        alert_lines = []

        for ticker, ticker_decision in tickers_output.items():
            decision   = ticker_decision.get("decision", "HOLD")
            confidence = ticker_decision.get("confidence", 0)

            # High-conviction REDUCE or EXIT — warrants immediate attention
            if decision in ("REDUCE", "EXIT") and confidence >= 4:
                alert_lines.append(
                    f"{ticker}: {decision} (confidence {confidence}/5)\n"
                    f"  {ticker_decision.get('primary_rationale', '')[:200]}"
                )

        if alert_lines:
            subject = f"Action required — {len(alert_lines)} high-conviction signal(s)"
            body = (
                f"Stock Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"VIX regime: {vix_regime} (VIX: {vix_level})\n\n"
                f"HIGH-CONVICTION SIGNALS\n"
                f"{'─' * 40}\n"
                + "\n\n".join(alert_lines)
                + f"\n\n{'─' * 40}\n"
                f"Review the full briefing in your terminal or run summary."
            )
            send_email_alert(subject, body)
    # ── End email alerts ──────────────────────────────────────
    print(f"  [META-AGENT] Complete — {duration}s")
    # Return parsed output AND any warnings from call_llm()
    # Caller appends these to run_warnings for the end-of-run summary
    return parsed, usage.get("warnings", [])


# ─────────────────────────────────────────────────────────────
# STEP 6 — TRANSLATOR
# Reads Meta-Agent output and produces plain English briefing.
# Not an analyst — never re-analyses. Only translates and teaches.
# ─────────────────────────────────────────────────────────────

def run_translator(meta_output, run_id):
    """
    Translates the Meta-Agent's portfolio decisions into plain English.
    Receives the full parsed Meta-Agent JSON.
    Returns plain text briefing string.
    """
    start = time.time()
    print("\n  [TRANSLATOR] writing plain English briefing...")

    text, usage = call_llm(
        prompt=(
            f"Here are today's portfolio manager decisions. "
            f"Please explain them clearly.\n\n"
            f"{json.dumps(meta_output, indent=2)}"
        ),
        system=TRANSLATOR_SYSTEM_PROMPT,
        model=config.TRANSLATOR_MODEL,
        max_tokens=config.TRANSLATOR_MAX_TOKENS,
        temperature=config.TRANSLATOR_TEMPERATURE,
        fallback_model=config.FALLBACK_MODEL,
        client=client,
        call_type="translator",
    )
    duration = round(time.time() - start, 1)

    database.write_llm_call(
        run_id=run_id,
        call_type="translator",
        model_requested=config.TRANSLATOR_MODEL,
        model_used=usage.get("model_used"),
        fallback_used=usage.get("fallback_used", False),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_secs=duration,
        status="fallback" if usage.get("fallback_used") else "success",
        retried=usage.get("retried", False),
        truncated=usage.get("truncated", False),
        retry_budget=usage.get("retry_budget"),
    )

    if text.startswith("[LLM_ERROR]"):
        return "[Translator unavailable — see LLM error above.]", usage.get("warnings", [])

    database.write_analysis(
        run_id=run_id,
        output_text=text,
        analysis_type="translator",
        ticker=None,
        source="stock_monitor",
        truncated=usage.get("truncated", False),
    )

    print(f"  [TRANSLATOR] Complete — {duration}s")
    # Return text AND any warnings from call_llm()
    # Caller appends these to run_warnings for the end-of-run summary
    return text, usage.get("warnings", [])


# ─────────────────────────────────────────────────────────────
# STEP 7 — DISPLAY
# Prints the Meta-Agent decisions and Translator briefing to terminal.
# Formatted for readability — not JSON.
# ─────────────────────────────────────────────────────────────

def display_results(price_data, meta_output, briefing):
    """
    Prints price data, Meta-Agent decisions, and plain English briefing.
    meta_output: the parsed Meta-Agent JSON dict.
    briefing:    the plain text Translator output.
    """
    print("\n" + "=" * 60)
    print(f"  STOCK MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # ── Price data ──
    print("\n[ PRICE DATA ]\n")
    for row in price_data:
        direction = "+" if row["pct_change"] >= 0 else ""
        vol_str   = (
            f"  vol: {row.get('volume_signal', '')}"
            if row.get("volume_signal") else ""
        )
        print(f"  {row['ticker']:<12} ${row['price']:<10} "
              f"{direction}{row['pct_change']}%{vol_str}")

    # ── Meta-Agent decisions ──
    if meta_output:
        print("\n[ PORTFOLIO DECISIONS ]\n")
        tickers_out = meta_output.get("tickers", {})
        for ticker, decision in tickers_out.items():
            d         = decision.get("decision", "N/A")
            conf      = decision.get("confidence", "?")
            rationale = decision.get("primary_rationale", "")
            print(f"  {ticker:<12} {d:<12} (confidence {conf})")
            print(f"             {rationale}")
            print()

        summary = meta_output.get("portfolio_summary", "")
        if summary:
            print(f"[ PORTFOLIO SUMMARY ]\n")
            print(f"  {summary}\n")

        premortem = meta_output.get("premortem_flag", False)
        if premortem:
            premortem_scenario = meta_output.get("premortem_scenario")
            print("  [STRESS TEST FAILED] Premortem triggered — "
                  "review before acting on decisions.")
            if premortem_scenario:
                print(f"  Alternative thesis: {premortem_scenario}\n")

    # ── Plain English briefing ──
    print("=" * 60)
    print("  PLAIN ENGLISH BRIEFING")
    print("=" * 60)
    print(briefing)
    print("=" * 60 + "\n")


# ─────────────────────────────────────────────────────────────
# MAIN — ORCHESTRATES THE FULL PIPELINE
# Order: init → kill triggers → fetch data → Stage 1 per ticker
#      → Stage 2 per ticker → Stage 3 portfolio → Translator
#      → display → run summary → finish
# ─────────────────────────────────────────────────────────────

def main():
    """
    Orchestrates the full six-agent pipeline.
    Each step is a discrete function — one concern per function.
    Stats accumulate throughout and are written to run_log on finish.
    """
    # ── Initialise ──
    database.initialise_db()
    run_id    = database.generate_run_id()
    data_mode = "live" if config.USE_LIVE_DATA else "fixture"
    database.start_run(run_id, data_mode=data_mode)

    # Record wall-clock start time so we can compute total run duration
    # in the summary. time.time() returns seconds since epoch — subtract
    # at the end to get elapsed seconds for the full pipeline.
    run_start_time = time.time()

    # Accumulates token counts, durations, and cost across all calls
    stats = {
        "tickers_attempted":   0,
        "tickers_succeeded":   0,
        "tickers_failed":      0,
        "analyst_input_tokens":    0,
        "analyst_output_tokens":   0,
        "translator_input_tokens": 0,
        "translator_output_tokens":0,
        "analyst_duration_secs":   0,
        "translator_duration_secs":0,
        "fallback_used": 0,
        "error_count":   0,
        "total_cost_usd":0,
    }

    # Accumulates all LLM call costs for run summary
    all_call_costs = []

    # ── RUN WARNING SUMMARY ───────────────────────────────────────────────────
    # Pipe-delimited format: SEVERITY | file | function() | description | fix
    # Machine-readable — import directly into Excel or SQLite for trend analysis.
    # To add a new warning source:
    #   1. Call format_warning() from shared/utils.py to build the string
    #   2. Return it via usage["warnings"] from call_llm() callers
    #      OR append directly to run_warnings for stock_monitor.py functions
    # Never add free-form strings to run_warnings — always use format_warning()
    # ─────────────────────────────────────────────────────────────────────────
    run_warnings = []

    try:
        print(f"\n{'='*60}")
        print(f"  STOCK MONITOR — Run {run_id}")
        print(f"  Mode: {data_mode.upper()}")
        print(f"{'='*60}\n")

        # Score persona calls from T-3 sessions at session start
        # Non-blocking — runs before kill triggers so scored data
        # is available if any downstream function queries outcomes
        score_persona_call_outcomes()
        
        # Check for crashed runs from previous sessions before doing anything else
        stuck_count = check_stuck_runs()


        # ── Kill trigger check ──
        # Must run before any data fetch so active triggers are
        # injected into data packages before agents start reasoning
        print("Checking kill triggers...")
        active_kill_triggers = check_kill_triggers()
        # Check thesis staleness after kill triggers
        # Non-blocking — flags stale entries in run summary but never stops the run
        stale_items = check_thesis_staleness()

        # Correlation checks run after market history update so they
        # use the freshest available data. In fixture mode market
        # history is not updated but existing history is still valid
        # for correlation computation.
        correlation_breaches = check_portfolio_correlations(run_id)

        # ── Update market history (delta pull) ──
        # Fetches new trading days since last stored date.
        # Skipped in fixture mode — agents read existing market_history.
        # This must run before build_historical_context() is called.
        print("\nUpdating market history...")
        update_market_history(
            tickers=list(config.TICKERS.keys()),
            use_live=config.USE_LIVE_DATA,
        )

        # ── Fetch current prices ──
        print("\nFetching current prices...")
        price_data = get_current_prices(
            tickers=config.TICKERS,
            use_live=config.USE_LIVE_DATA,
        )
        stats["tickers_attempted"] = len(config.TICKERS)
        stats["tickers_succeeded"] = len(
            [r for r in price_data if r.get("price") is not None]
        )
        stats["tickers_failed"] = (
            stats["tickers_attempted"] - stats["tickers_succeeded"]
        )

        if not price_data:
            print("No price data retrieved.")
            database.finish_run(run_id, status="failed", stats=stats)
            return

        print(f"  Retrieved {stats['tickers_succeeded']} tickers.\n")

        # ── Write prices to database ──
        database.write_prices(run_id, price_data)

        # Auto-update price fixtures when running on live data.
        # CAPTURE_LIVE_DATA_FOR_FIXTURES controls whether the file
        # is actually overwritten — handled inside save_price_fixtures().
        # Called unconditionally when USE_LIVE_DATA=True — the function
        # respects the capture flag internally and does nothing if False.
        if config.USE_LIVE_DATA:
            save_price_fixtures(price_data)

        # ── Get VIX regime for tagging persona_calls ──
        vix_regime, vix_level = determine_vix_regime(price_data)
        print(f"  VIX regime: {vix_regime} (VIX: {vix_level})\n")

        # ── Fetch intelligence context ──
        intelligence_context = get_intelligence_context(
            use_live=config.USE_LIVE_DATA
        )

        # ── Stage 1 + Stage 2 per ticker ──
        # all_ticker_outputs accumulates agent results across all tickers.
        # Meta-Agent reads this in Stage 3.
        all_ticker_outputs = {}

        print("Running Stage 1 + Stage 2 agents...\n")
        for ticker, instrument_type in config.TICKERS.items():

            # VIX is a regime classifier — agents reason about it but
            # it does not get its own Stage 1 analysis round
            if ticker == "^VIX":
                continue

            print(f"  {ticker}:")

            # ── Build the data package for this ticker ──
            data_package = build_data_package(
                ticker=ticker,
                instrument_type=instrument_type,
                all_price_data=price_data,
                active_kill_triggers=active_kill_triggers,
                intelligence_context=intelligence_context,
            )

            # ── Stage 1: four isolated agents ──
            # Each agent receives the same data package independently.
            # No agent sees another's output at this stage.
            stage1_outputs = {}

            agents = [
                ("bull",        STOCK_BULL_SYSTEM_PROMPT),
                ("bear",        STOCK_BEAR_SYSTEM_PROMPT),
                ("black_swan",  STOCK_BLACK_SWAN_SYSTEM_PROMPT),
                ("pragmatist",  STOCK_PRAGMATIST_SYSTEM_PROMPT),
            ]

            for agent_name, system_prompt in agents:
                output, agent_warnings = run_stage1_agent(
                    agent_name=agent_name,
                    system_prompt=system_prompt,
                    data_package=data_package,
                    ticker=ticker,
                    run_id=run_id,
                    vix_regime=vix_regime,
                    vix_level=vix_level,
                )
                stage1_outputs[agent_name] = output
                run_warnings.extend(agent_warnings)

            # ── Stage 2: Contrarian reads all four Stage 1 outputs ──
            contrarian_output, contrarian_warnings = run_contrarian(
                stage1_outputs=stage1_outputs,
                data_package=data_package,
                ticker=ticker,
                run_id=run_id,
                vix_regime=vix_regime,
                vix_level=vix_level,
            )
            run_warnings.extend(contrarian_warnings)

            # Compress agent outputs for Meta-Agent — pass only the
            # essential fields, not full JSON. This reduces Meta-Agent
            # input from ~32k tokens to ~8k tokens while preserving
            # all decision-relevant information.
            def compress(output, key_fields):
                # Extracts only the fields the Meta-Agent needs
                # Drops verbose fields like full rationale text
                if not output:
                    return None
                return {k: output.get(k) for k in key_fields if k in output}

            all_ticker_outputs[ticker] = {
                "price": {
                    "price":      next((r["price"] for r in price_data if r["ticker"] == ticker), None),
                    "pct_change": next((r["pct_change"] for r in price_data if r["ticker"] == ticker), None),
                },
                "bull": compress(stage1_outputs.get("bull"), [
                    "direction", "confidence", "primary_argument",
                    "key_assumption", "regime_sensitivity", "watch_items"
                ]),
                "bear": compress(stage1_outputs.get("bear"), [
                    "direction", "confidence", "primary_argument",
                    "key_assumption", "regime_sensitivity", "watch_items"
                ]),
                "black_swan": compress(stage1_outputs.get("black_swan"), [
                    "direction", "confidence", "unmapped_risk",
                    "underweighted_risk", "contagion_path", "watch_items"
                ]),
                "pragmatist": compress(stage1_outputs.get("pragmatist"), [
                    "direction", "confidence", "statistical_anchor",
                    "volume_assessment", "trend_assessment", "watch_items"
                ]),
                "contrarian": compress(contrarian_output, [
                    "direction", "confidence", "shared_blind_spot",
                    "unasked_question", "strongest_challenge"
                ]),
                "active_kill_triggers": active_kill_triggers.get(ticker, []),
            }

            print()  # spacing between tickers

        # ── Stage 3: Meta-Agent reads full portfolio ledger ──
        meta_output, meta_warnings = run_meta_agent(
            all_ticker_outputs=all_ticker_outputs,
            all_price_data=price_data,
            intelligence_context=intelligence_context,
            run_id=run_id,
            vix_regime=vix_regime,
            vix_level=vix_level,
        )
        run_warnings.extend(meta_warnings)

        # ── Translator: plain English briefing ──
        briefing = ""
        if meta_output:
            briefing, translator_warnings = run_translator(meta_output, run_id)
            run_warnings.extend(translator_warnings)

        # ── Display results ──
        display_results(price_data, meta_output, briefing)

        # ── Compute total run cost from all llm_calls for this run ──
        # Queries the database rather than summing from stats — this
        # captures every call including any that bypassed stats tracking
        try:
            with database.get_connection() as conn:
                cost_row = conn.execute(
                    "SELECT COALESCE(SUM(cost_usd), 0) AS total "
                    "FROM llm_calls WHERE run_id = ?",
                    (run_id,)
                ).fetchone()
                total_cost = round(cost_row["total"], 6)
        except Exception:
            total_cost = 0.0

        stats["total_cost_usd"] = total_cost
        balance = database.get_estimated_balance()

        # ── Run summary ──
        # Query llm_calls for full token breakdown — more accurate than
        # accumulating in stats because it captures every call including
        # retries. Groups by call_type prefix for readable summary.
        try:
            with database.get_connection() as conn:
                call_rows = conn.execute(
                    """
                    SELECT call_type,
                           CASE
                               WHEN model_used LIKE 'fixture:%'
                               THEN 'fixture'
                               ELSE model_used
                           END AS model_used,
                           SUM(input_tokens)  AS total_input,
                           SUM(output_tokens) AS total_output,
                           SUM(cost_usd)      AS total_cost,
                           COUNT(*)           AS call_count,
                           SUM(retried)       AS retries,
                           SUM(truncated)     AS truncations
                    FROM llm_calls
                    WHERE run_id = ?
                    GROUP BY call_type,
                           CASE
                               WHEN model_used LIKE 'fixture:%'
                               THEN 'fixture'
                               ELSE model_used
                           END
                    ORDER BY call_type
                    """,
                    (run_id,)
                ).fetchall()
        except Exception:
            call_rows = []

        total_input_all  = sum(r["total_input"]  for r in call_rows)
        total_output_all = sum(r["total_output"] for r in call_rows)
        total_retries    = sum(r["retries"]      for r in call_rows)
        total_truncations= sum(r["truncations"]  for r in call_rows)

        print("\n── Run Summary ──────────────────────────────────")
        print(f"  Run ID       — {run_id}")
        print(f"  Data mode    — {data_mode.upper()}")
        print(f"  Agent mode   — {'FIXTURE' if not config.USE_LIVE_AGENTS else 'LIVE'}")
        print(f"  Dev mode     — {'ON (Haiku)' if config.DEV_MODE else 'OFF (Sonnet)'}")
        print(f"  VIX regime   — {vix_regime}")
        print(f"  Tickers      — {stats['tickers_succeeded']} succeeded"
              f" / {stats['tickers_failed']} failed")
        
        # Compute total wall-clock duration from run start to summary print
        run_duration_secs = round(time.time() - run_start_time, 1)
        
        print(f"  Duration     — {run_duration_secs}s")
        if stale_items:
            print(f"  Stale thesis — {len(stale_items)} item(s) flagged for review")
        if correlation_breaches:
            print(f"  Correlations — {len(correlation_breaches)} threshold breach(es) — see signals table")
        print()
        print(f"  {'Call type':<28} {'Model':<10} {'In':>7} {'Out':>7} {'Cost':>8} {'Calls':>5}")
        print(f"  {'─'*28} {'─'*10} {'─'*7} {'─'*7} {'─'*8} {'─'*5}")
        for r in call_rows:
            print(
                f"  {r['call_type']:<28} "
                f"{r['model_used']:<10} "
                f"{r['total_input']:>7,} "
                f"{r['total_output']:>7,} "
                f"${r['total_cost']:>7.4f} "
                f"{r['call_count']:>5}"
            )
        print(f"  {'─'*28} {'─'*10} {'─'*7} {'─'*7} {'─'*8} {'─'*5}")
        print(
            f"  {'TOTAL':<28} {'':10} "
            f"{total_input_all:>7,} "
            f"{total_output_all:>7,} "
            f"${total_cost:>7.4f}"
        )
        print()
        if total_retries > 0:
            print(f"  [TRUNCATION] {total_retries} retries, "
                  f"{total_truncations} still truncated after retry.")
            print(f"  Consider raising token budgets for truncating agents.")
        if balance:
            print(f"  Est. balance remaining — ${balance['estimated_remaining']:.2f}")
            print(f"  Total spent to date    — ${balance['total_spent']:.4f}")
        else:
            print("  Balance — run tools/set_anthropic_balance.py to set opening balance")
        if stats["fallback_used"]:
            print("  [WARN] Fallback model was used this run.")

        # ── Consolidated warning summary ──────────────────────────────────
        # Pipe-delimited: SEVERITY | file | function() | description | fix
        # Machine-readable — copy into Excel or SQLite for trend analysis.
        # See run_warnings definition above for how to add new sources.
        # ─────────────────────────────────────────────────────────────────
        error_count   = sum(1 for w in run_warnings if w.startswith("ERROR"))
        warning_count = sum(1 for w in run_warnings if w.startswith("WARN"))
        print(f"\n── Warnings & Errors ──────────────────────────────────────")
        print(f"   Format: severity | file | function | description | fix")
        print(f"{'─' * 60}")
        if run_warnings:
            for w in run_warnings:
                print(f"  {w}")
        else:
            print("  None this run.")
        print(f"── {error_count} error(s), {warning_count} warning(s) ──"
              + "─" * 20)
        print("─" * 50)

        print(f"  Stuck runs cleared:  {stuck_count}")

        database.finish_run(run_id, status="complete", stats=stats)

    except Exception as e:
        print(f"\n[FATAL] Unexpected error: {e}")
        stats["error_count"] += 1
        database.finish_run(run_id, status="failed", stats=stats)
        raise


if __name__ == "__main__":
    main()