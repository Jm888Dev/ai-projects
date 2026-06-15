# feeds.py
# Intelligence feed ingestion — Stage 1 only.
# Fetches RSS headlines, scores relevance, stores to feeds table.
# Builds the injection string for build_data_package() per ticker.
#
# Stage 1 rule — NON-NEGOTIABLE:
#   No model reads feed content in this file.
#   Agents receive only the injected headline string built here.
#   Feed Stage 2 (agent consumption of full content) is gated
#   on Day 42 red-team completion.
#
# Three public functions called by stock_monitor.py:
#   fetch_and_store_feeds()  — fetch all 22 sources, store to DB
#   get_relevant_headlines() — score + filter for one ticker
#   build_feed_injection()   — format headlines for data package

import feedparser
import sqlite3
from datetime import datetime
from pathlib import Path
import sys
import config

# Import format_warning from shared/utils.py
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from utils import format_warning


def _score_headline(title, summary, ticker):
    """
    Scores a single headline against the keyword list for a ticker.
    Checks both title and summary — summary catches context the
    title omits. Case-insensitive. Returns match count (int).
    A score of 0 means no keywords matched — filtered out at injection.
    """
    keywords = config.FEED_KEYWORDS.get(ticker, [])
    if not keywords:
        return 0

    text = f"{title} {summary or ''}".lower()
    return sum(1 for kw in keywords if kw.lower() in text)


def _get_tickers_matched(title, summary):
    """
    Returns a comma-separated string of all tickers whose keywords
    appear in this headline. Used to populate tickers_matched column
    so we can query 'which headlines mentioned NVDA' without re-scoring.
    """
    matched = []
    text = f"{title} {summary or ''}".lower()
    for ticker, keywords in config.FEED_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            matched.append(ticker)
    return ",".join(matched) if matched else None


def fetch_and_store_feeds():
    """
    Fetches all 22 RSS sources from config.FEED_SOURCES.
    Parses each feed, scores every headline, stores to feeds table.
    Deduplication is handled by the UNIQUE constraint on url —
    INSERT OR IGNORE silently skips headlines already stored.
    Returns a summary dict: sources_attempted, sources_ok,
    sources_failed, headlines_fetched, headlines_new.
    Called once per pipeline run before build_data_package().
    """
    summary = {
        "sources_attempted": 0,
        "sources_ok":        0,
        "sources_failed":    0,
        "headlines_fetched": 0,
        "headlines_new":     0,
    }

    db_path = config.DB_PATH
    fetched_at = datetime.now().isoformat()

    for source in config.FEED_SOURCES:
        summary["sources_attempted"] += 1
        name   = source["name"]
        domain = source["domain"]
        url    = source["url"]

        try:
            # feedparser.parse() never raises — it returns a feed object
            # with a bozo flag if something went wrong (malformed XML,
            # network error, timeout). We check bozo_exception explicitly.
            feed = feedparser.parse(url)

            if feed.bozo and not feed.entries:
                # bozo=True means feedparser hit a problem parsing the XML.
                # If entries is also empty, there is nothing useful to store.
                print(format_warning(
                    "WARN", "feeds.py", "fetch_and_store_feeds()",
                    f"feed parse error for '{name}' ({url}) "
                    f"— bozo_exception: {feed.get('bozo_exception', 'unknown')}",
                    "check the RSS URL is still valid and the source is online"
                ))
                summary["sources_failed"] += 1
                continue

            entries_this_source = 0
            new_this_source     = 0

            for entry in feed.entries:
                title   = getattr(entry, "title",   "") or ""
                url_entry = getattr(entry, "link",  "") or ""
                published = getattr(entry, "published", None)
                summary_text = getattr(entry, "summary", "") or ""

                # Skip entries with no URL — cannot deduplicate without it
                if not url_entry:
                    continue

                # Score against all tickers to get relevance and matched list
                # Use max score across all tickers as the row-level score
                max_score = 0
                for ticker in config.FEED_KEYWORDS:
                    score = _score_headline(title, summary_text, ticker)
                    if score > max_score:
                        max_score = score

                tickers_matched = _get_tickers_matched(title, summary_text)
                entries_this_source += 1

                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO feeds
                            (fetched_at, source, domain, title, url,
                             published, summary, relevance_score,
                             tickers_matched)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fetched_at, name, domain, title, url_entry,
                            published, summary_text[:500],
                            max_score, tickers_matched,
                        ),
                    )
                    if cursor.rowcount == 1:
                        # rowcount=1 means the INSERT went through (not ignored)
                        new_this_source += 1
                    conn.commit()
                    conn.close()

                except Exception as e:
                    print(format_warning(
                        "WARN", "feeds.py", "fetch_and_store_feeds()",
                        f"failed to store headline '{title[:60]}' "
                        f"from '{name}' — {e}",
                        "check prices.db is not locked by another process"
                    ))
                    if conn:
                        conn.close()

            summary["headlines_fetched"] += entries_this_source
            summary["headlines_new"]     += new_this_source
            summary["sources_ok"]        += 1

            print(f"[FEEDS] {name}: {entries_this_source} fetched, "
                  f"{new_this_source} new")

        except Exception as e:
            print(format_warning(
                "WARN", "feeds.py", "fetch_and_store_feeds()",
                f"failed to fetch feed '{name}' ({url}) — {e}",
                "check network connectivity and that the URL is reachable"
            ))
            summary["sources_failed"] += 1

    print(f"\n[FEEDS] Fetch complete — "
          f"{summary['sources_ok']}/{summary['sources_attempted']} sources OK, "
          f"{summary['headlines_new']} new headlines stored")

    return summary


def get_relevant_headlines(ticker, limit_per_domain=None, threshold=None):
    """
    Queries the feeds table for headlines relevant to a ticker.
    Filters by relevance_score >= threshold (default: FEED_RELEVANCE_THRESHOLD).
    Returns top N per domain by score (default: FEED_MAX_HEADLINES_PER_DOMAIN).
    Total capped at FEED_MAX_TOTAL_HEADLINES across all domains.
    Returns a list of dicts: {title, source, domain, published, url}
    Called by build_feed_injection() — not called directly by pipeline.
    """
    if limit_per_domain is None:
        limit_per_domain = config.FEED_MAX_HEADLINES_PER_DOMAIN
    if threshold is None:
        threshold = config.FEED_RELEVANCE_THRESHOLD

    results = []

    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row

        # Get distinct domains that have relevant headlines for this ticker
        domains = conn.execute(
            """
            SELECT DISTINCT domain FROM feeds
            WHERE relevance_score >= ?
            AND (tickers_matched LIKE ? OR tickers_matched LIKE ?
                 OR tickers_matched LIKE ? OR tickers_matched = ?)
            """,
            (threshold,
             f"{ticker},%",    # ticker at start of list
             f"%,{ticker},%",  # ticker in middle
             f"%,{ticker}",    # ticker at end
             ticker),          # ticker is the only entry
        ).fetchall()

        for domain_row in domains:
            domain = domain_row["domain"]

            # Top N headlines for this ticker in this domain, by relevance score
            rows = conn.execute(
                """
                SELECT title, source, domain, published, url, summary
                FROM feeds
                WHERE domain = ?
                AND relevance_score >= ?
                AND (tickers_matched LIKE ? OR tickers_matched LIKE ?
                     OR tickers_matched LIKE ? OR tickers_matched = ?)
                ORDER BY relevance_score DESC, fetched_at DESC
                LIMIT ?
                """,
                (domain, threshold,
                 f"{ticker},%", f"%,{ticker},%",
                 f"%,{ticker}", ticker,
                 limit_per_domain),
            ).fetchall()

            for row in rows:
                results.append(dict(row))

                # Stop at hard cap
                if len(results) >= config.FEED_MAX_TOTAL_HEADLINES:
                    conn.close()
                    return results

        conn.close()

    except Exception as e:
        print(format_warning(
            "WARN", "feeds.py", "get_relevant_headlines()",
            f"failed to query feeds for ticker '{ticker}' — {e}",
            "check prices.db is accessible and feeds table exists"
        ))

    return results


def build_feed_injection(ticker):
    """
    Builds the feed headline string injected into build_data_package().
    Format is plain text — agents read it as part of the data package,
    not as a separate input. Each headline is one line:
        [DOMAIN] Source — Title (published)
    Returns empty string if no relevant headlines found.
    Stage 1 rule: this function returns text only — no model call here.
    """
    headlines = get_relevant_headlines(ticker)

    if not headlines:
        return ""

    lines = ["INTELLIGENCE FEED HEADLINES (for context only):"]
    for h in headlines:
        published = h.get("published", "") or ""
        # Trim published to date only if it's a full datetime string
        if "T" in published:
            published = published.split("T")[0]
        elif len(published) > 16:
            published = published[:16]

        line = f"  [{h['domain'].upper()}] {h['source']} — {h['title']}"
        if published:
            line += f" ({published})"
        lines.append(line)
        if h.get("summary"):
            lines.append(f"    {h['summary'][:200]}")

    return "\n".join(lines)

