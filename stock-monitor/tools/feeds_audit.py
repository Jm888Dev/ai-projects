# tools/feeds_audit.py
# Feed source health auditor.
# Tests all sources in config.FEED_SOURCES and prints a status report.
# Run this periodically to catch broken feeds before they silently
# fail in production.
#
# Usage (from stock-monitor/):
#   python tools/feeds_audit.py
#   python tools/feeds_audit.py --fix   (prints suggested replacements)

import sys
from pathlib import Path
import feedparser
import argparse

# Add project root to path so config is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

def audit_feeds(verbose=False):
    """
    Tests every source in config.FEED_SOURCES.
    Returns a list of result dicts with status, entry count, and error.
    """
    results = []

    print(f"\nFeed Source Health Audit — {len(config.FEED_SOURCES)} sources\n")
    print(f"  {'Status':<8} {'Entries':>7} {'Bozo':>6}  {'Source':<30} URL")
    print(f"  {'─'*8} {'─'*7} {'─'*6}  {'─'*30} {'─'*40}")

    ok_count      = 0
    warn_count    = 0
    failed_count  = 0

    for source in config.FEED_SOURCES:
        name   = source["name"]
        url    = source["url"]
        domain = source["domain"]

        feed = feedparser.parse(url)

        entry_count = len(feed.entries)
        bozo        = feed.bozo
        bozo_ex     = str(feed.get("bozo_exception", "")) if bozo else ""

        if not bozo and entry_count > 0:
            status = "OK"
            ok_count += 1
        elif bozo and entry_count > 0:
            status = "WARN"
            warn_count += 1
        else:
            status = "FAILED"
            failed_count += 1

        results.append({
            "name":       name,
            "domain":     domain,
            "url":        url,
            "status":     status,
            "entries":    entry_count,
            "bozo":       bozo,
            "bozo_ex":    bozo_ex,
        })

        status_display = {
            "OK":     "OK    ",
            "WARN":   "WARN  ",
            "FAILED": "FAILED",
        }[status]

        print(f"  {status_display:<8} {entry_count:>7} {str(bozo):>6}  "
              f"{name:<30} {url[:60]}")

        if verbose and bozo_ex:
            print(f"           Error: {bozo_ex[:80]}")

    print(f"\n  {'─'*80}")
    print(f"  OK: {ok_count}  |  WARN (entries but bozo): {warn_count}"
          f"  |  FAILED: {failed_count}"
          f"  |  Total: {len(config.FEED_SOURCES)}")

    failed = [r for r in results if r["status"] == "FAILED"]
    if failed:
        print(f"\n  FAILED sources — update URLs in config.py:")
        for r in failed:
            print(f"    [{r['domain'].upper()}] {r['name']}")
            print(f"      Current URL: {r['url']}")
            print(f"      Error:       {r['bozo_ex'][:100]}")

    print()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audit RSS feed sources in config.FEED_SOURCES"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print error details for bozo feeds"
    )
    args = parser.parse_args()
    audit_feeds(verbose=args.verbose)