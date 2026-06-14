**HDB Resale Buyer Analyser**

README — Project Documentation

# **What It Does**

An AI-powered buyer intelligence tool that fetches real HDB resale transaction data from data.gov.sg, runs a structured multi-section analysis using Claude, and produces a plain English buyer briefing — grounded in real government data and Singapore property rules.

Built as part of a 30-day AI development program using the Anthropic API.

- Fetches live HDB resale transaction data from data.gov.sg API

- Filters by town and flat type, samples the 20 most recent transactions

- Runs 7 focused analyst calls via Claude Sonnet — one per concern: value assessment, lease flag, financing, upfront costs, location signal, red flags, top picks

- Builds a plain English buyer briefing via Claude Haiku — 8 sections: summary, what it’s worth, lease explained, location and floor, watch out for, grant and financing, before you decide, next steps

- Applies Singapore-specific rules: MSR cap, LTV limits, age-65 trigger, CPF OA rules, BSD tiers, EHG grant eligibility, MOP classification

- Prints a run summary with token usage and duration per stage

# **Requirements**

- Python 3.12+

- Anthropic API key (stored in .env)

- Packages: anthropic, python-dotenv, requests, pandas

# **Setup**

- Clone the repo and navigate to the project folder

- Create and activate a virtual environment:

python -m venv myenv

myenv\Scripts\activate

- Install dependencies:

pip install anthropic python-dotenv requests pandas

- Create a .env file in the project root:

ANTHROPIC_API_KEY=your_key_here

- Run:

python hdb_analyser.py

# **Configuration**

All settings live in config.py — edit there, not in the pipeline script.

| **Constant** | **What it controls** |
| --- | --- |
| **ANALYST_MODEL** | Claude model for analysis (default: Sonnet) |
| **TRANSLATOR_MODEL** | Claude model for briefing (default: Haiku) |
| **ANALYST_TEMPERATURE** | Randomness for analyst (default: 0.2 — factual) |
| **TRANSLATOR_TEMPERATURE** | Randomness for translator (default: 0.5 — natural) |
| **FETCH_LIMIT** | Raw records pulled from data.gov.sg (default: 500) |
| **SAMPLE_SIZE** | Records passed to Claude after filtering (default: 20) |
| **REQUEST_TIMEOUT** | API call timeout in seconds (default: 15) |
| **DEFAULT_TOWN** | Default town for buyer query (default: SENGKANG) |
| **DEFAULT_FLAT_TYPE** | Default flat type (default: 4 ROOM) |
| **ANALYST_SECTIONS** | The 7 analyst concern sections — in order |
| **TRANSLATOR_SECTIONS** | The 8 buyer briefing sections — in order |
| **ANALYST_SECTION_DEPENDENCIES** | Which prior sections each analyst section needs |
| **TRANSLATOR_SECTION_TOKENS** | Per-section token budgets for translator |

## **Data Source**

Transaction data is sourced from the Singapore government’s open data portal via the data.gov.sg API.

| **Constant** | **What it controls** |
| --- | --- |
| **API_BASE_URL** | data.gov.sg API endpoint |
| **HDB_RESOURCE_ID** | Dataset ID — Resale flat prices from Jan 2017 onwards |

Both are defined in config.py. Update there if the endpoint or dataset changes. The dataset is maintained by HDB and updated monthly.

# **Buyer Profile**

Edit the BUYER_PROFILE dict in hdb_analyser.py to match your buyer. Unknown fields should be set to None — Claude flags what it cannot assess.

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

# **Output**

Each run produces:

- Structured JSON analyst output — 7 sections, one per concern

- Plain English buyer briefing — 8 sections including next steps

- Pipeline dict object ready for downstream agents (Day 21)

- Run summary with token counts and duration per stage

# **Known Limitations**

- Analysis is TOWN-RELATIVE — no national comparison data yet (Day 13)

- Buyer profile is hardcoded — conversational input added on Day 21

- Regulatory figures are indicative — RAG over official sources on Day 19-20

- No web interface yet — Streamlit dashboard on Day 28

- Buyer must obtain HDB Flat Eligibility (HFE) letter to confirm all figures

# **Project Structure**

hdb-analyser/

    hdb_analyser.py         # Main pipeline

    config.py               # All constants — edit here

    prompts/

        analyst_persona.py  # Claude system prompts — analyst and translator

    .env                    # API key — never commit this

    .gitignore