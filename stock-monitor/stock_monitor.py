# stock_monitor.py — v3
# Day 4: System prompts and personas
# What changed from v2: portfolio context moved into a dedicated system prompt.
# The user message now contains only live price data — clean separation of concerns.

import anthropic          # Claude API client
import yfinance as yf     # Yahoo Finance data wrapper
import json               # For parsing Claude's JSON response
import os                 # For reading environment variables
from datetime import datetime          # For timestamping the output
from dotenv import load_dotenv         # For loading the .env API key file

# Import the analyst persona we wrote in prompts/analyst_persona.py
# This is the standing brief — who Claude is and what rules it follows
# Import both personas — analyst for structured output, translator for plain English
from prompts.analyst_persona import STOCK_ANALYST_SYSTEM_PROMPT, TRANSLATOR_SYSTEM_PROMPT
from config import (
        ANALYST_MODEL,          # Sonnet - used in analyst call
        TRANSLATOR_MODEL,       # Haiku - used in translator call
        ANALYST_MAX_TOKENS,     # Token budget for analyst response
        TRANSLATOR_MAX_TOKENS,  # Token budget for translator response
        ANALYST_TEMPERATURE,    # Low - keeps analysis factual
        TRANSLATOR_TEMPERATURE, # Slightly higher - variance is better for natural language
        TICKERS,                # Full tracking universee
)

# Load the API key from the .env file into environment variables
load_dotenv()

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
# All tickers in one place — easy to add or remove without touching logic below
tickers = TICKERS   # Imported from config.py

# ── STEP 1: FETCH PRICES ──────────────────────────────────────────────────────
def fetch_prices(tickers):
    """
    Fetch current price and previous close for each ticker using yfinance.
    Returns a dict: { "NVDA": { "price": 120.5, "prev_close": 119.2, "change_pct": 1.09 }, ... }
    If a ticker fails, it is skipped — one bad ticker does not crash the run.
    """
    results = {}

    for ticker in tickers:
        try:
            # yf.Ticker creates an object representing one instrument
            stock = yf.Ticker(ticker)

            # fast_info is the quickest way to get current price data
            # It returns a lightweight object — not the full historical dataset
            info = stock.fast_info

            current_price = info.last_price      # Most recent traded price
            prev_close = info.previous_close     # Yesterday's closing price

            # Guard against None values — some tickers return null outside market hours
            if current_price is None or prev_close is None:
                print(f"  [SKIP] {ticker} — price data unavailable")
                continue

            # Calculate percentage change from previous close to current price
            change_pct = ((current_price - prev_close) / prev_close) * 100

            results[ticker] = {
                "price": round(current_price, 2),
                "prev_close": round(prev_close, 2),
                "change_pct": round(change_pct, 2)
            }

        except Exception as e:
            # If anything goes wrong with this ticker, log it and keep going
            print(f"  [ERROR] {ticker} — {e}")

    return results

# ── STEP 2: FORMAT FOR CLAUDE ─────────────────────────────────────────────────
def format_price_data(prices):
    """
    Convert the price dictionary into a clean text block for the user message.
    This is ALL the user message contains — just today's numbers.
    The analyst already knows the portfolio context from the system prompt.
    """
    lines = ["Current market data:\n"]

    for ticker, data in prices.items():
        # Format each ticker as a readable line with price and percentage move
        direction = "+" if data["change_pct"] >= 0 else ""
        lines.append(
            f"  {ticker}: ${data['price']} "
            f"(prev close ${data['prev_close']}, "
            f"{direction}{data['change_pct']}%)"
        )

    return "\n".join(lines)

# ── STEP 3: CALL CLAUDE ───────────────────────────────────────────────────────
def get_claude_analysis(price_text):
    """
    Send the price data to Claude and return its raw text response.
    The system= parameter carries the analyst persona — separate from the query.
    The user message carries only the live data — clean and minimal.
    """
    # Initialise the Anthropic client using the API key from .env
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=ANALYST_MODEL,   # Sonnet - used in analyst call
        max_tokens=ANALYST_MAX_TOKENS,
        temperature=ANALYST_TEMPERATURE,

        system=STOCK_ANALYST_SYSTEM_PROMPT,  # Standing brief — the analyst persona
        messages=[
            {
                "role": "user",
                # The user message is now just the data — no context, no rules repeated
                "content": f"{price_text}\n\nAnalyse this data and return your JSON response."
            }
        ]
    )

    # Extract the text from Claude's response object
    return response.content[0].text


# ── STEP 3B: TRANSLATE ANALYSIS INTO PLAIN ENGLISH ───────────────────────────
def get_plain_english_explanation(analysis_json):
    """
    Second Claude call — takes the analyst's structured JSON and explains it
    in plain English for a first-time investor.
    The translator never sees raw prices — only the analyst's conclusions.
    This is a chained call: output of call 1 becomes input of call 2.
    """
    # Initialise a fresh client — same pattern as the analyst call
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Convert the parsed dictionary back into a JSON string to pass to the translator
    # The translator receives the analyst's full structured output as its input
    analysis_text = json.dumps(analysis_json, indent=2)

    response = client.messages.create(
        model=TRANSLATOR_MODEL,
        max_tokens=TRANSLATOR_MAX_TOKENS,
        temperature=TRANSLATOR_TEMPERATURE,

        system=TRANSLATOR_SYSTEM_PROMPT,     # The educator persona
        messages=[
            {
                "role": "user",
                "content": f"Here is today's market analysis. Please explain it clearly:\n\n{analysis_text}"
            }
        ]
    )

    return response.content[0].text

# ── STEP 4: PARSE CLAUDE'S JSON RESPONSE ─────────────────────────────────────
def parse_claude_response(raw_text):
    """
    Convert Claude's raw text response into a Python dictionary.
    Claude sometimes wraps JSON in markdown code fences — this handles that.
    Returns the parsed dict, or None if parsing fails entirely.
    """
    # First attempt: try parsing the raw response directly
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Second attempt: strip markdown code fences if Claude added them
    # Claude sometimes returns ```json ... ``` — we strip the wrapper and retry
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            # Remove the opening fence (```json or just ```)
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            # Remove the closing fence
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        # If both attempts fail, log the error and the raw response for debugging
        print(f"\n[PARSE ERROR] Could not parse Claude's response: {e}")
        print(f"[RAW RESPONSE]\n{raw_text}")
        return None

# ── STEP 5: DISPLAY RESULTS ───────────────────────────────────────────────────
def display_analysis(prices, analysis):
    """
    Print the price data and Claude's structured analysis to the terminal.
    Each field is printed individually — we're reading from a Python dict, not prose.
    """
    print("\n" + "="*60)
    print(f"  STOCK MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    # Print raw price data first so you can see what Claude was given
    print("\n[ PRICE DATA ]\n")
    for ticker, data in prices.items():
        direction = "+" if data["change_pct"] >= 0 else ""
        print(f"  {ticker:<12} ${data['price']:<10} {direction}{data['change_pct']}%")

    # Print Claude's structured analysis field by field
    print("\n[ CLAUDE ANALYSIS ]\n")

    if analysis is None:
        print("  Analysis unavailable — see parse error above.")
        return

    # .get() is used throughout — if Claude skips a field, we get a fallback
    # instead of a KeyError crash
    print(f"  Market Tone:        {analysis.get('market_tone', 'N/A')}")
    print(f"\n  Summary:\n  {analysis.get('session_summary', 'N/A')}")
    print(f"\n  Notable Movers:\n  {analysis.get('notable_movers', 'N/A')}")
    print(f"\n  VIX Signal:\n  {analysis.get('vix_signal', 'N/A')}")
    print(f"\n  Concentration Risk:\n  {analysis.get('concentration_risk', 'N/A')}")
    print(f"\n  Buy List Impact:\n  {analysis.get('buy_list_impact', 'N/A')}")
    print(f"\n  Watch Tomorrow:\n  {analysis.get('watch_tomorrow', 'N/A')}")

    print("\n" + "="*60 + "\n")

# ── MAIN — wires all steps together ───────────────────────────────────────────
# ── MAIN — wires all steps together ───────────────────────────────────────────
def main():
    print("Fetching prices...")
    prices = fetch_prices(TICKERS)

    if not prices:
        print("No price data retrieved. Check your internet connection and ticker symbols.")
        return

    print(f"  Retrieved {len(prices)} tickers.\n")

    # Format prices into clean text for the analyst
    price_text = format_price_data(prices)

    # First Claude call — analyst returns structured JSON
    print("Sending to analyst...")
    raw_response = get_claude_analysis(price_text)
    analysis = parse_claude_response(raw_response)

    # Display the structured analyst output as before
    display_analysis(prices, analysis)

    # Second Claude call — translator explains the JSON in plain English
    # Only runs if the first call succeeded and returned valid data
    if analysis:
        print("Translating for plain English explanation...\n")
        explanation = get_plain_english_explanation(analysis)

        # Print the translator's output as a clearly separate section
        print("="*60)
        print("  PLAIN ENGLISH BRIEFING")
        print("="*60)
        print(explanation)
        print("="*60 + "\n")

# Standard Python entry point — only runs main() if this file is executed directly
if __name__ == "__main__":
    main()