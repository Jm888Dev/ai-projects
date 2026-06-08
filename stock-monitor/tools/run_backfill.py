# tools/run_backfill.py
# One-time script to backfill 5 years of daily market history.
# Run once from the stock-monitor folder with myenv active.
# Safe to re-run — INSERT OR IGNORE prevents duplicates.
# After this, update_market_history() in each session only
# pulls the delta since the last stored date.

import sys
import os

# Add the project root to the path so shared/ and database are importable
# Walk up two levels: tools/ → stock-monitor/ → ai-projects/
# shared/ lives at the ai-projects/ level
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCK_MONITOR = os.path.join(ROOT, "stock-monitor")

# Add both to path:
# ROOT gives access to shared/
# STOCK_MONITOR gives access to config and database
sys.path.insert(0, ROOT)
sys.path.insert(0, STOCK_MONITOR)

import config
import database
from shared.utils import update_market_history

# Initialise the database first — creates tables if not already there
database.initialise_db()

# Run the backfill in live mode regardless of USE_LIVE_DATA flag —
# this is a one-time setup, not a per-session pipeline call
print("Starting 5-year backfill — this will take 1-2 minutes...")
print(f"Tickers: {list(config.TICKERS.keys())}")
print("-" * 50)

update_market_history(
    tickers=list(config.TICKERS.keys()),
    use_live=True   # always live for the backfill
)

print("-" * 50)
print("Backfill complete. Run check_tables.py to verify row counts.")