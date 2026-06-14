
Mack | 30-Day AI Dev Journey
I am Mack — an enterprise IT engineer at a global bank (engineering team, not ops). I am on a 30-day AI development journey to go from prompt engineer to credible AI builder. Read both uploaded documents before responding: 1. Mack_30Day_Master_Plan.docx — full context, projects, learning goals, 30-day schedule, deep review 2. Mack_Day1_Command_Reference.docx — every command from Day 1 setup with explanations MY SETUP - Machine: Acer Swift Go 14, i9, 32GB RAM, Windows 11 - Environment: Python 3.12, VS Code, Git, GitHub - Venv: C:\Users\Mack\ai-projects\stock-monitor\myenv - Claude API: Connected and tested - SQL: Advanced level — a genuine strength MY STYLE - I am on a mobile screen often — keep responses concise and structured - I learn by building, not watching - Challenge my thinking — don't just agree - When I'm drifting from the plan, tell me - Use the Thinking Canvas approach for complex problems before jumping to solutions CURRENT STATUS - Day 1: Complete - Next: Day 2 — first real pipeline
Show more



How can I help you today?


Day 15 progress
Last message 14 minutes ago
Multi-agent debate loop for investment analysis
Last message 4 hours ago
Using agent swarms for project execution
Last message 15 hours ago
Day 11 pipeline hardening and database verification
Last message 23 hours ago
Aligning sessions with AI Builder Master Plan
Last message yesterday
Improving a write-up draft
Last message yesterday
Neo4j and Pinecone for knowledge graphs
Last message 2 days ago
Mapping company relationships through ownership networks
Last message 3 days ago
vikk
Last message 3 days ago
Day 9 begins
Last message 4 days ago
Capturing stop message for API calls and EOS
Last message 5 days ago
Mind mapping project connections
Last message 7 days ago
Stock ticker fund exposure analysis
Last message Jun 5
Multi-agent debate and SWOT analysis
Last message Jun 5
Day 6 start
Last message Jun 5
Learning langchain and langraph
Last message Jun 5
Day 5 beginning
Last message Jun 1
Building an agentic workflow
Last message May 31
Starting day four
Last message May 31
Starting day three
Last message May 30
Day 2 progress check-in
Last message May 29
Memory
Only you
Purpose & context Mack is an Enterprise IT Engineer at a global bank in Singapore, executing a self-directed 30-day AI development program with a Day 30 leadership demo as the target milestone. His longer-term goal is transitioning into an AI ops role. He won an internal prompt engineering competition and uses this program as a structured capability-building exercise — building real, production-adjacent tools rather than toy examples. Two primary projects are under construction: Stock Market AI Monitor (stock-monitor): A multi-agent adversarial pipeline tracking a semiconductor supply chain thesis portfolio HDB Resale Buyer Analyser (hdb-analyser): A Singapore public housing buyer intelligence tool using government transaction data A Days 31–60 plan is formally scoped: deepen both projects, explore the Hermes Agent (ICLR 2026 companion: hermes-agent-self-evolution), formally design Hermes around Day 28, and build a knowledge graph at Days 45–55. Mythos patching pipeline is dropped entirely. Background & skills: Strong SQL, lapsed-beginner Python (rebuilding through doing). Systemic divergent thinker — consumes widely across AI research, philosophy, geopolitics, and markets, arrives at conclusions intuitively before articulating reasoning, and uses pushback as a primary design tool. Curiosity is an asset that needs guardrails to land on the right things at the right time. Uses these sessions to think through problems he wouldn't raise with colleagues. Investment philosophy (Stock Monitor context): Core stability (G3B.SI, QQQ, SMH) → thematic growth (NVDA, TSMC, AVGO) → frontier bets (LITE, quantum — small sizing). Years-not-decades horizon, Berkshire patience on core, informed conviction on thematic, managed risk on frontier. Quantum tickers (IONQ, RGTI, QUBT, IBM) ready to add post-Day 30 via a single config.py line. G3B.SI diversification thesis flagged for re-evaluation at Days 31–60 — Meta-Agent already identified it as a potential false diversifier on the first live run. Visual preference: All briefing artifacts use warm dark palette (lifted background #18181F, warm off-white text #EDE8DC, amber/coral/gold/rose accents, no blues or cool greens, larger text, thicker borders). --- Current state Mack is at Day 11, with the following completed and in place: Stock Monitor pipeline (fully operational): Six-agent adversarial architecture live: Bull, Bear, Black Swan, Pragmatist (Stage 1, Haiku, temp 0.5–0.7), Contrarian (Stage 2, Sonnet, temp 0.7), Meta-Agent (Stage 3, Sonnet, temp 0.1) Structured JSON output contracts per agent; Meta-Agent returns ACCUMULATE/HOLD/REDUCE/EXIT + 3 kill triggers per ticker stored in signals table DEVMODE flag (default True): all-Haiku routing; production uses Sonnet routing USELIVEDATA (default False), USELIVEAGENTS (default False), DEVMODE (default True) — all currently at dev defaults Three capture flags: CAPTURELIVEDATAFORFIXTURES, CAPTURELIVEAGENTSFORFIXTURES, USELIVEAGENTS — 37 agent fixture files populated via live capture run callllm() wrapper with fixture load/capture logic; hard stop (not silent fallback) when fixtures missing thesisdrafts and thesisreviews tables added; checkthesisstaleness() runs non-blocking at session start thesisoverrides.json with deepupdate() and utf-8-sig encoding (Windows BOM fix) compress() function reducing Meta-Agent input tokens significantly personacalls table tracking directional calls per persona/ticker/session with confidence, regime tag, VIX level, rationale Run summary shows agent mode, dev mode, duration, stale thesis count, grouped call types Cost tracking: MODELPRICING in config.py, costusd on llmcalls, computecallcost(), balanceledger table stopreason captured in callllm() usage dict HDB Analyser: Operational pipeline fetching data.gov.sg transactions, running structured analysis through Claude, generating section-by-section buyer briefings. Regulatory verification discipline locked in (all figures indicative, subject to HFE letter confirmation). Shared infrastructure: shared/utils.py with callllm() and extractjson(); shared/datasources.py abstracting all external reads; config.py centralised across both projects; nine-table SQLite schema live. Environment: Python on Windows 11 (PowerShell), VS Code, virtual environment myenv, project at C:\Users\Mack\ai-projects\stock-monitor, GitHub repo Jm888Dev/ai-projects. Tickers: NVDA, AVGO, LITE, TSM, QQQ, SMH, G3B.SI, ^VIX. Deferred from Day 11 to Day 12: Correlation health checks, email alerts via SMTP, outcome scoring stub. Day 12 must begin with a call chain map and session reorientation before any code — Mack explicitly requested this given how much the project has grown. --- On the horizon Immediate (Days 12–16): Day 12: Call chain map + reorientation first; then correlation health checks, SMTP email alerts, outcome scoring stub Day 13: National HDB sample fetch; buyer criteria expansion (OneMap API, feng shui flags, amenities/transport proximity, MoneySmart guide); national context for valueassessment; HDB Devil's Advocate + Optimist personas (devil's advocate must challenge whether comparison sample is large/recent enough) Day 14: Watch item parser, feed triggers for thesis maintenance; adversarial lenses for Stock Monitor Day 15: Truncation counter added to run summary (stopreason already captured); formal observability pass; Translator prompt rewrite for complete beginner audience (stricter jargon rules, concrete before/after examples, plain English equivalents list, real-world analogies only — may need token budget adjustment); "beginner investment concepts" layer explaining what signals mean and what to do with them Day 16: Formal codebase scrutiny day — Opus 4.8 reviews architecture, persona prompts against personacalls accuracy data, full codebase; produces refactor priorities, banking governance gaps, Day 17–24 sequence adjustments; Mack decides what to action. Day 11 = optional 2hr persona prompt review after 3 sessions of data Days 17–30: Day 17: Orchestrator design (one per project) Day 18: Tool vocabulary defined Day 19: ChromaDB for RAG (local first; Pinecone as deliberate comparison at Day 31+) Day 20: HDB RAG pipeline including routing pattern; regulatory RAG layer Day 21: First agent loops; premortem agent (fires on specific failure conditions, not calendar); full premortem loop deferred here Day 22: Stateful memory agents; section-level AI thesis drafts with rejection history awareness Day 25: SLM day — Gemma 3 4B quantized via Ollama (primary, runs on CPU); Gemma 4 12B via Ollama (stretch, CPU-only slow); callllm() wrapper makes this a one-line config change; hands-on SLM learning experience Day 26: Observability; D3.js radial tree architecture map generated from codebase file structure and call traces (not hand-coded) Day 28: Streamlit review UI for thesis; thesisoverrides.json UI; formal Hermes Agent design session; Days 31–60 planning Day 30: Leadership demo Days 31–60: Deepen Stock Monitor: two-layer storyline architecture (Layer 1 = weekly narrative in Magnifica Humanitas register connecting AI research, geopolitics, human meaning — never filtered through investment intent; Layer 2 = separate plain language investment commentary referencing Layer 1, flagging thesis changes not price moves) Intelligence feeds: 22 curated RSS/API sources across 6 domains (AI, Quantum, Geopolitics, Current Affairs with SG/JP/EU/US/CN lenses, Social Sentiment via Reddit PRAW, Tech). Manual-only sources (not automated): The Rundown, TLDR, Professor Casey AI Ethics. Four regional lenses: Singapore, Japan, Europe, US Hermes Agent (hermes-agent-self-evolution, ICLR 2026) — learn foundation first, then build; not forced into earlier pipeline Knowledge graph Days 45–55: 6 layers — ownership (13F/ETF CSVs), shared holders (computed), supply chain (manual), revenue exposure, geographic concentration, regulatory linkage; entitya/relationship/entityb schema reserved; intelligence feed headlines trigger 2-degree graph traversal. Day 45=Layer 1, Day 50=Layer 2, Day 55=Layers 3–6 Neo4j introduced at Days 45–55 when graph density justifies traversal advantages (not front-loaded) G3B.SI diversification thesis: proper re-evaluation once knowledge graph and regional lenses are built Quantum tickers (IONQ, RGTI, QUBT, IBM) added via single config.py line RAG backend comparison: swap ChromaDB for Pinecone after Day 31 as deliberate learning comparison Deferred items tracked: Narrator stub (Layer 1 weekly storyline, Magnifica Humanitas register) in analystpersona.py — full implementation Days 13–14 Translator prompt rewrite for complete beginner — Day 15 Ruff linter — Day 16 shared/utils.py README — Day 16 Model drift management — Days 26–27 Async pipeline execution — Day 17 (currently sequential) Full data dictionary assembled from daily deltas — end of project (deltas started Day 10 onward) --- Key learnings & principles Concepts local first, managed cloud as deliberate comparison: ChromaDB before Pinecone, SQLite before Neo4j — tool strengths only become visible at appropriate scale and complexity Build IS the learning: Design work and AI literacy are complementary, not competing; structured reading is the counterbalance Hard stops over silent fallbacks: When fixtures are missing or a condition is unrecoverable, the system should halt and surface the problem explicitly, not degrade silently Separation of concerns: All prompts live in analystpersona.py as named constants; zero prompt content in pipeline scripts; data abstraction through datasources.py Regulatory data handling: All financial/regulatory figures are indicative and subject to primary-source confirmation; dangerous to produce confident wrong numbers on large-ticket decisions Divergence signal discipline: Only directional divergence (score 2–3) persisted to signals table; magnitude divergence noted but not stored; agreement written as consensus signal for later challenge; stale unresolved divergences auto-escalate after 5 sessions Five POC wins before scaling: Build small, demonstrate intermediate value, then accelerate Wrong answer first: Mack works best when the incorrect approach is presented so he can articulate precisely what the right answer needs to be Warning message standard (three questions): What happened (with variable values) / where / concrete fix action Naming conventions matter: Flag and function names must be unambiguous and distinguishable in tracebacks; avoid plural/near-identical names --- Approach & patterns Session opening: Every Day session begins with an interactive React "Day X Briefing" artifact before any code — dark theme, tabbed, mobile-first, checkable items, progress bar, four sections: What You're Building / Key Concepts / Why It Matters / Research & Prep Confirm alignment before building: Lock design decisions explicitly before implementation; call chain map and reorientation before Day 12 code Explain every command and line: Inline comments in all code explaining what each section does and why it's there — not just what the code says but how it fits the overall program State the directory: Always specify which directory to run from Verify before proceeding: Confirm previous steps completed successfully before moving forward GitHub commit at session end: Every productive session ends with a commit and push; Day N summary .docx generated for Project Knowledge upload Data dictionary delta: Every Day summary .docx includes a delta of new tables, columns, config constants, functions, and output schemas added that day Pushback as design tool: Mack challenges answers that feel architecturally weak; this is productive signal, not obstruction Sequential discipline over pre-emptive architecture: Lock decisions, execute in order, resist scope expansion mid-session One change at a time during complex multi-file edits --- Tools & resources Languages/runtime: Python 3.14, Windows 11, PowerShell, VS Code AI APIs: Anthropic Claude API — Haiku 4.5 (DEV_MODE), Sonnet 4.6 (production analyst), Opus 4.8 (Day 16 scrutiny and frontier tasks) Pricing (June 2026): Haiku 4.5 $1/$5, Sonnet 4.6 $3/$15, Opus 4.8 $5/$25 per million input/output tokens Data: yfinance (market data), data.gov.sg API (HDB transactions), OneMap API (planned Day 13) Storage: SQLite (prices.db), fixture JSON files Future storage: ChromaDB (Day 19, local RAG), Neo4j (Days 45–55, knowledge graph), Pinecone (post-Day 31 comparison) SLM (Day 25): Ollama — Gemma 3 4B quantized (primary), Gemma 4 12B (stretch, CPU-only) Hardware: Acer Swift Go 14, i9, 32GB RAM Version control: Git/GitHub (Jm888Dev/ai-projects) Intelligence sources: Import AI, The Rundown, TLDR, Substack, Professor Casey AI Ethics, Magnifica Humanitas (Pope Leo XIV 2026 encyclical), Straits Times, Japan Times, FT, Guardian, Reddit/PRAW, arXiv, institutional AI/Quantum blogs Course: Skilljar Claude API course (target completion Day 12) Investments (accessible): BGF World Technology Fund (BlackRock) as accessible proxy for SMH; direct equities through Singapore broker

Last updated 6 hours ago

Instructions
I am Mack — an enterprise IT engineer at a global bank (engineering team, not ops). I am on a 30-day AI development journey to go from prompt engineer to credible AI builder and developer. ALWAYS READ FIRST Before responding, read all documents in Project Knowledge. They include my AI Builder master plan, day references, daily summaries, codebase, session ledger and prep briefing notes. Always use them to orient before answering. MY SETUP - Machine: Acer Swift Go 14, i9, 32GB RAM, Windows 11 - User account: Mack (not Administrator) - Python 3.14, VS Code, Git, GitHub — all configured - Venv: C:\Users\Mack\ai-projects\stock-monitor\myenv - Claude API: Connected and tested (hello_claude.py works) - Packages installed: anthropic, python-dotenv, pandas, requests, yfinance, sqlalchemy - SQL: Advanced level — a genuine strength - Python: Lapsed beginner — I can read and modify code but need explanations and hand-holding on new concepts MY TWO PROJECTS 1. Stock Market AI Monitor — live prices, Claude commentary, threshold alerts, scheduled automation 2. HDB Housing Analyser — buyer-focused, HDB.gov.sg data, RAG over transactions, Claude recommendations CURRENT STATUS Update this section at the start of each new day: - Days complete: 2 - Last built: stock-monitor.py — ETL for yfinance working - Current day: 3 - Today's goal: working with Json - Documents in Project Knowledge: Master Plan, Day 1 Reference, Stock Monitor Design, Briefing, Summary ABOUT HOW I THINK - I am a systems thinker — I understand problems better when I see how parts connect to the whole. Always show me the big picture before drilling into details - I am a divergent thinker — I naturally explore multiple directions and make unexpected connections. This is a strength but can cause scope creep. Help me channel divergence into the current build rather than new ideas - When I go wide, help me go deep instead - I find cross-domain analogies energising — connect AI concepts to banking, systems architecture, geopolitics or real-world processes I already understand HOW TO TEACH ME - I am a beginner builder — explain every line of code, not just what it does but WHY it is written that way - Never give me code without explaining it first - When introducing a new concept, explain the mental model before showing the code - Use real-world analogies — I understand systems , data and banking processes well - After every code block, tell me what I should see when it runs successfully - Tell me what could go wrong and how to recognise it - Build confidence — celebrate small wins, they matter - If I paste an error, diagnose it step by step like a senior developer would with a junior - When I am confused, slow down and try a different explanation before moving forward HOW TO STRUCTURE SESSIONS - Start each session by confirming what day I am on and what we are building - Reference the 30-day plan to keep me on track - If I am drifting, flag it gently but firmly - Break every task into small numbered steps — one thing at a time - Do not give me the next step until I confirm the current one worked - End each session with a summary of what we built, what is committed, and what is next HOW TO CHALLENGE ME - Use the Thinking Canvas approach for complex problems — map the problem before jumping to solutions - Separate facts from assumptions when I describe a problem - If I propose something that will not work, tell me clearly and explain why - Do not agree just to be agreeable — I need honest feedback to grow - When I am about to make a mistake, warn me before I make it MY LEARNING STYLE - I learn by building, not watching or reading - I need to understand the why, not just the how - I respond well to structure — numbered steps, clear sections, concrete examples - I am often on mobile — keep responses concise where possible but never sacrifice clarity for brevity when code is involved - I ask a lot of questions — encourage this and answer thoroughly DOCUMENT CONVENTION I will upload a briefing for prep each day using this naming pattern: - Day2_Summary — what I built, what worked, what broke, what is next - Day3_Briefing — goals and questions before starting Read all documents present before each session. THINGS TO ALWAYS DO Explain every command and every line of code Tell me which folder to run commands from Remind me to activate myenv if relevant Check that previous steps worked before moving on Commit to GitHub at the end of every productive day Keep both projects moving — do not let one stall All inline code comments must explain why the code exists and how it fits the overall program, not just what it does Every warning and error message must answer three questions: What happened — the specific condition that fired, including the variable values involved Where it happened — which function, which model, which ticker if relevant What to do about it — a concrete action the developer can take to resolve it Format: [MODULE] WARNING/ERROR: {what happened} — {where} — Fix: {what to do} Examples: Bad: [DB] WARNING: no pricing found for model — cost set to 0 Good: [DB] WARNING: no pricing found for model 'claude-opus-4-8' in compute_call_cost() — cost recorded as $0.00. Fix: add 'claude-opus-4-8' to MODEL_PRICING in config.py This applies to: All print() warning statements All except block messages All graceful degradation paths Any place the pipeline continues despite an unexpected condition THINGS TO NEVER DO - Never skip explaining a concept because it seems obvious - Never give me a wall of code without explanation - Never assume I know why something is done a certain way - Never let me end a session without a GitHub commit if we wrote code - Never let scope creep add new topics without finishing current ones

Files
4% of project capacity used
Search mode

DATA_DICTIONARY.md
436 lines

md



SESSION_LEDGER.md
88 lines

md



Day14_Summary.docx
153 lines

docx



OPEN_QUESTIONS.docx
156 lines

docx



CODEBASE_MAP.md
156 lines

md



Day13_Summary.docx
137 lines

docx



AI_Builder_Master_Plan_Days_1-60_v1-1.md
333 lines

md



Day12_Summary.docx
152 lines

docx



Day12_Codebase_Map.docx
222 lines

docx



Day11_Summary.docx
239 lines

docx



Day10_Summary.docx
368 lines

docx



Day9_Summary.docx
260 lines

docx



Day8_Summary.docx
164 lines

docx



Day7_Summary.docx
121 lines

docx



README_Stock_Monitor.docx
99 lines

docx



README_HDB_Analyser.docx
146 lines

docx



Day6_Summary.docx
122 lines

docx



Day5_Summary.docx
142 lines

docx



Day4_Summary.docx
97 lines

docx



day4_briefing.html
460 lines

html



Day3_Summary.docx
86 lines

docx



Day2_Summary.docx
85 lines

docx



Mack_Stock_Monitor_Universe_v2-1.docx
96 lines

docx



Mack_Day1_Command_Reference.docx
243 lines

docx


Mack_Day1_Command_Reference.docx
**Day 1 Command Reference**
 
Mack · AI Development Setup · Everything you ran and what it means
 
────────────────────────────────────────────────────────────────────────────────
 
**1. Python Setup**
 
**▸**** Check Python is installed**
 
python --version
 
Asks your system which version of Python is installed. If it returns 'Python 3.x.x' you're good. If not, Python isn't on your PATH.
 
**▸**** Check where Python lives**
 
where.exe python
 
Shows the exact file path of your Python installation. Useful for diagnosing whether Python installed for your user only or system-wide.
 
**▸**** Check pip is available**
 
pip --version
 
pip is Python's package manager — it installs libraries. This confirms pip is ready to use.
 
**2. Virtual Environments**
 
**▸**** Create a virtual environment**
 
python -m venv myenv
 
Creates an isolated Python environment called 'myenv' inside your current folder. Think of it as a clean room — packages installed here don't affect anything else on your system. Always do this per project.
 
**▸**** Activate the virtual environment (Windows)**
 
myenv\Scripts\activate
 
Switches your terminal into the isolated environment. You'll see (myenv) appear at the start of your prompt. Every pip install after this goes into this environment only.
 
**▸**** Confirm venv is active**
 
(myenv) PS C:\...> appears at prompt
 
When you see (myenv) you are inside your virtual environment. This must be showing before you install packages or run your code.
 
**▸**** Fix script execution error (one-time setup)**
 
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
 
Windows blocks PowerShell scripts by default. This unlocks scripts for your user account only. RemoteSigned means your own scripts run freely, downloaded ones need a digital signature. You only need to run this once per user account.
 
**3. Installing Packages**
 
**▸**** Install all core libraries at once**
 
pip install anthropic python-dotenv pandas requests yfinance sqlalchemy
 
Installs six libraries:
  • anthropic — Claude API client
  • python-dotenv — reads your .env file
  • pandas — data manipulation
  • requests — HTTP calls to web APIs
  • yfinance — Yahoo Finance stock data
  • sqlalchemy — database toolkit
 
**▸**** List all installed packages**
 
pip list
 
Shows everything installed in your current environment. Useful to verify a package installed correctly.
 
**4. Project Files ****&**** Security**
 
**▸**** .env file — stores your secrets**
 
ANTHROPIC_API_KEY=sk-ant-xxxxx
 
Stores your secret API key. Never hardcode keys directly in your Python files. This file must NEVER be pushed to GitHub — always keep it local.
 
**▸**** .gitignore file — tells Git what to ignore**
 
myenv/
.env
__pycache__/
*.pyc
 
Tells Git which files/folders to skip:
  • myenv/ — your virtual environment (too large for GitHub)
  • .env — your secret keys
  • __pycache__/ — Python's auto-generated cache
  • *.pyc — compiled Python bytecode
 
**▸**** Load .env in Python**
 
from dotenv import load_dotenv
load_dotenv()
 
Reads your .env file and makes its values available to your Python script. Always call load_dotenv() before trying to read your API key.
 
**▸**** Read API key in Python**
 
os.getenv('ANTHROPIC_API_KEY')
 
Fetches the value of ANTHROPIC_API_KEY from environment variables. Returns None if not found — check this when debugging authentication errors.
 
**5. First Claude API Call**
 
**▸**** Full hello_claude.py script**
 
import anthropic
import os
from dotenv import load_dotenv
 
load_dotenv()
 
client = anthropic.Anthropic(
    api_key=os.getenv('ANTHROPIC_API_KEY')
)
 
message = client.messages.create(
    model='claude-haiku-4-5-20251001',
    max_tokens=1024,
    messages=[
        {'role': 'user', 'content': 'Say hello.'}
    ]
)
 
print(message.content[0].text)
 
What each part does:
  • load_dotenv() — loads your API key from .env
  • anthropic.Anthropic() — creates the Claude client
  • client.messages.create() — sends your message to Claude
  • model — which Claude to use (Haiku = cheapest, good for learning)
  • max_tokens — max length of Claude's response
  • message.content[0].text — extracts Claude's reply as plain text
 
**▸**** Run your Python file**
 
python hello_claude.py
 
Executes your script. Must be run from the folder containing the file, with (myenv) active in your terminal — not from inside the Python CLI (>>>).
 
**6. Git ****&**** GitHub**
 
*Git is a version control system — it tracks every change you make to your code. GitHub is where your code lives online (your portfolio). They work together.*
 
**▸**** Check Git is installed**
 
git --version
 
Confirms Git is installed and shows the version.
 
**▸**** Set your name globally (one-time)**
 
git config --global user.name "Mack"
 
Attaches your name to every commit you make. --global means it applies to all projects on this machine.
 
**▸**** Set your email globally (one-time)**
 
git config --global user.email "you@email.com"
 
Your email is also attached to every commit. Use the same email as your GitHub account so commits link to your profile.
 
**▸**** Initialise Git in a folder**
 
git init
 
Turns your current folder into a Git repository — Git starts tracking it. Creates a hidden .git folder. Only needed when starting fresh without cloning.
 
**▸**** Clone a GitHub repo to your machine**
 
git clone https://github.com/USERNAME/repo.git
 
Downloads a repository from GitHub and automatically links it. Use this when the repo already exists on GitHub.
 
**▸**** Link local folder to GitHub repo**
 
git remote add origin https://github.com/USERNAME/repo.git
 
Connects your local folder to a GitHub repo. 'origin' is the standard nickname for your remote repo. Use this when you ran git init locally first.
 
**▸**** Pull latest changes from GitHub**
 
git pull origin main
 
Downloads and merges the latest changes from GitHub into your local folder. Always pull before starting work to stay up to date.
 
**▸**** Rename branch to main**
 
git branch -M main
 
Renames your current branch to 'main'. Older Git versions default to 'master' — this aligns with the modern GitHub standard.
 
**▸**** Check what has changed**
 
git status
 
Shows which files have been modified, added, or deleted since your last commit. Red = not staged. Green = staged and ready to commit.
 
**▸**** Stage all changes for commit**
 
git add .
 
Tells Git to include ALL changed files in your next commit. The dot means 'everything in this folder'. You can also stage one file: git add filename.py
 
**▸**** Create a commit (save point)**
 
git commit -m "Initial setup - hello_claude working"
 
Creates a permanent save point with all staged changes. The -m message describes what changed. Write clear messages — your future self will thank you.
 
**▸**** Push commits to GitHub**
 
git push origin main
 
Uploads your commits to GitHub. 'origin' = your remote repo. 'main' = the branch. Your code is now backed up and visible on GitHub.
 
**7. Terminal Navigation**
 
**▸**** Navigate to a folder**
 
cd C:\Users\Mack\ai-projects\stock-monitor
 
Changes your terminal's current location. cd = change directory. Always navigate to your project folder before running Python files or Git commands.
 
**▸**** List files in current folder**
 
ls
 
Shows all files and folders in your current location. Useful for confirming a file exists before trying to run it.
 
**▸**** Move a file**
 
move myenv\.env .
 
Moves a file to a new location. The dot at the end means 'move here, into the current folder'.
 
────────────────────────────────────────────────────────────────────────────────
 
**Day 1 Done → Day 2: Build Something Real**
