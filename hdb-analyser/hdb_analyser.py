# hdb_analyser.py
# HDB Resale Buyer Analyser — main script
# Day 5: Fetches real transaction data from data.gov.sg, runs the analyst,
# then builds a buyer briefing section by section. Two outputs:
#   - briefing_dict: structured Python object for downstream agents (Day 21)
#   - briefing_text: plain English rendering for the human reader

# ── Imports ───────────────────────────────────────────────────────────────────
import anthropic
import requests       # sends HTTP calls to web APIs (like a browser, but in Python)
import pandas as pd   # turns raw data into a filterable table (SQL in Python)
import json           # parses JSON strings into Python dicts
import re             # regular expressions — used in JSON cleaning
import os             # reads environment variables
import time           # measures elapsed duration per pipeline stage
import sys

from pathlib import Path

# Add the ai-projects root to Python's path dynamically.
# This makes shared/ importable regardless of where the project lives on disk.
# Path(__file__) = this file's location
# .parent = the project folder (hdb-analyser/)
# .parent.parent = the ai-projects root
sys.path.insert(0, str(Path(__file__).parent.parent))  # ai-projects/ — finds shared/
from shared.utils import extract_json  # Shared utility — same cleaner for both projects

from dotenv import load_dotenv

from config import (
    ANALYST_MODEL,        # Sonnet — complex buyer reasoning
    TRANSLATOR_MODEL,     # Haiku — plain English rewrite
    ANALYST_MAX_TOKENS,   # Per-section token budget for analyst
    TRANSLATOR_MAX_TOKENS, # Per-section token budget for translator
    ANALYST_TEMPERATURE,  # Low — keeps analysis factual
    TRANSLATOR_TEMPERATURE, # Slightly higher — natural language
    API_BASE_URL,         # data.gov.sg endpoint
    HDB_RESOURCE_ID,      # Dataset identifier
    FETCH_LIMIT,          # Raw records pulled from API
    SAMPLE_SIZE,          # Records passed to Claude after filtering
    REQUEST_TIMEOUT,      # API call timeout in seconds
    DEFAULT_TOWN,         # Default buyer query town
    DEFAULT_FLAT_TYPE,    # Default flat type filter
    ANALYST_SECTIONS,     # Seven analyst concern sections
    TRANSLATOR_SECTIONS,  # Seven buyer-facing briefing sections
    ANALYST_SECTION_DEPENDENCIES, # Controls which sections get prior context
    TRANSLATOR_SECTION_TOKENS,  # Per-section token budgets for translator
)
from prompts.analyst_persona import (
    HDB_ANALYST_SYSTEM_PROMPT,
    HDB_TRANSLATOR_SYSTEM_PROMPT,
    HDB_SECTION_PROMPTS,
    ANALYST_SECTION_PROMPTS,    # New — per-section analyst instructions
)

# Load the .env file so ANTHROPIC_API_KEY is available via os.getenv()
load_dotenv()


# ── Function 1: Fetch HDB data from the API ───────────────────────────────────
def fetch_hdb_data(town=None, flat_type=None, limit=REQUEST_TIMEOUT):
    """
    Calls data.gov.sg and returns HDB resale records as a pandas DataFrame.
    Filters are applied server-side — only matching rows are sent back.
    Sorted by month descending so the newest transactions arrive first.
    """

    # Request parameters — the API treats these as the query string
    params = {
        "resource_id": HDB_RESOURCE_ID,
        "limit": limit,
        "sort": "month desc"  # newest first — critical for buyer relevance
    }

    # Add server-side filters when town or flat_type are provided
    # SQL equivalent: WHERE town = 'SENGKANG' AND flat_type = '4 ROOM'
    filters = {}
    if town:
        filters["town"] = town.upper()
    if flat_type:
        filters["flat_type"] = flat_type.upper()
    if filters:
        # API expects filters as a JSON string, not a raw Python dict
        params["filters"] = json.dumps(filters)

    filter_desc = f" ({', '.join(filters.values())})" if filters else ""
    print(f"Fetching HDB resale records{filter_desc} from data.gov.sg...")

    try:
        response = requests.get(API_BASE_URL, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        records = data["result"]["records"]
        total_available = data["result"]["total"]

        df = pd.DataFrame(records)
        print(f"✓ Fetched {len(df)} records (total available: {total_available})")
        return df

    except requests.exceptions.Timeout:
        print("ERROR: API request timed out. Check your internet connection.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not reach data.gov.sg — {e}")
        return None

    except KeyError:
        print("ERROR: Unexpected API response format.")
        return None


# ── Function 2: Filter and sample transactions ────────────────────────────────
def filter_transactions(df, town, flat_type, sample_size=SAMPLE_SIZE):
    """
    Narrows the DataFrame to matching town and flat type, sorts by most
    recent, and returns the top N rows as a sample for Claude.
    We sample because Claude has a context window — sending thousands of
    rows would blow past it. 20 recent transactions give enough signal.
    """

    town_upper = town.upper()
    flat_type_upper = flat_type.upper()

    # SQL equivalent: WHERE town = X AND flat_type = Y
    filtered = df[df['town'] == town_upper]
    filtered = filtered[filtered['flat_type'] == flat_type_upper]

    if filtered.empty:
        print(f"WARNING: No transactions found for {town_upper} / {flat_type_upper}")
        print(f"Available towns: {df['town'].unique().tolist()}")
        return None

    # SQL equivalent: ORDER BY month DESC LIMIT 20
    filtered = filtered.sort_values('month', ascending=False)
    sample = filtered.head(sample_size)

    print(f"✓ Found {len(filtered)} transactions for {town_upper} / {flat_type_upper}")
    print(f"✓ Using most recent {len(sample)} for analysis")

    return sample


# ── Function 3: Format sample data for Claude ─────────────────────────────────
def format_for_claude(sample, town, flat_type, buyer_profile=None):
    """
    Converts the DataFrame sample into a structured text block Claude can
    reason across. Includes the buyer profile so Claude can apply loan
    tenure, TDSR, CPF, and grant rules specific to this buyer.
    None values are passed explicitly — Claude flags what it cannot assess.
    """

    display_cols = ['month', 'storey_range', 'floor_area_sqm',
                    'resale_price', 'remaining_lease']
    table = sample[display_cols].to_string(index=False)

    # Build buyer profile text — include None values so Claude knows
    # which fields are missing and can flag the impact
    profile_text = ""
    if buyer_profile:
        profile_lines = [f"  {k}: {v}" for k, v in buyer_profile.items()]
        profile_text = "\nBuyer profile:\n" + "\n".join(profile_lines)

    formatted = f"""
Buyer criteria:
- Town: {town.upper()}
- Flat type: {flat_type.upper()}
{profile_text}

Most recent {len(sample)} resale transactions (newest first):
{table}

Analyse these transactions and return your assessment as structured JSON.
"""
    return formatted

# ── Function 4: Deterministic HDB string cleaner. Strips code fences/quote wrapping from string sections that aren't JSON ────────────────────────────────────
def clean_analyst_response(raw):
    """
    Strips code fences, quote wrapping, and JSON object wrappers
    from plain string sections. Claude occasionally wraps plain text
    in ```json fences or {"section_name": "..."} objects despite
    instructions — Python cleans it, not the prompt.
    """
    # Remove code fences — ```json and ```
    clean = re.sub(r'```json\s*|\s*```', '', raw)

    # Remove JSON object wrapper if Claude returned {"key": "value"}
    # instead of just the plain string value
    clean = clean.strip()
    if clean.startswith('{') and clean.endswith('}'):
        try:
            parsed = json.loads(clean)
            # Extract the first string value from the object
            for v in parsed.values():
                if isinstance(v, str):
                    clean = v
                    break
        except json.JSONDecodeError:
            pass

    # Remove wrapping quotes if Claude returned "string"
    # instead of just string
    clean = clean.strip()
    if clean.startswith('"') and clean.endswith('"'):
        clean = clean[1:-1]

    return clean.strip()

# ── Function 5: Claude analyst call ───────────────────────────────────────────
def run_analyst_section(client, formatted_data, system_prompt):
    """
    Runs the HDB analyst as seven focused Claude calls — one per section.
    Each section gets only the context it genuinely needs — no blind
    accumulation. Returns a dict keyed by section name.
    Replaces the single 6000-token call from Day 5.
    """

    print("\nRunning HDB analyst — section by section...")
    analyst_start = time.time()
    # Collect results here as each section completes.
    # Later sections that need prior context read from this dict.
    analyst_results = {}
    # Track token usage across all analyst section calls.
    # Accumulated here, returned with results for the run summary.
    analyst_tokens = {"input": 0, "output": 0}

    for section in ANALYST_SECTIONS:
        print(f"  Analysing: {section}...")

        # Build the context block for this section.
        # Start with the raw transaction data and buyer profile —
        # every section needs this as its factual foundation.
        context_parts = [formatted_data]

        # Check if this section depends on any prior section results.
        # ANALYST_SECTION_DEPENDENCIES declares these dependencies explicitly —
        # only the listed prior sections are included, nothing more.
        dependencies = ANALYST_SECTION_DEPENDENCIES.get(section, [])

        if dependencies:
            # Build a focused prior context block — only what this
            # section declared it needs, in a clearly labelled format.
            prior_context = "\n\n## PRIOR ANALYSIS RESULTS\n"
            for dep in dependencies:
                if dep in analyst_results:
                    # Only include if the dependency actually ran —
                    # guards against missing results from failed calls.
                    prior_context += f"\n### {dep.upper()}\n{analyst_results[dep]}\n"
            context_parts.append(prior_context)

        # Add the focused instruction for this specific section.
        # Tells Claude exactly what to reason about and what to return.
        section_instruction = (
            f"\n\n## YOUR TASK\n"
            f"Analyse ONLY the following concern: {section}\n\n"
            f"{ANALYST_SECTION_PROMPTS[section]}"
        )
        context_parts.append(section_instruction)

        # Combine all context into one clean user message.
        user_message = "\n".join(context_parts)

        try:
            response = client.messages.create(
                model=ANALYST_MODEL,           # Sonnet — complex reasoning
                max_tokens=ANALYST_MAX_TOKENS, # Per-section budget from config
                temperature=ANALYST_TEMPERATURE, # Low — keeps analysis factual
                system=system_prompt,          # Standing brief — who Claude is
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Extract the raw text from Claude's response
            raw = response.content[0].text.strip()
            # Accumulate token usage from this section call.
            # response.usage contains input_tokens and output_tokens.
            analyst_tokens["input"] += response.usage.input_tokens
            analyst_tokens["output"] += response.usage.output_tokens

            # top_picks returns a JSON array — parse it into a Python list.
            # All other sections return plain strings — store directly.
           
            if section == "top_picks":
                # Strip code fences first — Claude occasionally wraps
                # the array in ```json fences despite instructions.
                # Same principle as clean_analyst_response() for plain sections.
                clean_raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
                
                # Find the JSON array boundaries — [ to ]
                start = clean_raw.find("[")
                end = clean_raw.rfind("]") + 1
                
                if start == -1 or end == 0:
                    print(f"  WARNING: No JSON array found in top_picks response")
                    analyst_results[section] = []
                else:
                    try:
                        analyst_results[section] = json.loads(clean_raw[start:end])
                        print(f"  ✓ top_picks parsed successfully")
                    except json.JSONDecodeError as e:
                        print(f"  WARNING: Could not parse top_picks — {e}")
                        analyst_results[section] = []
            else:
                # Strip code fences and quote wrapping before storing.
                # Claude occasionally wraps plain text responses despite
                # instructions — clean_analyst_response() handles it in
                # Python rather than relying on prompt instructions.
                analyst_results[section] = clean_analyst_response(raw)
            
            print(f"  ✓ {section} complete")

        except Exception as e:
            # A failed section is logged but doesn't crash the pipeline.
            # The section gets an empty value — downstream rendering handles it.
            print(f"  ERROR: {section} failed — {e}")
            analyst_results[section] = "" if section != "top_picks" else []

    print("✓ Analyst complete — all sections processed")
    analyst_duration = round(time.time() - analyst_start, 1)
    return analyst_results, analyst_tokens, analyst_duration


# ── Function 6: Render one briefing section ───────────────────────────────────
def run_translator_section(client, section_key, analyst_json, buyer_profile,
                   translator_prompt, section_prompts):
    """
    Generates one section of the buyer briefing per Claude call.
    Each section gets its own focused prompt and its own token budget.
    No section can crowd out or truncate another.

    All prompts come in as parameters — none are hardcoded here.
    This keeps the pipeline script free of prompt content.
    """

    # Look up the specific instruction for this section
    # Fallback exists in case an unknown key is passed
    prompt = section_prompts.get(
        section_key,
        "Explain this section in plain English."
    )

    try:
        response = client.messages.create(
            model=TRANSLATOR_MODEL,
            # Look up this section's token budget — falls back to
            # TRANSLATOR_MAX_TOKENS if section key is not found
            max_tokens=TRANSLATOR_SECTION_TOKENS.get(
                section_key, TRANSLATOR_MAX_TOKENS
            ),
            temperature=TRANSLATOR_TEMPERATURE,
            system=translator_prompt,   # Standing brief — the translator persona
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Property analysis:\n{json.dumps(analyst_json, indent=2)}\n\n"
                        f"Buyer profile:\n{json.dumps(buyer_profile, indent=2)}\n\n"
                        f"Your task: {prompt}"
                    )
                }
            ]
        )
        # Return text and token usage as a tuple — briefing loop accumulates tokens
        return response.content[0].text.strip(), {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens
        }

    except Exception as e:
        return f"Could not generate this section: {e}"


# ── Function 7: Build full buyer briefing ─────────────────────────────────────
def run_translator_briefing(client, analyst_json, buyer_profile, town, flat_type,
                         translator_prompt, section_prompts):
    """
    Builds the complete buyer briefing by making one small Claude call per
    section. Each call is focused with its own token budget. No section
    can truncate another.

    Returns two things:
    - briefing_dict: structured Python object — every field accessible by
      future agents and pipeline stages (Day 21+)
    - briefing_text: rendered plain English string for the human reader

    Both come from the same underlying data — the dict is the pipeline
    object, the text is the human output.
    """

    # Section keys in the order they appear in the final briefing
    sections = TRANSLATOR_SECTIONS

    # Human-readable headers for the rendered text output
    section_headers = {
        "summary":             "SUMMARY",
        "what_its_worth":      "WHAT THIS FLAT IS WORTH",
        "lease_explained":     "LEASE — WHAT YOU NEED TO KNOW",
        "location_and_floor":  "LOCATION AND FLOOR",
        "watch_out_for":       "WATCH OUT FOR",
        "grant_and_financing": "GRANT AND FINANCING",
        "before_you_decide":   "BEFORE YOU DECIDE",
        "next_steps":          "NEXT STEPS"
    }

    briefing_dict = {}
    # Track token usage across all analyst section calls.
    # Accumulated here, returned with results for the run summary.
    translator_tokens = {"input": 0, "output": 0}

    # Generate each section independently — one API call per section
    print("\nBuilding buyer briefing...")
    translator_start = time.time()
    for section in sections:
        print(f"  Generating: {section}...")
        section_text, section_tokens = run_translator_section(
            client, section, analyst_json, buyer_profile,
            translator_prompt, section_prompts
        )
        briefing_dict[section] = section_text
        translator_tokens["input"] += section_tokens["input"]
        translator_tokens["output"] += section_tokens["output"]

    # Render the plain English output for the human reader
    # Built from the dict — no extra API call needed
    rendered = []
    rendered.append("=" * 60)
    rendered.append(f"HDB BUYER BRIEFING — {town.upper()} {flat_type.upper()}")
    rendered.append("=" * 60)

    for section in sections:
        rendered.append(f"\n{section_headers[section]}")
        rendered.append("-" * 40)
        rendered.append(briefing_dict[section])

    rendered.append("\n" + "=" * 60)

    briefing_text = "\n".join(rendered)
    translator_duration = round(time.time() - translator_start, 1)
    return briefing_dict, briefing_text, translator_tokens, translator_duration


# ── Main — runs only when this file is executed directly ──────────────────────
if __name__ == "__main__":

    # Initialise the Anthropic client — API key from .env via load_dotenv()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Buyer profile — populate known fields, leave unknowns as None
    # Claude flags every None field and explains what it cannot assess
    BUYER_PROFILE = {
        "age": 51,
        "monthly_income_sgd": 12000,
        "first_time_buyer": True,
        "outstanding_loans": None,    # e.g. car loan monthly repayment
        "cpf_oa_balance": None,       # current CPF Ordinary Account balance
        "budget_ceiling_sgd": 700000,
        "preferred_storey": None,     # "high", "mid", "low", or None
        "citizenship": "SC"
    }

    # Buyer criteria — change these to test different towns and flat types
    TOWN = DEFAULT_TOWN 
    FLAT_TYPE = DEFAULT_FLAT_TYPE

    # Step 1: Fetch filtered, sorted data from the API
    df = fetch_hdb_data(town=TOWN, flat_type=FLAT_TYPE)

    if df is not None:

        # Step 2: Filter and sample to 20 most recent rows
        sample = filter_transactions(df, town=TOWN, flat_type=FLAT_TYPE)

        if sample is not None:

            # Step 3: Format the sample and buyer profile for Claude
            formatted = format_for_claude(
                sample, town=TOWN, flat_type=FLAT_TYPE,
                buyer_profile=BUYER_PROFILE
            )

            # Step 4: Run the analyst — returns structured JSON dict
            analyst_result, analyst_tokens, analyst_duration = run_analyst_section(
                client, formatted, HDB_ANALYST_SYSTEM_PROMPT
            )

            if analyst_result:
                print("\n── Analyst JSON ──")
                print(json.dumps(analyst_result, indent=2))

                # Step 5: Build the buyer briefing section by section
                briefing_dict, briefing_text, translator_tokens, translator_duration = run_translator_briefing(
                    client, analyst_result, BUYER_PROFILE, TOWN, FLAT_TYPE,
                    HDB_TRANSLATOR_SYSTEM_PROMPT, HDB_SECTION_PROMPTS
                )

                # Print the plain English briefing for the human reader
                print("\n── Buyer Briefing ──")
                print(briefing_text)

                # Confirm the pipeline dict is ready for future agents
                # On Day 21, downstream agents consume briefing_dict directly
                print("\n── Pipeline object ready ──")
                print(f"Fields available: {list(briefing_dict.keys())}")
                # ── Token usage summary ───────────────────────────────────────────
                # Printed at end of every run — tracks cost and section efficiency
                total_input = analyst_tokens["input"] + translator_tokens["input"]
                total_output = analyst_tokens["output"] + translator_tokens["output"]
                total_duration = round(analyst_duration + translator_duration, 1)

                print("\n── Run Summary ──")
                print(f"  Analyst    — input: {analyst_tokens['input']:,}  output: {analyst_tokens['output']:,} duration: {analyst_duration}s")
                print(f"  Translator — input: {translator_tokens['input']:,}  output: {translator_tokens['output']:,}  duration: {translator_duration}s")
                print(f"  TOTAL      — input: {total_input:,}  output: {total_output:,}  duration: {total_duration}s")