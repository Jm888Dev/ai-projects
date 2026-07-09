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
    sev = "ERROR" if severity.upper() == "ERROR" else "WARN "
    return f"{sev} | {file} | {function} | {description} | {fix}"


# ─────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────

def _safe_float(value):
    try:
        if value is None:
            return None
        result = float(value)
        return None if math.isnan(result) else result
    except (TypeError, ValueError):
        return None


def _safe_int(value):
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
    start = raw.find("{")
    end = raw.rfind("}") + 1

    if start == -1 or end == 0:
        return None, "No JSON object found in response"

    clean = raw[start:end]
    clean = clean.replace("**", "")

    array_pattern = re.compile(r'"red_flags"\s*:\s*\[([^\]]*)\]', re.DOTALL)
    match = array_pattern.search(clean)
    if match:
        array_contents = match.group(1)
        items = re.findall(r'"([^"]*)"', array_contents)
        joined = " ".join(items)
        clean = array_pattern.sub(f'"red_flags": "{joined}"', clean)

    try:
        parsed = json.loads(clean)
        return parsed, None
    except json.JSONDecodeError:
        # First parse failed — attempt structural repair before giving up.
        # Handles common SLM output errors: missing quotes around string
        # values, trailing commas, unescaped characters.
        # json-repair is conservative — it only fixes what it can infer
        # unambiguously. If repair also fails, return the original error.
        try:
            from json_repair import repair_json
            repaired = repair_json(clean, return_objects=True)
            if repaired:
                return repaired, None
            return None, "JSON repair returned empty result"
        except Exception as repair_err:
            return None, f"JSON parse and repair both failed: {repair_err}"

# ─────────────────────────────────────────────────────────────
# OLLAMA LOCAL INFERENCE
# ─────────────────────────────────────────────────────────────

def _call_ollama(prompt, system=None, model="phi4-mini",
                 max_tokens=1024, temperature=0.3,
                 base_url="http://localhost:11434/api/chat",
                 timeout=300, model_max_ctx=None,
                 chars_per_token_estimate=4, num_ctx_safety_margin=2048,
                 num_ctx_fallback_max=8192, hardware_cap=32000):
    """
    Makes a single inference call to the local Ollama REST endpoint.

    model_max_ctx:             real context ceiling for this specific
                               model (e.g. 131072 for phi4-mini), looked
                               up by the caller from
                               config.OLLAMA_MODEL_MAX_CTX. None means
                               unknown — falls back to num_ctx_fallback_max.
    chars_per_token_estimate:  rough chars-per-token heuristic used to
                               estimate input size before the call,
                               since Ollama only reports actual token
                               counts in the response, not before.
    num_ctx_safety_margin:    extra tokens added on top of the estimate
                               to absorb estimation error.
    num_ctx_fallback_max:     conservative ceiling used only when
                               model_max_ctx is None.

    Returns (text, usage_dict).
    Sovereignty rule: base_url must always be localhost.
    """
    import requests

    if "localhost" not in base_url and "127.0.0.1" not in base_url:
        raise ValueError(
            f"_call_ollama() sovereignty violation: base_url '{base_url}' "
            f"points outside localhost. The sovereign SLM tier must never "
            f"send data to an external endpoint. Check OLLAMA_BASE_URL "
            f"in config.py — it must always be http://localhost:11434/api/chat"
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # num_ctx must be set explicitly — Ollama defaults to a small context
    # window (commonly 2048 tokens) regardless of model capability.
    # Without this, prompts larger than the default are silently truncated
    # and the model reasons on a fragment with no warning of any kind.
    # Discovered Day 19 during SLM benchmarking.
    #
    # num_ctx covers INPUT + OUTPUT combined, not output alone — an
    # earlier version of this fix (same session) wrongly treated it as
    # output-only headroom. Corrected after checking real model ceilings
    # via `ollama show <model>` — phi4-mini and gemma4:e4b support up to
    # 131,072 tokens; qwen3.6:35b-a3b and gemma4:26b support up to 262,144.
    #
    # We don't know the exact input token count before the call — Ollama
    # only reports it in the response — so we estimate from character
    # count using a standard ~4 chars/token heuristic, then add the
    # output budget and a safety margin for estimation error.
    estimated_input_tokens = len(prompt) // chars_per_token_estimate
    if system:
        estimated_input_tokens += len(system) // chars_per_token_estimate

    required_ctx = estimated_input_tokens + max_tokens + num_ctx_safety_margin

    # Three-way cap, minimum wins:
    #   1. model_max_ctx   — what the model architecturally supports
    #   2. hardware_cap    — what this machine can safely hold in RAM
    #                        regardless of model capability
    #   3. required_ctx    — what the actual prompt+output need
    # This module is config-free, so both ceiling values arrive as
    # parameters from the caller's config.py lookups.
    model_ceiling = model_max_ctx if model_max_ctx else num_ctx_fallback_max
    required_ctx = min(required_ctx, model_ceiling, hardware_cap)

    payload = {
        "model":    model,
        "messages": messages,
        "stream":   False,
        "options": {
            "num_predict":  max_tokens,
            "temperature":  temperature,
            "num_ctx":      required_ctx,
        },
    }

    response = requests.post(
        base_url,
        json=payload,
        timeout=timeout,
    )

    response.raise_for_status()

    data = response.json()

    text = data.get("message", {}).get("content", "")

    input_tokens  = data.get("prompt_eval_count", 0)
    output_tokens = data.get("eval_count", 0)

    thinking_tokens = data.get("thinking_eval_count", 0)

    raw_stop = data.get("done_reason", "stop")
    stop_reason = "max_tokens" if raw_stop == "length" else "end_turn"

    usage = {
        "input_tokens":   input_tokens,
        "output_tokens":  output_tokens,
        "model_used":     model,
        "fallback_used":  False,
        "stop_reason":    stop_reason,
        "thinking_tokens": thinking_tokens,
    }

    return text, usage

# ─────────────────────────────────────────────────────────────
# LLM WRAPPER
# ─────────────────────────────────────────────────────────────

def call_llm(prompt, system=None, model=None, max_tokens=1024,
             temperature=0.3, fallback_model=None, client=None,
             call_type=None, use_live_agents=True,
             capture_fixtures=False, fixture_dir=None,
             use_slm=False, slm_model=None,
             ollama_base_url="http://localhost:11434/api/chat",
             ollama_timeout=300, ollama_model_max_ctx=None,
             ollama_chars_per_token_estimate=4,
             ollama_num_ctx_safety_margin=2048,
             ollama_num_ctx_fallback_max=8192,
             ollama_hardware_cap=32000):
    """
    Universal wrapper for all Claude API calls across both projects.

    Returns (response_text, usage_dict).
    usage_dict contains: input_tokens, output_tokens, model_used,
    fallback_used, stop_reason, retried, truncated, retry_budget,
    prompt_text, warnings.
    """
    warnings = []

    _FIXTURE_DIR = Path(fixture_dir) if fixture_dir else None

    if call_type and not use_live_agents:
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
                "prompt_text":   prompt,
                "warnings":      [],
            }
            print(f"[call_llm] Fixture loaded: {call_type}.json")
            return fixture_text, fixture_usage
        else:
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

    if use_slm:
        if not slm_model:
            msg = format_warning(
                "ERROR", "shared/utils.py", "call_llm()",
                "use_slm=True but slm_model was not provided",
                "pass slm_model from your project wrapper — "
                "see sm_call_llm() in stock_monitor.py for the pattern"
            )
            print(msg)
            raise ValueError(msg)

        try:
            text, slm_usage = _call_ollama(
                prompt=prompt,
                system=system,
                model=slm_model,
                max_tokens=max_tokens,
                temperature=temperature,
                base_url=ollama_base_url,
                timeout=ollama_timeout,
                model_max_ctx=ollama_model_max_ctx,
                chars_per_token_estimate=ollama_chars_per_token_estimate,
                num_ctx_safety_margin=ollama_num_ctx_safety_margin,
                num_ctx_fallback_max=ollama_num_ctx_fallback_max,
                hardware_cap=ollama_hardware_cap,
            )

            slm_usage["fallback_used"] = False
            slm_usage["retried"]       = False
            slm_usage["truncated"]     = False
            slm_usage["retry_budget"]  = None
            slm_usage["prompt_text"]   = prompt
            slm_usage["warnings"]      = []

            if slm_usage["stop_reason"] == "max_tokens":
                retry_budget = int(max_tokens * 1.5)
                print(f"[call_llm] SLM truncation on {slm_model} — "
                      f"retrying at {retry_budget} tokens")
                try:
                    text, retry_usage = _call_ollama(
                        prompt=prompt,
                        system=system,
                        model=slm_model,
                        max_tokens=retry_budget,
                        temperature=temperature,
                        base_url=ollama_base_url,
                        timeout=ollama_timeout,
                        model_max_ctx=ollama_model_max_ctx,
                        chars_per_token_estimate=ollama_chars_per_token_estimate,
                        num_ctx_safety_margin=ollama_num_ctx_safety_margin,
                        num_ctx_fallback_max=ollama_num_ctx_fallback_max,
                        hardware_cap=ollama_hardware_cap,
                    )
                    slm_usage["retried"]       = True
                    slm_usage["retry_budget"]  = retry_budget
                    slm_usage["input_tokens"]  = retry_usage["input_tokens"]
                    slm_usage["output_tokens"] = retry_usage["output_tokens"]
                    slm_usage["stop_reason"]   = retry_usage["stop_reason"]

                    if retry_usage["stop_reason"] == "max_tokens":
                        slm_usage["truncated"] = True
                        text = (
                            text
                            + "\n\n[TRUNCATION_FLAG: SLM output reached token "
                            "limit after retry. Reasoning may be incomplete.]"
                        )
                    else:
                        print(f"[call_llm] SLM retry resolved truncation.")

                except Exception as retry_err:
                    msg = format_warning(
                        "WARN", "shared/utils.py", "call_llm()",
                        f"SLM truncation retry failed for '{slm_model}' "
                        f"— {retry_err}",
                        "raise OLLAMA_TIMEOUT in config.py or reduce "
                        "max_tokens for this stage"
                    )
                    print(msg)
                    slm_usage["warnings"].append(msg)
                    slm_usage["truncated"] = True
                    text = (
                        text
                        + "\n\n[TRUNCATION_FLAG: SLM retry failed. "
                        "Output may be incomplete.]"
                    )

            if call_type and capture_fixtures and _FIXTURE_DIR:
                _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
                fixture_path = _FIXTURE_DIR / f"{call_type}.json"
                try:
                    with open(fixture_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    print(f"[call_llm] SLM fixture captured: {call_type}.json")
                except Exception as e:
                    msg = format_warning(
                        "WARN", "shared/utils.py", "call_llm()",
                        f"SLM fixture capture failed for '{call_type}' "
                        f"— {e}",
                        f"check write permissions on {_FIXTURE_DIR}"
                    )
                    print(msg)
                    slm_usage["warnings"].append(msg)

            return text, slm_usage

        except Exception as slm_error:
            msg = format_warning(
                "ERROR", "shared/utils.py", "call_llm()",
                f"SLM call failed for model '{slm_model}' — {slm_error}",
                "check Ollama is running: curl http://localhost:11434 "
                "and verify model is pulled: ollama list"
            )
            print(msg)
            warnings.append(msg)
            empty_usage = {
                "input_tokens":   0,
                "output_tokens":  0,
                "model_used":     slm_model,
                "fallback_used":  False,
                "stop_reason":    "error",
                "retried":        False,
                "truncated":      False,
                "retry_budget":   None,
                "thinking_tokens": 0,
                "prompt_text":    prompt,
                "warnings":       warnings,
            }
            # Same error prefix the Anthropic cloud path uses below — callers
            # only check for "[LLM_ERROR]" and don't need to know WHICH
            # provider failed, only THAT it failed. Before this fix, an
            # Ollama failure returned "[SLM_ERROR]" instead, which none of
            # the four call sites in stock_monitor.py matched — the error
            # silently fell through to extract_json(), which correctly found
            # no JSON and reported "JSON parse failed" instead of the real
            # cause. One error dialect, not two — and a future third
            # provider (e.g. DeepSeek) won't need its own prefix either.
            return (
                f"[LLM_ERROR] Ollama call failed for '{slm_model}'. "
                f"Error: {slm_error}",
                empty_usage,
            )

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
                "prompt_text":   prompt,
                "warnings":      warnings,
            }
            return f"[LLM_ERROR] All models failed. Last error: {primary_error}", empty_usage

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

    usage["warnings"]     = warnings
    usage["prompt_text"]  = prompt

    return text, usage


# ─────────────────────────────────────────────────────────────
# MARKET HISTORY
# ─────────────────────────────────────────────────────────────

def update_market_history(tickers, use_live=True):
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
            latest_date = database.get_latest_market_history_date(ticker)

            if latest_date is None:
                start_date = (now - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
                print(f"[market_history] {ticker}: no history — "
                      f"backfilling from {start_date}")
            else:
                last_dt = datetime.strptime(latest_date, "%Y-%m-%d")
                start_date = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"[market_history] {ticker}: last date {latest_date} — "
                      f"delta pull from {start_date}")

            today = now.strftime("%Y-%m-%d")

            if start_date >= today:
                print(f"[market_history] {ticker}: already current — skipping.")
                continue

            df = yf.Ticker(ticker).history(
                start=start_date,
                end=today,
                auto_adjust=True,
            )

            if df.empty:
                print(f"[market_history] {ticker}: no new data returned "
                      f"(market may be closed or ticker inactive).")
                continue

            inserted_at = now.isoformat()
            rows = []
            prev_close = None
            skipped_rows = 0

            for trade_date, row in df.sort_index().iterrows():

                close = _safe_float(row.get("Close"))
                if close is None:
                    skipped_rows += 1
                    continue

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

        time.sleep(1)

    print(f"[market_history] Complete. Total rows written: {total_rows_written}")


# ─────────────────────────────────────────────────────────────
# FIXTURE PRICE UPDATER
# ─────────────────────────────────────────────────────────────

def save_price_fixtures(price_data, fixture_path, capture=True):
    from datetime import datetime

    if not capture:
        print("[save_price_fixtures] capture=False — fixture not updated.")
        return

    fixture_path = Path(fixture_path)

    try:
        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8-sig") as f:
                existing = json.load(f)
        else:
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

        existing["prices"]   = price_data
        existing["_created"] = datetime.now().strftime("%Y-%m-%d")

        with open(fixture_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        print(f"[save_price_fixtures] {fixture_path.name} updated "
              f"with {len(price_data)} price records.")

    except Exception as e:
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
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from dotenv import load_dotenv

    if env_path:
        load_dotenv(dotenv_path=Path(env_path))

    email_from     = os.getenv("EMAIL_FROM")
    email_to       = os.getenv("EMAIL_TO")
    email_password = os.getenv("EMAIL_PASSWORD")
    smtp_server    = os.getenv("SMTP_SERVER", "smtp-mail.outlook.com")
    smtp_port      = int(os.getenv("SMTP_PORT", "587"))

    if not all([email_from, email_to, email_password, smtp_server]):
        print(format_warning(
            "WARN", "shared/utils.py", "send_email_alert()",
            "missing email credentials — email not sent",
            "add EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD, SMTP_SERVER, "
            "SMTP_PORT to your project's .env file"
        ))
        return False

    try:
        msg = MIMEMultipart()
        msg["From"]    = email_from
        msg["To"]      = email_to
        msg["Subject"] = f"[{project_tag}] {subject}"

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
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