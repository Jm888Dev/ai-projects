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

Please provide:
1. A brief summary of today's overall market tone (2-3 sentences)
2. Notable movers — any ticker up or down more than 1%, with a possible reason
3. Supply chain read — how are NVDA, AVGO, LITE, TSM moving relative to each other?
4. Concentration risk flag — if SMH, NVDA, and TSM are all moving in the same direction, flag it
5. One question worth watching tomorrow

Keep the analysis concise and grounded in the data provided."""

    print("\nSending to Claude for analysis...")

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("MACK STOCK MONITOR — Day 2")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    price_data = fetch_prices(ALL_TICKERS)

    if not price_data:
        print("No price data retrieved. Exiting.")
        return

    price_summary = format_for_claude(price_data)

    analysis = get_claude_analysis(price_summary)

    print("\n" + "=" * 60)
    print("CLAUDE'S ANALYSIS")
    print("=" * 60)
    print(analysis)
    print("=" * 60)

if __name__ == "__main__":
    main()