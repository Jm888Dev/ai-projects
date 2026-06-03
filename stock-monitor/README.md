**Stock Market AI Monitor**

README — Project Documentation

# **What It Does**

An AI-powered market intelligence tool that fetches live prices for a curated portfolio of stocks and ETFs, sends them to Claude for structured analysis, and produces a plain English briefing — automatically, every run.

Built as part of a 30-day AI development program using the Anthropic API.

- Fetches real-time prices for 8 instruments via yfinance (NVDA, AVGO, LITE, TSM, QQQ, SMH, G3B.SI, ^VIX)

- Sends price data to Claude Sonnet for structured JSON analysis — market tone, notable movers, VIX signal, concentration risk, buy list impact, watch tomorrow

- Passes analyst output to Claude Haiku for a plain English briefing

- Prints a run summary with token usage and duration

# **Requirements**

- Python 3.12+

- Anthropic API key (stored in .env)

- Packages: anthropic, python-dotenv, yfinance

# **Setup**

- Clone the repo and navigate to the project folder

- Create and activate a virtual environment:

python -m venv myenv

myenv\Scripts\activate

- Install dependencies:

pip install anthropic python-dotenv yfinance

- Create a .env file in the project root:

ANTHROPIC_API_KEY=your_key_here

- Run:

python stock_monitor.py

# **Configuration**

All settings live in config.py — edit there, not in the pipeline script.

| **Constant** | **What it controls** |
| --- | --- |
| **ANALYST_MODEL** | Claude model for market analysis (default: Sonnet) |
| **TRANSLATOR_MODEL** | Claude model for plain English briefing (default: Haiku) |
| **ANALYST_MAX_TOKENS** | Token budget for analyst response |
| **TRANSLATOR_MAX_TOKENS** | Token budget for translator response |
| **ANALYST_TEMPERATURE** | Randomness for analyst (default: 0.2 — factual) |
| **TRANSLATOR_TEMPERATURE** | Randomness for translator (default: 0.5 — natural) |
| **TICKERS** | List of instruments to track — add or remove here |

# **Output**

Each run produces:

- Live price table for all tracked instruments

- Structured JSON analysis from Claude Sonnet

- Plain English market briefing from Claude Haiku

- Run summary with token counts and duration

# **Known Limitations**

- G3B.SI (STI ETF) may return null outside Singapore Exchange hours

- ^VIX price data can behave unexpectedly — handled gracefully

- No persistent storage yet — each run is independent (Day 8)

- No scheduling yet — must be run manually (Day 12)

# **Project Structure**

stock-monitor/

    stock_monitor.py        # Main pipeline

    config.py               # All constants — edit here

    prompts/

        analyst_persona.py  # Claude system prompts

    .env                    # API key — never commit this

    .gitignore