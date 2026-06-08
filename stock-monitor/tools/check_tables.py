# tools/check_tables.py
# Verifies database tables exist and shows row counts.
# Run any time to inspect the state of prices.db.

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCK_MONITOR = os.path.join(ROOT, "stock-monitor")
sys.path.insert(0, ROOT)
sys.path.insert(0, STOCK_MONITOR)

import sqlite3
import config

conn = sqlite3.connect(config.DB_PATH)

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print(f"\n{'TABLE':<25} {'ROWS':>8}")
print("-" * 35)

for (table,) in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:<25} {count:>8,}")

print("-" * 35)
conn.close()