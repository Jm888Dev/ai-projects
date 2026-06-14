# shared/utils.py
# Utilities shared across both projects.
# Import from here rather than duplicating in each pipeline.
# Usage: from shared.utils import extract_json, call_llm, update_market_history,
#                                 save_price_fixtures, send_email_alert, format_warning

# ─────────────────────────────────────────────────────────────
# ARCHITECTURAL RULE — NON-NEGOTIABLE
# This module must never import either project's config.py.
# Shared functions receive config-dependent values as parameters
# from the caller. Each project defines thin wrappers that inject
# its own config values once — call sites stay clean.
#
# WHY THIS RULE EXISTS:
# Importing config here poisons the importing project's config via
# sys.modules caching — the first config loaded wins and the correct
# one is silently ignored. This broke hdb_analyser.py on Day 15 and
# took an hour to diagnose. The fix was surgical but the lesson is
# permanent: shared modules are config-free by design.
#
# HOW TO ADD A NEW SHARED FUNCTION:
# 1. Write the function here with project-specific values as parameters
# 2. Add a thin wrapper in each project that injects its own config
# 3. Call the wrapper at call sites — never call shared functions directly
#    if they need config values
#
# Enforce at every code review. No exceptions. Ever.
# ─────────────────────────────────────────────────────────────

import json
import re
import math
import time
import os
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# WARNING FORMATTER
# ─────────────────────────────────────────────────────────────

def format_warning(severity, file, function, description, fix):
    """
    Builds a pipe-delimited warning string for the run summary.

    Why a dedicated formatter?
    The format is defined once here — changing it later is a
    one-line edit. No caller builds the string manually.
    Every warning in the codebase calls this function.

    Pipe-delimited format is machine-readable — import directly
    into Excel or SQLite for recurring issue analysis.

    severity:    'ERROR' or 'WARN'
    file:        exact filename e.g. 'shared/utils.py'
    function:    exact function name e.g. 'call_llm()'
    description: what happened, with variable values
    fix:         concrete action the developer can take

    Returns a single formatted string. Always print() this
    at point of failure AND append to run_warnings for the
    end-of-run consolidated summary.
    """
    # Pad WARN to 5 chars so columns align with ERROR in terminal
    # and in Excel when sorted by severity
    sev = "ERROR" if severity.upper() == "ERROR" else "WARN "
    return f"{sev} | {file} | {function} | {description} | {fix}"


# ─────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# Prefixed with _ to signal these are not for external use.
# Called by update_market_history() to guard yfinance field reads.
# ─────────────────────────────────────────────────────────────

def _safe_float(value):
    """
    Converts a value to float safely.
    Returns None if the value is null, NaN, or unconvertible.
    NaN from pandas is a valid Python float but not a valid price —
    we treat it as missing data.
    """
    try:
        if value is None:
            return None
        result = float(value)
        return None if math.isnan(result) else result
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    """
    Converts a value to int safely.
    Returns None if the value is null, NaN, or unconvertible.
    Volume from yfinance is occasionally NaN on thinly traded tickers
    or when markets are closed — this guards against that.
    """
    try:
        if value is None:
            return None
        f = float(value)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────
# JSON EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_json(raw):
    """
    Extracts and cleans a JSON object from Claude's raw response text.
    Handles: code fences, preamble, trailing text, markdown bold markers,
    and red_flags returned as an array instead of a string.

    Returns (parsed_dict, None) on success, (None, error_message) on failure.
    """
    # Step 1: Find the JSON object by locating first { and last }
    # Everything outside these boundaries is discarded
    start = raw.find("{")
    end = raw.rfind("}") + 1

    if start == -1 or end == 0:
        return None, "No JSON object found in response"

    clean = raw[start:end]

    # Step 2: Remove markdown bold markers — ** never appears in valid JSON
    clean = clean.replace("**", "")

    # Step 3: Collapse red_flags array into a string if Claude returned a list
    # Despite schema instructions, Claude sometimes returns ["item1", "item2"]
    array_pattern = re.compile(r'"red_flags"\s*:\s*\[([^\]]*)\]', re.DOTALL)
    match = array_pattern.search(clean)
    if match:
        array_contents = match.group(1)
        items = re.findall(r'"([^"]*)"', array_contents)
        joined = " ".join(items)
        clean = array_pattern.sub(f'"red_flags": "{joined}"', clean)

    # Step 4: Parse — this is the only place a parse error can occur
    try:
        parsed = json.loads(clean)
        return parsed, None
    except json.JSONDecodeError as e:
        return None, str(e)


# ─────────────────────────────────────────────────────────────
# LLM WRAPPER
# ─────────────────────────────────────────────────────────────

def call_llm(prompt, system=None, model=None, max_tokens=1024,
             temperature=0.3, fallback_model=None, client=None,
             call_type=None, use_live_agents=True,
             capture_fixtures=False, fixture_dir=None):
    """
    Universal wrapper for all Claude API calls across both projects.

    Tries the primary model first. If it fails and a fallback model is
    provided, tries that. If both fail, returns a graceful error string
    rather than crashing the pipeline.

    Truncation handling:
      If stop_reason is max_tokens, retries once at 1.5x token budget.
      If still truncated after retry, passes the truncated output through
      with a TRUNCATION_FLAG appended — never drops the signal.
      The truncated output still carries useful signal even if incomplete.

    Parameters:
      use_live_agents:   True = make real API calls; False = load from fixtures.
                         Default True — a caller with no fixture system gets
                         real API calls, which is always the safe behaviour.
      capture_fixtures:  True = save live responses to disk as fixture files.
                         Default False — fixtures are frozen unless explicitly
                         enabled. Never overwrite fixtures accidentally.
      fixture_dir:       Path to the folder where fixture JSONs are stored.
                         Caller passes this in — shared/utils.py never constructs
                         project-specific paths itself. Required when
                         use_live_agents=False; ignored otherwise.

    HOW TO USE FROM A NEW PROJECT:
      Define a thin wrapper in your project that injects your config values:
        def my_call_llm(**kwargs):
            return call_llm(**kwargs,
                            use_live_agents=config.USE_LIVE_AGENTS,
                            capture_fixtures=config.CAPTURE_FIXTURES,
                            fixture_dir=config.FIXTURE_DIR)
      Then call my_call_llm() everywhere in your project — config is declared
      once in the wrapper, never repeated at call sites.

    Returns (response_text, usage_dict).
    usage_dict contains: input_tokens, output_tokens, model_used,
    fallback_used, stop_reason, retried, truncated, retry_budget,
    warnings (list of pipe-delimited strings for run summary).
    """
    # Accumulates pipe-delimited warning strings during this call.
    # Returned via usage["warnings"] so the caller can append them
    # to run_warnings for the end-of-run consolidated summary.
    # Always print() at point of failure AND append here.
    warnings = []

    # ── Fixture agent logic ───────────────────────────────────
    # fixture_dir comes from the caller — this function never constructs
    # project-specific paths. Each project knows where its fixtures live.
    _FIXTURE_DIR = Path(fixture_dir) if fixture_dir else None

    if call_type and not use_live_agents:
        # Guard: fixture mode requested but no directory provided —
        # unrecoverable, hard stop per Day 9 principle. Silent fallback
        # here would mask a misconfiguration and waste API budget.
        if _FIXTURE_DIR is None:
            msg = format_warning(
                "ERROR", "shared/utils.py", "call_llm()",
                f"use_live_agents=False for call_type='{call_type}' "
                f"but fixture_dir was not provided",
                "pass fixture_dir=config.FIXTURE_DIR from your project "
                "wrapper — see call_llm() docstring for the wrapper pattern"
            )
            print(f"\n{msg}")
            raise ValueError(msg)

        fixture_path = _FIXTURE_DIR / f"{call_type}.json"

        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8") as f:
                fixture_text = f.read()

            fixture_usage = {
                "input_tokens":  0,
                "output_tokens": 0,
                "model_used":    f"fixture:{call_type}",
                "fallback_used": False,
                "stop_reason":   "end_turn",
                "retried":       False,
                "truncated":     False,
                "retry_budget":  None,
                "warnings":      [],  # no warnings on clean fixture load
            }
            print(f"[call_llm] Fixture loaded: {call_type}.json")
            return fixture_text, fixture_usage
        else:
            # Hard stop — fixture missing means the pipeline cannot proceed.
            # Always an ERROR, never a WARN — silent fallback to live API
            # would defeat the purpose of fixture mode entirely.
            msg = format_warning(
                "ERROR", "shared/utils.py", "call_llm()",
                f"fixture not found for '{call_type}' "
                f"— expected at {fixture_path}",
                "set use_live_agents=True and capture_fixtures=True in your "
                "project wrapper, run once to populate fixtures, then set "
                "both back to their defaults"
            )
            print(f"\n{msg}")
            raise FileNotFoundError(msg)
    # ── End fixture load logic ────────────────────────────────

    messages = [{"role": "user", "content": prompt}]
    call_kwargs = {
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "messages":    messages,
    }
    if system:
        call_kwargs["system"] = system

    def _attempt(mdl, token_budget):
        kw = {**call_kwargs, "max_tokens": token_budget}
        response = client.messages.create(model=mdl, **kw)
        usage = {
            "input_tokens":  response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model_used":    mdl,
            "fallback_used": False,
            "stop_reason":   response.stop_reason,
        }
        return response.content[0].text, usage

    # ── Attempt 1 — primary model ─────────────────────────────
    text  = None
    usage = None

    try:
        text, usage = _attempt(model, max_tokens)

    except Exception as primary_error:
        msg = format_warning(
            "ERROR", "shared/utils.py", "call_llm()",
            f"primary model '{model}' failed — {primary_error}",
            "check ANTHROPIC_API_KEY in .env and Anthropic service status"
        )
        print(msg)
        warnings.append(msg)

        if fallback_model:
            try:
                text, usage = _attempt(fallback_model, max_tokens)
                usage["fallback_used"] = True
                print(f"[call_llm] Fallback succeeded ({fallback_model})")
            except Exception as fallback_error:
                msg = format_warning(
                    "ERROR", "shared/utils.py", "call_llm()",
                    f"fallback model '{fallback_model}' also failed "
                    f"— {fallback_error}",
                    "check Anthropic API status — pipeline will receive "
                    "[LLM_ERROR] and degrade gracefully"
                )
                print(msg)
                warnings.append(msg)

        if text is None:
            empty_usage = {
                "input_tokens":  0,
                "output_tokens": 0,
                "model_used":    None,
                "fallback_used": False,
                "stop_reason":   "error",
                "retried":       False,
                "truncated":     False,
                "retry_budget":  None,
                "warnings":      warnings,
            }
            return f"[LLM_ERROR] All models failed. Last error: {primary_error}", empty_usage

    # ── Truncation detection and retry ────────────────────────
    usage["retried"]      = False
    usage["truncated"]    = False
    usage["retry_budget"] = None

    if usage["stop_reason"] == "max_tokens":
        retry_budget = int(max_tokens * 1.5)
        print(f"[call_llm] Truncation detected on {usage['model_used']} — "
              f"retrying at {retry_budget} tokens (was {max_tokens})")

        try:
            retry_text, retry_usage = _attempt(usage["model_used"], retry_budget)

            usage["retried"]      = True
            usage["retry_budget"] = retry_budget
            usage["input_tokens"]  = retry_usage["input_tokens"]
            usage["output_tokens"] = retry_usage["output_tokens"]
            usage["stop_reason"]   = retry_usage["stop_reason"]

            if retry_usage["stop_reason"] == "max_tokens":
                print(f"[call_llm] Still truncated after retry — "
                      f"passing through with truncation flag")
                usage["truncated"] = True
                text = (
                    retry_text
                    + "\n\n[TRUNCATION_FLAG: Output reached token limit after "
                    "retry. Reasoning may be incomplete. Weight this input "
                    "accordingly.]"
                )
            else:
                print(f"[call_llm] Retry resolved truncation.")
                usage["truncated"] = False
                text = retry_text

        except Exception as retry_error:
            msg = format_warning(
                "WARN", "shared/utils.py", "call_llm()",
                f"truncation retry failed for model '{usage['model_used']}' "
                f"— {retry_error}",
                f"raise token budget in config.py for this agent stage. "
                f"Passing original truncated output through with flag."
            )
            print(msg)
            warnings.append(msg)
            usage["retried"]      = True
            usage["retry_budget"] = retry_budget
            usage["truncated"]    = True
            text = (
                text
                + "\n\n[TRUNCATION_FLAG: Output reached token limit. Retry "
                "failed. Reasoning may be incomplete. Weight this input "
                "accordingly.]"
            )

    # ── Fixture capture logic ─────────────────────────────────
    # Saves live response to disk when capture_fixtures=True.
    # _FIXTURE_DIR comes from fixture_dir parameter — never constructed here.
    # Frozen by default (capture_fixtures=False) so fixtures are never
    # overwritten accidentally during normal runs.
    if call_type and use_live_agents and capture_fixtures and _FIXTURE_DIR:
        _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        fixture_path = _FIXTURE_DIR / f"{call_type}.json"
        try:
            with open(fixture_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[call_llm] Fixture captured: {call_type}.json")
        except Exception as e:
            msg = format_warning(
                "WARN", "shared/utils.py", "call_llm()",
                f"fixture capture failed for '{call_type}' — {e}",
                f"check write permissions on {_FIXTURE_DIR}"
            )
            print(msg)
            warnings.append(msg)
    # ── End fixture capture logic ─────────────────────────────

    # Attach accumulated warnings to usage dict before returning.
    # Caller reads usage["warnings"] and appends to run_warnings.
    usage["warnings"] = warnings

    return text, usage


# ─────────────────────────────────────────────────────────────
# MARKET HISTORY
# ─────────────────────────────────────────────────────────────

def update_market_history(tickers, use_live=True):
    """
    Fetches daily OHLCV data for all tickers and writes to market_history.

    Two modes:
      - First run for a ticker: fetches 5 years of history (backfill)
      - Subsequent runs: fetches only new trading days since the last
        stored date (delta pull)

    Missed days are caught automatically on the next run — no manual
    intervention needed. Safe to re-run: INSERT OR IGNORE on
    (ticker, trade_date) prevents duplicates.

    use_live=True  — fetches from yfinance (production and backfill)
    use_live=False — skips fetch entirely, agents read from whatever
                     is already in market_history or fixture CSV files
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    import database

    if not use_live:
        print("[market_history] Fixture mode — skipping live fetch.")
        return

    now = datetime.now()
    total_rows_written = 0

    for ticker in tickers:
        try:
            # Check what we already have for this ticker
            latest_date = database.get_latest_market_history_date(ticker)

            if latest_date is None:
                # No history at all — fetch full 5-year backfill
                start_date = (now - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
                print(f"[market_history] {ticker}: no history — "
                      f"backfilling from {start_date}")
            else:
                # We have history — fetch only from the day after last stored
                # yfinance start is inclusive so +1 day gives us new days only
                last_dt = datetime.strptime(latest_date, "%Y-%m-%d")
                start_date = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"[market_history] {ticker}: last date {latest_date} — "
                      f"delta pull from {start_date}")

            today = now.strftime("%Y-%m-%d")

            # Already current — nothing to fetch
            if start_date >= today:
                print(f"[market_history] {ticker}: already current — skipping.")
                continue

            # Fetch from yfinance
            # auto_adjust=True adjusts prices for splits and dividends
            df = yf.Ticker(ticker).history(
                start=start_date,
                end=today,
                auto_adjust=True,
            )

            if df.empty:
                print(f"[market_history] {ticker}: no new data returned "
                      f"(market may be closed or ticker inactive).")
                continue

            # Build row dicts — iterate oldest to newest so pct_change
            # is computed correctly from the prior row's close
            inserted_at = now.isoformat()
            rows = []
            prev_close = None
            skipped_rows = 0

            for trade_date, row in df.sort_index().iterrows():

                # Guard Close — a row without a close is not useful
                close = _safe_float(row.get("Close"))
                if close is None:
                    skipped_rows += 1
                    continue

                # Compute daily percentage change from prior close
                try:
                    pct_change = (
                        round(((close - prev_close) / prev_close) * 100, 4)
                        if prev_close and prev_close != 0
                        else None
                    )
                except Exception as pct_err:
                    print(format_warning(
                        "WARN", "shared/utils.py",
                        "update_market_history()",
                        f"could not compute pct_change for '{ticker}' "
                        f"on {trade_date.strftime('%Y-%m-%d')} — {pct_err}",
                        "check prev_close value is not None or zero "
                        "in market_history for this ticker"
                    ))
                    pct_change = None

                rows.append({
                    "ticker":      ticker,
                    "trade_date":  trade_date.strftime("%Y-%m-%d"),
                    "open":        _safe_float(row.get("Open")),
                    "high":        _safe_float(row.get("High")),
                    "low":         _safe_float(row.get("Low")),
                    "close":       close,
                    "volume":      _safe_int(row.get("Volume")),
                    "pct_change":  pct_change,
                    "source":      "yfinance",
                    "inserted_at": inserted_at,
                })
                prev_close = close

            if skipped_rows > 0:
                print(f"[market_history] {ticker}: {skipped_rows} rows "
                      f"skipped — null or malformed data.")

            # Write the batch — INSERT OR IGNORE handles duplicates safely
            written = database.write_market_history_rows(rows)
            total_rows_written += written
            print(f"[market_history] {ticker}: {written} rows written.")

        except Exception as e:
            print(format_warning(
                "ERROR", "shared/utils.py",
                "update_market_history()",
                f"failed to fetch or write history for '{ticker}' — {e}",
                "check yfinance connectivity or verify ticker symbol "
                "is valid in config.TICKERS"
            ))
            continue

        # Small delay between tickers to avoid Yahoo Finance rate limiting
        # 1 second across 8 tickers adds 8 seconds total — acceptable
        time.sleep(1)

    print(f"[market_history] Complete. Total rows written: {total_rows_written}")


# ─────────────────────────────────────────────────────────────
# FIXTURE PRICE UPDATER
# ─────────────────────────────────────────────────────────────

def save_price_fixtures(price_data, fixture_path, capture=True):
    """
    Updates the prices block in a fixture JSON file with current
    live price data.

    Generic — works for any project that uses price fixtures.
    Stock Monitor passes its normal_day.json path. HDB Analyser
    will pass its own fixture path when it adopts this pattern.

    Parameters:
      price_data:    list of price dicts from get_current_prices()
                     or equivalent fetch function
      fixture_path:  full path to the fixture JSON file to update.
                     Caller constructs this from their own config —
                     shared/utils.py never constructs project paths.
      capture:       True = update the file; False = skip silently.
                     Caller passes config.CAPTURE_LIVE_DATA_FOR_FIXTURES
                     or equivalent. Default True so the function is
                     useful without a fixture system.

    Preserves all existing keys in the fixture file — only the
    prices block and _created date are replaced.
    """
    from datetime import datetime

    # Respect the capture flag — do nothing if False
    if not capture:
        print("[save_price_fixtures] capture=False — fixture not updated.")
        return

    fixture_path = Path(fixture_path)

    try:
        # Read existing file first — only prices and _created are replaced,
        # intelligence block and all metadata are preserved untouched
        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8-sig") as f:
                existing = json.load(f)
        else:
            # File missing — build minimal shell rather than hard stop
            # because this is a write operation, not a read dependency
            print(format_warning(
                "WARN", "shared/utils.py",
                "save_price_fixtures()",
                f"fixture file not found at {fixture_path} "
                "— creating new file with prices only",
                "run once with live data enabled to populate a complete "
                "fixture file including any non-price blocks"
            ))
            existing = {
                "_description": "Auto-generated fixture from live run.",
            }

        # Replace only prices and update the created date
        existing["prices"]   = price_data
        existing["_created"] = datetime.now().strftime("%Y-%m-%d")

        # Write back — utf-8 without BOM, indent=2 matches original format
        with open(fixture_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        print(f"[save_price_fixtures] {fixture_path.name} updated "
              f"with {len(price_data)} price records.")

    except Exception as e:
        # Never crash the pipeline over a fixture write failure
        print(format_warning(
            "WARN", "shared/utils.py",
            "save_price_fixtures()",
            f"failed to write fixture at {fixture_path} — {e}",
            "check write permissions on the fixture directory"
        ))


# ─────────────────────────────────────────────────────────────
# EMAIL ALERTS
# ─────────────────────────────────────────────────────────────

def send_email_alert(subject, body, env_path=None, project_tag="Monitor"):
    """
    Sends a plain text email alert via Outlook SMTP.

    Generic — works for any project that needs email alerts.
    Stock Monitor uses it for REDUCE/EXIT signals. HDB Analyser
    will use it for price drops, opportunity matches, and pipeline
    failures when it adopts this pattern.

    Parameters:
      subject:      email subject line (project tag prepended automatically)
      body:         plain text email body
      env_path:     full path to the .env file containing email credentials.
                    Caller passes this from their own project directory —
                    shared/utils.py never constructs project-specific paths.
                    Falls back to os.getenv() if None, which works when
                    load_dotenv() was already called by the pipeline.
      project_tag:  prepended to subject as [project_tag] for inbox filtering.
                    Default 'Monitor' — callers pass their project name.

    Credentials expected in .env:
      EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT

    Returns True if sent successfully, False if send failed.
    Never crashes the pipeline — email failure is logged and
    execution continues.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from dotenv import load_dotenv

    # Load credentials from the caller's .env path if provided.
    # If None, credentials are read from environment as already loaded
    # by the pipeline's own load_dotenv() call at startup.
    if env_path:
        load_dotenv(dotenv_path=Path(env_path))

    email_from     = os.getenv("EMAIL_FROM")
    email_to       = os.getenv("EMAIL_TO")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server    = os.getenv("SMTP_SERVER", "smtp-mail.outlook.com")
    smtp_port      = int(os.getenv("SMTP_PORT", "587"))

    # Validate that all required credentials are present before
    # attempting a connection — fail fast with a clear message
    if not all([email_from, email_to, email_password, smtp_server]):
        print(format_warning(
            "WARN", "shared/utils.py", "send_email_alert()",
            "missing email credentials — email not sent",
            "add EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD, SMTP_SERVER, "
            "SMTP_PORT to your project's .env file"
        ))
        return False

    try:
        # Build the email message
        # MIMEMultipart allows us to add both plain text and HTML later
        msg = MIMEMultipart()
        msg["From"]    = email_from
        msg["To"]      = email_to
        msg["Subject"] = f"[{project_tag}] {subject}"

        # Attach the body as plain text
        # UTF-8 ensures special characters like % and $ render correctly
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect to Outlook SMTP server
        # SMTP + starttls uses port 587 (upgrades to encrypted mid-session)
        # Outlook requires the starttls approach on port 587
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()       # introduce client to server
            server.starttls()   # upgrade to encrypted TLS
            server.ehlo()       # re-identify after TLS upgrade
            server.login(email_from, email_password)
            server.sendmail(email_from, [email_to], msg.as_string())

        print(f"[EMAIL] Alert sent: {subject}")
        return True

    except smtplib.SMTPAuthenticationError:
        print(format_warning(
            "ERROR", "shared/utils.py", "send_email_alert()",
            f"authentication failed for '{email_from}' "
            f"on {smtp_server}:{smtp_port}",
            "verify EMAIL_PASSWORD in .env is correct and that "
            "SMTP access is enabled in your email account settings"
        ))
        return False

    except smtplib.SMTPException as e:
        print(format_warning(
            "ERROR", "shared/utils.py", "send_email_alert()",
            f"SMTP error — {e}",
            "check SMTP_SERVER and SMTP_PORT in .env match your "
            "email provider settings"
        ))
        return False

    except Exception as e:
        print(format_warning(
            "ERROR", "shared/utils.py", "send_email_alert()",
            f"unexpected failure — {e}",
            "check network connectivity and .env credentials"
        ))
        return False
