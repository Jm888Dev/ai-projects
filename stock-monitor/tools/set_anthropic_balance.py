# tools/set_balance.py
# Run this whenever you top up your Anthropic API credit.
# Updates the local balance ledger so the run summary shows
# an accurate estimated remaining balance.
#
# Usage:
#   python tools/set_balance.py
#
# You will be prompted to enter the amount showing in your
# Anthropic console at console.anthropic.com/settings/billing

import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCK_MONITOR = os.path.join(ROOT, "stock-monitor")
sys.path.insert(0, ROOT)
sys.path.insert(0, STOCK_MONITOR)

import database

database.initialise_db()

print("\n── Set Anthropic API Balance ──────────────────────")
print("  Check your current balance at:")
print("  console.anthropic.com → Billing")
print("─" * 50)

try:
    amount = float(input("\n  Enter current balance in USD (e.g. 18.50): $"))
    note   = input("  Note (optional, press Enter to skip): ").strip()
    if not note:
        note = "Manual balance entry"

    # Get current estimated balance to compute the adjustment needed
    # We log the difference so the ledger stays accurate
    current = database.get_estimated_balance()
    current_estimate = current["estimated_remaining"] if current else 0.0

    # The adjustment is the difference between what console shows
    # and what our local estimate thinks we have
    adjustment = round(amount - current_estimate, 4)

    database.log_balance_topup(adjustment, note)

    print(f"\n  Balance set to ${amount:.2f}")
    print(f"  Adjustment logged: ${adjustment:+.4f}")
    print("─" * 50 + "\n")

except ValueError:
    print("\n  [ERROR] Please enter a number — e.g. 18.50")
except Exception as e:
    print(f"\n  [ERROR] {e}")