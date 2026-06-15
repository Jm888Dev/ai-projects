# tools/reset_db.py
# Full database reset — delete, reinitialise, backfill.
# Use when schema changes require a clean slate.
# WARNING: destroys all existing data including run history.
# Safe to run during development. Do NOT run in production.
#
# Usage:
#   python tools/reset_db.py

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCK_MONITOR = os.path.join(ROOT, "stock-monitor")
sys.path.insert(0, ROOT)
sys.path.insert(0, STOCK_MONITOR)

import config
import database
from shared.utils import update_market_history

# ── Safety confirmation ───────────────────────────────────────
# Stops accidental runs — one extra keystroke protects your data
print("\n── Database Reset ───────────────────────────────────")
print(f"  Target: {config.DB_PATH}")
print("  This will DELETE all existing data and backfill")
print("  market_history from scratch (5 years, ~10,000 rows).")
print("─" * 50)
confirm = input("\n  Type YES (cap-sensitive) to continue: ").strip()

if confirm != "YES":
    print("  Cancelled.")
    sys.exit(0)

# ── Step 1: Backup then delete existing database ─────────────
import shutil
from datetime import datetime

if os.path.exists(config.DB_PATH):
    backup_dir = r"C:\AI_Projects\backups\stock-monitor"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"prices_{timestamp}.db")
    shutil.copy2(config.DB_PATH, backup_path)
    print(f"\n  [1/3] Backed up to {backup_path}")
    os.remove(config.DB_PATH)
    print(f"        Deleted {config.DB_PATH}")
else:
    print(f"\n  [1/3] No existing database found — skipping backup and delete")

# ── Step 2: Reinitialise schema ───────────────────────────────
database.initialise_db()
print("  [2/3] Schema initialised — all tables created")

# ── Step 3: Backfill market history ──────────────────────────
print("  [3/3] Starting 5-year backfill...")
print(f"        Tickers: {list(config.TICKERS.keys())}")
print("─" * 50)

update_market_history(
    tickers=list(config.TICKERS.keys()),
    use_live=True
)

print("─" * 50)
print("  Reset complete. Run check_tables.py to verify. Remember to set_anthropic_balance before running stock_monitor.\n")