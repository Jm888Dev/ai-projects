# shared/data_sources.py
# Abstracts all external data reads behind a single interface.
# Every input to the pipeline goes through one of these functions.
#
# USE_LIVE_DATA in config.py controls the mode:
#   False = read from fixtures (development, prompt tuning, testing)
#   True  = fetch from live sources (production, real sessions)
#
# This means the agents never know whether they are reading fixtures
# or live data. The pipeline code is identical in both modes.
# Swap one config flag — nothing else changes.

import os
import json
import sys

# Ensure shared/ and stock-monitor/ are on the path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_MONITOR = os.path.join(ROOT, "stock-monitor")
sys.path.insert(0, ROOT)
sys.path.insert(0, STOCK_MONITOR)

import config


# ─────────────────────────────────────────────────────────────
# FIXTURE LOADER
# ─────────────────────────────────────────────────────────────

def _load_fixture(filename):
    """
    Loads a JSON fixture file from the fixtures/ directory.
    fixtures/ lives in stock-monitor/ alongside config.py.
    Raises FileNotFoundError with a clear message if missing —
    better to fail loudly than return silent empty data.
    """
    # Build path: stock-monitor/fixtures/filename
    fixtures_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "stock-monitor",
        "fixtures"
    )
    filepath = os.path.join(fixtures_dir, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"[data_sources] Fixture not found: {filepath}\n"
            f"Create it or set USE_LIVE_DATA=True in config.py"
        )

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# PRICE DATA
# ─────────────────────────────────────────────────────────────

def get_current_prices(tickers, use_live=None):
    """
    Returns current price data for all tickers as a list of dicts.
    Each dict contains: ticker, instrument_type, price,
    prev_close, pct_change.

    use_live=None reads from config.USE_LIVE_DATA.
    use_live=True forces live fetch regardless of config.
    use_live=False forces fixture regardless of config.

    Live mode fetches from yfinance.
    Fixture mode reads from fixtures/normal_day.json.
    """
    if use_live is None:
        use_live = config.USE_LIVE_DATA

    if use_live:
        return _fetch_live_prices(tickers)
    else:
        print("[data_sources] Price mode: fixture")
        data = _load_fixture("normal_day.json")
        return data["prices"]


def _fetch_live_prices(tickers):
    """
    Fetches live prices from yfinance for all tickers.
    Gracefully handles failed tickers — logs and continues.
    Returns a list of dicts in the same shape as the fixture.
    """
    import yfinance as yf

    print("[data_sources] Price mode: live")
    results = []

    for ticker, instrument_type in tickers.items():
        try:
            info = yf.Ticker(ticker).fast_info
            price      = getattr(info, "last_price",      None)
            prev_close = getattr(info, "previous_close",  None)

            pct_change = None
            if price is not None and prev_close and prev_close != 0:
                pct_change = round(((price - prev_close) / prev_close) * 100, 4)

            # Fetch volume data for Pragmatist conviction signal
            # volume_vs_avg compares today's volume to 30-day average
            # volume_signal classifies as elevated/normal/low
            # ^VIX and ETFs may not have meaningful volume — handled gracefully
            try:
                volume = int(getattr(info, "three_month_average_volume", 0) or 0)
                avg_volume = int(getattr(info, "three_month_average_volume", 0) or 0)
                day_volume = int(getattr(info, "last_volume", 0) or 0)

                if avg_volume and avg_volume > 0 and day_volume > 0:
                    volume_vs_avg = round(day_volume / avg_volume, 2)
                    if volume_vs_avg > 1.5:
                        volume_signal = "elevated"
                    elif volume_vs_avg < 0.7:
                        volume_signal = "low"
                    else:
                        volume_signal = "normal"
                else:
                    day_volume     = None
                    volume_vs_avg  = None
                    volume_signal  = "unavailable"
            except Exception:
                day_volume    = None
                volume_vs_avg = None
                volume_signal = "unavailable"

            results.append({
                "ticker":          ticker,
                "instrument_type": instrument_type,
                "price":           round(price, 4) if price else None,
                "prev_close":      round(prev_close, 4) if prev_close else None,
                "pct_change":      pct_change,
                "volume":          day_volume,
                "volume_vs_avg":   volume_vs_avg,
                "volume_signal":   volume_signal,
            })

            status = f"{price:.2f} ({pct_change:+.2f}%)" if price else "no data"
            print(f"[data_sources] {ticker}: {status}")

        except Exception as e:
            print(f"[data_sources] {ticker}: fetch failed — {e}")
            results.append({
                "ticker":          ticker,
                "instrument_type": instrument_type,
                "price":           None,
                "prev_close":      None,
                "pct_change":      None,
            })

    return results


# ─────────────────────────────────────────────────────────────
# INTELLIGENCE CONTEXT
# ─────────────────────────────────────────────────────────────

def get_intelligence_context(use_live=None):
    """
    Returns the intelligence context block for the current session.
    Contains: macro_regime, geopolitical_signals, ai_research_signals,
    regulatory_signals, sentiment_signals.

    Live mode: reads from intelligence.py (manual stub for now,
    automated RSS pipeline on Day 13-15).
    Fixture mode: reads from fixtures/normal_day.json intelligence block.
    """
    if use_live is None:
        use_live = config.USE_LIVE_DATA

    if use_live:
        print("[data_sources] Intelligence mode: live stub")
        from intelligence import INTELLIGENCE_CONTEXT_TODAY
        return INTELLIGENCE_CONTEXT_TODAY
    else:
        print("[data_sources] Intelligence mode: fixture")
        data = _load_fixture("normal_day.json")
        return data["intelligence"]