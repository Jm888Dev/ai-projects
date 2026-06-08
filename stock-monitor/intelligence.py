# intelligence.py
# Manual intelligence context for the current session.
# Updated before each live run with the day's relevant signals.
#
# This is the manual stub — automated RSS pipeline replaces the
# contents (not the structure) on Day 13-15. The shape of this
# dict is the contract. The pipeline and agents depend on these
# exact keys. Do not rename them.
#
# How to update before a live run:
#   1. Skim your morning feeds — Import AI, Straits Times, FT, Reuters
#   2. Fill in what is signal (not noise) across the five categories
#   3. Save the file — the pipeline reads it at run time
#   4. After Day 13-15, the RSS pipeline fills this automatically

INTELLIGENCE_CONTEXT_TODAY = {

    # Current macroeconomic conditions — the frame everything else sits in
    # Fed stance, rate environment, dollar strength, key upcoming events
    "macro_regime": {
        "fed_stance":        "data-dependent, paused at current rate",
        "rate_environment":  "10Y UST at 4.2%, stable",
        "dollar_strength":   "USD/SGD 1.34, stable",
        "key_macro_signal":  "No major macro events this week"
    },

    # Geopolitical signals relevant to the portfolio
    # Focus: Taiwan, US-China tech controls, Middle East, Singapore
    # Each entry is one signal — specific, not generic
    "geopolitical_signals": [
        "Taiwan strait — no new escalation signals this week",
        "US-China export controls — no new restrictions announced",
        "Singapore — MAS policy stance unchanged"
    ],

    # AI and quantum research signals
    # Focus: breakthroughs affecting NVDA, AVGO, LITE, TSM thesis
    # Source: Import AI, arXiv, Anthropic blog, DeepMind blog
    "ai_research_signals": [
        "No major model releases or architecture announcements this week",
        "Hyperscaler CapEx guidance — no updates since last earnings cycle"
    ],

    # Regulatory signals affecting the portfolio or AI sector broadly
    # Focus: SEC, MAS, EU AI Act, semiconductor export controls
    "regulatory_signals": [
        "No new semiconductor export control announcements",
        "EU AI Act implementation — no material updates this week"
    ],

    # Market sentiment signals
    # Focus: retail positioning, institutional flows, contrarian indicators
    # Source: Reddit PRAW, AAII survey, options flow (manual observation)
    "sentiment_signals": {
        "retail_positioning":    "neutral — no strong directional bias observed",
        "institutional_flows":   "no notable rotation signals this week",
        "contrarian_indicator":  "AAII bull-bear spread — not checked this session"
    }
}