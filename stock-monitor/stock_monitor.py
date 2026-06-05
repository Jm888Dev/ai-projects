# stock_monitor.py — v4
# Day 8: call_llm() wrapper + SQLite storage
# What changed from v3: TICKERS is now a dict with instrument types,
# all Claude calls go through call_llm(), database writes added to main().

import time
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf
import anthropic
import sys
from pathlib import Path

# Add ai-projects root to Python's path so shared/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.utils import extract_json, call_llm

from prompts.analyst_persona import STOCK_ANALYST_SYSTEM_PROMPT, TRANSLATOR_SYSTEM_PROMPT
import config
import database

load_dotenv()

# Initialise the Anthropic client once at module level.
# All call_llm() calls share this single client instance —
# no need to re-initialise inside every function.
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── STEP 1: FETCH PRICES ──────────────────────────────────────────────────────
def fetch_prices(tickers):
    """
    Fetch current price and previous close for each ticker using yfinance.
    tickers is now a dict: { "NVDA": "equity", "^VIX": "index", ... }
    Returns a list of dicts — one per ticker — including instrument_type.
    List format (not dict) makes it easier to pass directly to write_prices().
    Skips tickers where price data is unavailable — one failure does not
    crash the run.
    """
    results = []

    # .items() unpacks the dict into ticker + instrument_type pairs
    for ticker, instrument_type in tickers.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info

            current_price = info.last_price
            prev_close = info.previous_close

            if current_price is None or prev_close is None:
                print(f"  [SKIP] {ticker} — price data unavailable")
                continue

            pct_change = ((current_price - prev_close) / prev_close) * 100

            # instrument_type now included — stored in the database per row
            results.append({
                "ticker": ticker,
                "instrument_type": instrument_type,
                "price": round(current_price, 2),
                "prev_close": round(prev_close, 2),
                "pct_change": round(pct_change, 2),
            })

        except Exception as e:
            print(f"  [ERROR] {ticker} — {e}")

    return results


# ── STEP 2: FORMAT FOR CLAUDE ─────────────────────────────────────────────────
def format_price_data(price_data):
    """
    Convert the price list into a clean text block for the analyst prompt.
    instrument_type is included so Claude knows what kind of instrument
    it is reasoning about — equity vs index vs ETF changes the interpretation.
    """
    lines = ["Current market data:\n"]

    for row in price_data:
        direction = "+" if row["pct_change"] >= 0 else ""
        lines.append(
            f"  {row['ticker']} ({row['instrument_type']}): "
            f"${row['price']} "
            f"(prev close ${row['prev_close']}, "
            f"{direction}{row['pct_change']}%)"
        )

    return "\n".join(lines)


# ── STEP 3: ANALYST CALL ──────────────────────────────────────────────────────
def get_claude_analysis(price_text, run_id):
    """
    Sends price data to Claude via call_llm() and returns the raw response.
    call_llm() handles primary model, fallback, and graceful degradation.
    Also writes one row to llm_calls audit table per invocation.
    """
    start = time.time()

    text, usage = call_llm(
        prompt=f"{price_text}\n\nAnalyse this data and return your JSON response.",
        system=STOCK_ANALYST_SYSTEM_PROMPT,
        model=config.ANALYST_MODEL,
        max_tokens=config.ANALYST_MAX_TOKENS,
        temperature=config.ANALYST_TEMPERATURE,
        fallback_model=config.FALLBACK_MODEL,
        client=client,
    )

    duration = round(time.time() - start, 1)

    # Write audit row — one row per call_llm() invocation
    database.write_llm_call(
        run_id=run_id,
        call_type="analyst",
        model_requested=config.ANALYST_MODEL,
        model_used=usage["model_used"],
        fallback_used=usage["fallback_used"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        duration_secs=duration,
        status="fallback" if usage["fallback_used"] else "success",
    )

    return text, usage, duration


# ── STEP 3B: TRANSLATOR CALL ──────────────────────────────────────────────────
def get_plain_english_explanation(analysis_json, run_id):
    """
    Second Claude call via call_llm() — translates analyst JSON into
    plain English. The translator never sees raw prices — only conclusions.
    Chained call: analyst output becomes translator input.
    """
    start = time.time()
    analysis_text = json.dumps(analysis_json, indent=2)

    text, usage = call_llm(
        prompt=f"Here is today's market analysis. Please explain it clearly:\n\n{analysis_text}",
        system=TRANSLATOR_SYSTEM_PROMPT,
        model=config.TRANSLATOR_MODEL,
        max_tokens=config.TRANSLATOR_MAX_TOKENS,
        temperature=config.TRANSLATOR_TEMPERATURE,
        fallback_model=config.FALLBACK_MODEL,
        client=client,
    )

    duration = round(time.time() - start, 1)

    # Audit row for translator call
    database.write_llm_call(
        run_id=run_id,
        call_type="translator",
        model_requested=config.TRANSLATOR_MODEL,
        model_used=usage["model_used"],
        fallback_used=usage["fallback_used"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        duration_secs=duration,
        status="fallback" if usage["fallback_used"] else "success",
    )

    return text, usage, duration


# ── STEP 4: PARSE CLAUDE'S RESPONSE ──────────────────────────────────────────
def parse_claude_response(raw_text):
    """
    Converts Claude's raw text response into a Python dictionary.
    Uses extract_json() from shared/utils.py — the same deterministic
    cleaner used in the HDB analyser. Falls back to direct json.loads()
    if the response is clean. Returns None on total failure.
    """
    # Try shared cleaner first — handles fences, preamble, bold markers
    parsed, error = extract_json(raw_text)
    if parsed:
        return parsed

    # Direct parse as fallback — sometimes Claude returns clean JSON
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"\n[PARSE ERROR] Could not parse Claude's response: {e}")
        print(f"[RAW RESPONSE]\n{raw_text}")
        return None


# ── STEP 5: DISPLAY RESULTS ───────────────────────────────────────────────────
def display_analysis(price_data, analysis):
    """
    Prints price data and Claude's structured analysis to the terminal.
    price_data is now a list of dicts — updated from v3's dict of dicts.
    """
    print("\n" + "="*60)
    print(f"  STOCK MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    print("\n[ PRICE DATA ]\n")
    for row in price_data:
        direction = "+" if row["pct_change"] >= 0 else ""
        print(f"  {row['ticker']:<12} ${row['price']:<10} {direction}{row['pct_change']}%")

    print("\n[ CLAUDE ANALYSIS ]\n")

    if analysis is None:
        print("  Analysis unavailable — see parse error above.")
        return

    print(f"  Market Tone:        {analysis.get('market_tone', 'N/A')}")
    print(f"\n  Summary:\n  {analysis.get('session_summary', 'N/A')}")
    print(f"\n  Notable Movers:\n  {analysis.get('notable_movers', 'N/A')}")
    print(f"\n  VIX Signal:\n  {analysis.get('vix_signal', 'N/A')}")
    print(f"\n  Concentration Risk:\n  {analysis.get('concentration_risk', 'N/A')}")
    print(f"\n  Buy List Impact:\n  {analysis.get('buy_list_impact', 'N/A')}")
    print(f"\n  Watch Tomorrow:\n  {analysis.get('watch_tomorrow', 'N/A')}")

    print("\n" + "="*60 + "\n")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    # Initialise database — creates tables if they don't exist
    # Safe to call every run — IF NOT EXISTS protects existing data
    database.initialise_db()

    # Generate run_id once — passed to every write function so all rows
    # for this run are linked across prices, analysis, signals, llm_calls
    run_id = database.generate_run_id()
    database.start_run(run_id)

    # Track stats across the run — passed to finish_run() at the end
    stats = {
        "tickers_attempted": 0,
        "tickers_succeeded": 0,
        "tickers_failed": 0,
        "analyst_input_tokens": 0,
        "analyst_output_tokens": 0,
        "translator_input_tokens": 0,
        "translator_output_tokens": 0,
        "analyst_duration_secs": 0,
        "translator_duration_secs": 0,
        "fallback_used": 0,
        "error_count": 0,
    }

    try:
        # ── Fetch prices ──
        print("Fetching prices...")
        price_data = fetch_prices(config.TICKERS)
        stats["tickers_attempted"] = len(config.TICKERS)
        stats["tickers_succeeded"] = len(price_data)
        stats["tickers_failed"] = stats["tickers_attempted"] - stats["tickers_succeeded"]

        if not price_data:
            print("No price data retrieved. Check internet connection and tickers.")
            database.finish_run(run_id, status="failed", stats=stats)
            return

        print(f"  Retrieved {len(price_data)} tickers.\n")

        # ── Write prices to database ──
        database.write_prices(run_id, price_data)

        # ── Format for Claude ──
        price_text = format_price_data(price_data)

        # ── Analyst call ──
        print("Sending to analyst...")
        raw_response, analyst_usage, analyst_duration = get_claude_analysis(
            price_text, run_id
        )
        analysis = parse_claude_response(raw_response)

        # Update stats from analyst call
        stats["analyst_input_tokens"] = analyst_usage["input_tokens"]
        stats["analyst_output_tokens"] = analyst_usage["output_tokens"]
        stats["analyst_duration_secs"] = analyst_duration
        if analyst_usage["fallback_used"]:
            stats["fallback_used"] = 1

        # Write analyst output to database
        if raw_response and not raw_response.startswith("[LLM_ERROR]"):
            database.write_analysis(
                run_id=run_id,
                output_text=raw_response,
                analysis_type="analyst",
                source="stock_monitor",
            )

        # Display structured output
        display_analysis(price_data, analysis)

        # ── Translator call ──
        if analysis:
            print("Translating to plain English...\n")
            explanation, translator_usage, translator_duration = get_plain_english_explanation(
                analysis, run_id
            )

            # Update stats from translator call
            stats["translator_input_tokens"] = translator_usage["input_tokens"]
            stats["translator_output_tokens"] = translator_usage["output_tokens"]
            stats["translator_duration_secs"] = translator_duration
            if translator_usage["fallback_used"]:
                stats["fallback_used"] = 1

            # Write translator output to database
            if explanation and not explanation.startswith("[LLM_ERROR]"):
                database.write_analysis(
                    run_id=run_id,
                    output_text=explanation,
                    analysis_type="translator",
                    source="stock_monitor",
                )

            # Display plain English briefing
            print("="*60)
            print("  PLAIN ENGLISH BRIEFING")
            print("="*60)
            print(explanation)
            print("="*60 + "\n")

        # ── Run summary ──
        total_input = stats["analyst_input_tokens"] + stats["translator_input_tokens"]
        total_output = stats["analyst_output_tokens"] + stats["translator_output_tokens"]
        total_duration = round(
            stats["analyst_duration_secs"] + stats["translator_duration_secs"], 1
        )

        print("\n── Run Summary ──")
        print(f"  Run ID     — {run_id}")
        print(f"  Analyst    — input: {stats['analyst_input_tokens']:,}  output: {stats['analyst_output_tokens']:,}  duration: {stats['analyst_duration_secs']}s")
        print(f"  Translator — input: {stats['translator_input_tokens']:,}  output: {stats['translator_output_tokens']:,}  duration: {stats['translator_duration_secs']}s")
        print(f"  TOTAL      — input: {total_input:,}  output: {total_output:,}  duration: {total_duration}s")
        print(f"  Tickers    — {stats['tickers_succeeded']} succeeded / {stats['tickers_failed']} failed")
        if stats["fallback_used"]:
            print(f"  [WARN] Fallback model was used this run.")

        # Close the run log — status complete
        database.finish_run(run_id, status="complete", stats=stats)

    except Exception as e:
        # Something unexpected failed — log it, mark run as failed
        print(f"\n[FATAL] Unexpected error: {e}")
        stats["error_count"] += 1
        database.finish_run(run_id, status="failed", stats=stats)
        raise


if __name__ == "__main__":
    main()