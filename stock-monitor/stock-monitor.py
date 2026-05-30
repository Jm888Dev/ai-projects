import anthropic
import yfinance as yf
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ── TICKERS ──────────────────────────────────────────────────────────────────
EQUITIES = ["NVDA", "AVGO", "LITE", "TSM"]
ETFS = ["G3B.SI", "QQQ", "SMH"]
MACRO = ["^VIX"]

ALL_TICKERS = EQUITIES + ETFS + MACRO

# ── FETCH PRICES ─────────────────────────────────────────────────────────────
def fetch_prices(tickers):
    print(f"\nFetching prices for: {', '.join(tickers)}")
    results = []

    for ticker in tickers:
        try:
            data = yf.Ticker(ticker)
            info = data.fast_info
            price = round(info.last_price, 2)
            prev_close = round(info.previous_close, 2)
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)
            results.append({
                "ticker": ticker,
                "price": price,
                "prev_close": prev_close,
                "change_pct": change_pct
            })
            print(f"  {ticker}: ${price} ({change_pct:+.2f}%)")
        except Exception as e:
            print(f"  {ticker}: Failed to fetch — {e}")

    return results

# ── FORMAT FOR CLAUDE ─────────────────────────────────────────────────────────
def format_for_claude(price_data):
    lines = []
    for item in price_data:
        direction = "up" if item["change_pct"] > 0 else "down"
        lines.append(
            f"{item['ticker']}: ${item['price']} ({direction} {abs(item['change_pct'])}% from previous close of ${item['prev_close']})"
        )
    return "\n".join(lines)

# ── CLAUDE ANALYSIS ───────────────────────────────────────────────────────────
def get_claude_analysis(price_summary):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""You are a market analyst monitoring a portfolio of technology stocks, ETFs, and macro indicators.

Today's date: {datetime.now().strftime("%A, %d %B %Y")}

Here is the latest price data:
{price_summary}

Context on the portfolio structure:
- NVDA, AVGO, LITE, TSM form a semiconductor supply chain (demand anchor → network → photonics → production)
- G3B.SI is the Singapore STI ETF — local dividend stability anchor
- QQQ is Nasdaq-100 — broad US tech exposure
- SMH is a semiconductor ETF — note it overlaps with NVDA and TSM (concentration risk)
- ^VIX is the fear gauge — spikes signal risk-off conditions

Please respond with ONLY a JSON object. No preamble, no explanation, no markdown code fences.
    Return exactly this structure:

    {{
        "market_tone": "one sentence summary of overall market mood",
        "notable_movers": ["list", "of", "tickers", "moving", "more", "than", "1%", "with", "brief", "reason"],
        "vix_signal": "one sentence interpreting the VIX level and what it means",
        "concentration_risk": "one sentence on whether SMH, NVDA, TSM are moving together and whether that is a concern",
        "watch_tomorrow": "one question worth monitoring in the next session"
    }}"""

    print("\nSending to Claude for analysis...")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

# ── PARSE CLAUDE RESPONSE ─────────────────────────────────────────────────────
def parse_claude_response(raw_text):
    # Import json here — it's a built-in Python library, no pip install needed
    import json

    try:
        # Remove leading/trailing whitespace first
        cleaned = raw_text.strip()

        # Claude sometimes wraps JSON in markdown code fences like ```json ... ```
        # We strip those out so json.loads() sees clean JSON, not backticks
        if cleaned.startswith("```"):
            # Remove the first line (```json or ```) and the last line (```)
            cleaned = "\n".join(cleaned.split("\n")[1:-1]).strip()

        # json.loads() converts a JSON string into a Python dictionary
        # This is the moment text becomes data — a dict we can query by key
        parsed = json.loads(cleaned)

        return parsed

    except json.JSONDecodeError as e:
        # If Claude returned something that isn't valid JSON, we catch it here
        # We print the error and the raw text so you can see what went wrong
        # Returning None signals to the caller that parsing failed
        print(f"\nJSON parse failed: {e}")
        print(f"Raw response was:\n{raw_text}")
        return None

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("MACK STOCK MONITOR — Day 3")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    price_data = fetch_prices(ALL_TICKERS)

    if not price_data:
        print("No price data retrieved. Exiting.")
        return

    price_summary = format_for_claude(price_data)

 # Get the raw text response from Claude
    raw_analysis = get_claude_analysis(price_summary)

    # Attempt to parse Claude's response into a Python dictionary
    parsed = parse_claude_response(raw_analysis)

    print("\n" + "=" * 60)
    print("CLAUDE'S ANALYSIS")
    print("=" * 60)

    if parsed:
        # parsed is now a dict — we access each field by its key name
        # This is what "structured output" means — individual fields, not a blob of text
        print(f"Market Tone     : {parsed.get('market_tone', 'N/A')}")
        print(f"VIX Signal      : {parsed.get('vix_signal', 'N/A')}")
        print(f"Concentration   : {parsed.get('concentration_risk', 'N/A')}")
        print(f"Watch Tomorrow  : {parsed.get('watch_tomorrow', 'N/A')}")

        # notable_movers is a list — we print each item on its own line
        print(f"\nNotable Movers:")
        for mover in parsed.get('notable_movers', []):
            print(f"  • {mover}")
    else:
        # Parsing failed — fall back to printing the raw text so you still see something
        print("Could not parse structured response. Raw output:")
        print(raw_analysis)

    print("=" * 60)

if __name__ == "__main__":
    main()