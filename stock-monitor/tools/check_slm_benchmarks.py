"""
tools/check_slm_benchmarks.py

PURPOSE
Answers one question: did the heavy tier benchmark (qwen3.6:35b-a3b and
gemma4:26b, at xl and xxl) already run? Reads slm_benchmarks directly.
Does not run any benchmark itself.

This is a narrowly-scoped first version of the db_inspector.py tool
that's been in the backlog since Day 16 (rollover count 4).

WHY THE PATH IS BUILT THIS WAY
Day 14: a scheduled script launched from the wrong working directory
and couldn't find prices.db, even though the database was fine. To avoid
that exact failure mode here, this script locates prices.db relative to
ITS OWN file location, not whatever directory you happen to run python
from. Works the same whether you call it from stock-monitor/ or
stock-monitor/tools/.
"""

import sqlite3
from pathlib import Path

# __file__ = this script's own path. parent.parent steps up from
# tools/ to stock-monitor/, where prices.db actually lives.
# Deliberately independent of the current working directory.
DB_PATH = Path(__file__).resolve().parent.parent / "prices.db"

HEAVY_TIER_MODELS = ("qwen3.6:35b-a3b", "gemma4:26b")


def main():
    if not DB_PATH.exists():
        # Loud failure, not a silent empty result. If this path is wrong,
        # we want to know immediately, not mistake it for "no rows found".
        print(
            f"[CHECK_SLM] ERROR: prices.db not found at {DB_PATH} — "
            f"in main() — Fix: confirm prices.db still lives in "
            f"stock-monitor/ and this script is still in stock-monitor/tools/."
        )
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name, e.g. row["model"]
    cursor = conn.cursor()

    # ?, ? placeholders, not f-string interpolation — same reason you'd
    # never concatenate raw values into SQL at the bank: avoids injection
    # and lets sqlite3 handle quoting correctly regardless of input.
    cursor.execute(
        """
        SELECT model, prompt_size, prompt_mode, input_tokens, output_tokens,
               duration_secs, tokens_per_sec, json_valid, direction_valid,
               hallucination_flag, timestamp
        FROM slm_benchmarks
        WHERE model IN (?, ?)
        ORDER BY timestamp DESC
        """,
        HEAVY_TIER_MODELS,
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("[CHECK_SLM] No heavy tier rows found in slm_benchmarks.")
        print("Conclusion: the overnight benchmark has not run (or did not write results).")
        return

    print(f"[CHECK_SLM] Found {len(rows)} heavy tier row(s):\n")
    for row in rows:
        print(
            f"  model={row['model']:<16} size={row['prompt_size']:<4} "
            f"mode={row['prompt_mode']:<10} in={row['input_tokens']:>6} "
            f"out={row['output_tokens']:>5} dur={row['duration_secs']:>7.1f}s "
            f"tok/s={(row['tokens_per_sec'] or 0):>5.2f} "
            f"json={'Y' if row['json_valid'] else 'N'} "
            f"dir={'Y' if row['direction_valid'] else 'N'} "
            f"halluc={'Y' if row['hallucination_flag'] else 'N'} "
            f"at={row['timestamp']}"
        )


if __name__ == "__main__":
    main()