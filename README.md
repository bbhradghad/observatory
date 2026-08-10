# Observatory

Observatory turns WHO Global Health Observatory data into a report worth reading. Point it at a health indicator for Saudi Arabia and it fetches the numbers, works out the trend and flags anything unusual, then writes a short, plain-English HTML and Word report with charts — all without an API key, and without any of your data leaving the machine.

The project is built around one rule: **the model never touches the numbers.** Every statistic, trend, anomaly flag, and status color in the report is computed in plain Python. A small local LLM (via Ollama) only turns those already-computed numbers into readable sentences — a one-line definition, a short summary, a caption per chart. It never calculates, estimates, or decides anything itself, which means the numbers in a report are exactly reproducible without the model in the loop at all.

## Project Overview

A run through Observatory looks like this:

1. Pick a health indicator — either a shortcut like `tb` or `malaria` from the curated shortlist, or any of the ~3,000 indicators in the WHO GHO catalogue by code or keyword search.
2. **`fetch.py`** pulls that indicator for Saudi Arabia from the WHO GHO API and caches it as a CSV.
3. **`analyze.py`** computes stats and anomalies in plain Python, then asks the local model to explain them in plain English.
4. **`report.py`** runs the full pipeline end to end — fetch, analyze, chart, narrate — and writes a polished HTML + Word report.

Every stage reuses the cached CSV by default, so re-running a report doesn't re-hit the API unless you pass `--refresh`.

## Deterministic Core

All the numbers come from `src/analysis`, with no LLM involved:

| Stage | What it computes |
|---|---|
| **Stats** (`stats.py`) | Latest value, 5-year and 10-year trend (direction + % change), year-over-year changes |
| **Anomaly detection** (`anomalies.py`) | Two independent checks: year-over-year change beyond 20%, and deviation of more than 2 standard deviations from a rolling 5-year baseline |
| **Status** (`status.py`) | Green / amber / red per report section, derived directly from anomaly severity — never assigned by the model |

Anomaly flags are ranked by severity (`medium` / `high`) and already carry a plain-English reason string, so the LLM's later job is to elaborate on a decision that's already been made, not to make one.

## Multi-Agent Narrative Layer

The narrative side is a three-agent [CrewAI](https://www.crewai.com/) pipeline (`src/agents/crew.py`), run sequentially on a local Ollama model. None of the agents have tools or see raw data — each only reads the JSON it's handed and writes prose.

**1. Public Health Data Analyst**
Explains the trend in 5–8 plain-English sentences: the latest value, direction and size of change over 5 and 10 years, without editorializing on whether it's good or bad news.

**2. Epidemiological Anomaly Reviewer**
Walks through each anomaly flag, explains in one or two sentences why it was raised, and rates its concern level as low, medium, or high.

**3. Report Writer**
Only runs for the full report (`report.py`, not `analyze.py`). Takes the other two agents' output as context and writes five fixed-length sections for the report itself: a one-line indicator definition, a 2–3 sentence executive summary, and one caption per chart — chart-first copy, not paragraphs.

All three agents are instructed, in writing, to use only the numbers they're given, never recalculate anything, and never assign their own status rating.

### Crew Configuration

- `Process.sequential`, `memory=False`, `allow_delegation=False`
- `temperature=0.2`
- The Report Writer gets its own tighter `max_tokens` cap (350) since its output is five short fixed-length sections, not free-form prose

## Charts

Charts are rendered with matplotlib (`src/reports/charts.py`) and designed to be self-sufficient — readable without the surrounding text:

- **Trend line** — the indicator over the recent years, with anomaly-flagged points marked and a shaded confidence band when the API provides Low/High bounds. The final point is always labelled with its value, WHO-chart style.
- **Year-over-year bar chart** — % change per year, colored red where it crosses the anomaly threshold.
- **Comparison chart** — Saudi Arabia against the WHO Eastern Mediterranean region and the global aggregate, when that data exists. It draws with whatever series are actually available and never fails just because a region/global series is missing.

## Local AI Model

Observatory runs entirely on a local model through [Ollama](https://ollama.com/):

```
MODEL=ollama/qwen2.5:3b
BASE_URL=http://localhost:11434
```

`qwen2.5:3b` was chosen deliberately for machines without a GPU — a short 4096-token context window and a capped response length keep it usable on an 8GB RAM CPU-only setup. No API key, no per-request cost, nothing leaves your machine.

## Entry Points

| Command | What it does |
|---|---|
| `python fetch.py` | Fetch and cache one indicator's data — no analysis, no model |
| `python analyze.py` | Fetch + stats + anomalies + two-agent narrative → JSON + Markdown |
| `python report.py` | The full pipeline → HTML + Word report with charts |

Run any of them with no arguments for an interactive menu of the shortlist (TB, malaria, HIV, hepatitis B, measles, life expectancy at birth). You're not limited to the shortlist — any WHO GHO indicator works by code or keyword search:

```bash
python fetch.py --search tuberculosis
python fetch.py --indicator MDG_0000000020
python fetch.py --indicator MDG_0000000020 --add-favourite   # save it to the shortlist
```

Indicators broken down by a dimension like sex or age group (`src/validate.py`) are narrowed automatically to the combined total when there's an unambiguous one, or you're asked which breakdown to use interactively.

## System Architecture

```
                         ┌─────────────────────┐
                         │      WHO GHO API     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌────────────────────────────────┐
                    │ fetch.py                        │
                    │ • validate, select dimension    │
                    │ • cache as CSV (data/raw/)      │
                    └──────────┬──────────────────────┘
                                │
                                ▼
                    ┌────────────────────────────────┐
                    │ Deterministic Python Core        │
                    │ (src/analysis)                   │
                    │                                  │
                    │ • trend & year-over-year stats   │
                    │ • anomaly detection               │
                    │ • green/amber/red status          │
                    └──────────┬───────────┬───────────┘
                                │           │
                                │           ▼
                                │   ┌────────────────────┐
                                │   │ data/analysis/      │
                                │   │ JSON + narrative.md │
                                │   └────────────────────┘
                                │
                                ▼
                    ┌────────────────────────────────┐
                    │ CrewAI Sequential Narrative      │
                    │ (local Ollama, qwen2.5:3b)       │
                    │                                  │
                    │ 1. Public Health Data Analyst    │
                    │ 2. Anomaly Reviewer               │
                    │ 3. Report Writer                  │
                    └──────────┬───────────────────────┘
                                │
                                ▼
                    ┌────────────────────────────────┐
                    │ Charts + HTML/DOCX Report        │
                    │ (output/)                        │
                    └────────────────────────────────┘
```

## Local Data Storage

Nothing here needs a database — everything is a plain file, all gitignored so a fresh clone starts empty:

| Location | Contents |
|---|---|
| `data/raw/` | Cached indicator CSVs, one per indicator (+ a separate one for the region/global comparison series) |
| `data/analysis/` | Compact stats+anomalies JSON, and the analyst/anomaly-reviewer narrative as Markdown |
| `output/` | Final HTML and Word reports |
| `output/assets/` | Generated chart PNGs |

## Technologies

- Python
- CrewAI
- Ollama + Qwen2.5 3B Instruct
- pandas
- matplotlib
- python-docx
- WHO GHO OData API

## Project Structure

```
observatory/
├── fetch.py                  entry point: fetch + cache one indicator
├── analyze.py                entry point: fetch + stats + two-agent narrative
├── report.py                 entry point: full pipeline → HTML + Word report
├── requirements.txt
│
├── config/
│   ├── indicators.yaml       curated disease shortlist
│   └── country.yaml          country scope (fixed to Saudi Arabia)
│
├── src/
│   ├── catalogue.py          search/refresh the full WHO indicator catalogue
│   ├── config.py             shortlist loading, favourites
│   ├── country.py            country config loading
│   ├── data_pipeline.py      cache-aware fetch orchestration
│   ├── gho_client.py         WHO GHO API client
│   ├── validate.py           data sanity checks, dimension selection
│   ├── output.py             CSV writing
│   │
│   ├── analysis/             stats + anomaly detection — plain Python, no LLM
│   │   ├── data.py
│   │   ├── stats.py
│   │   ├── anomalies.py
│   │   └── report.py
│   │
│   ├── agents/                CrewAI agents that narrate the stats (local Ollama)
│   │   ├── llm.py
│   │   └── crew.py
│   │
│   └── reports/                charts, status, HTML and DOCX rendering
│       ├── status.py
│       ├── charts.py
│       ├── html.py
│       └── docx.py
│
├── data/
│   ├── raw/                    cached CSVs (gitignored)
│   └── analysis/                stats JSON + narrative markdown (gitignored)
│
└── output/                     generated reports + chart assets (gitignored)
    └── assets/
```

## Installation

**1. Install Ollama and pull the model**

```bash
ollama pull qwen2.5:3b
ollama serve
```

**2. Set up the Python environment**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
python fetch.py --disease tb        # just fetch and cache the data
python analyze.py --disease tb      # fetch + stats + narrative (JSON + markdown)
python report.py --disease tb       # full report: HTML + Word, with charts
```

## Notes on Country Scope

Country is fixed to Saudi Arabia. The WHO API requires the ISO code `SAU` — `KSA` silently returns zero rows, so `config/country.yaml` keeps `api_code: SAU` even though `display_name` is `KSA` for everything user-facing (titles, headings, filenames). This was verified directly against the live API and is deliberate, not a bug to "fix" later.

## Current Limitations

- Indicator coverage depends entirely on what the WHO GHO API reports for Saudi Arabia — some indicators have too few years of data to produce a trend, and are rejected with a clear error rather than a broken report.
- Anomaly detection is threshold-based (year-over-year % and rolling z-score), not a learned or semantic model.
- The narrative layer requires a local Ollama instance with `qwen2.5:3b` installed and running; without it, `report.py` still saves the JSON and charts but stops before the text.
- No automated test suite yet.

## Author

Raghad Saleh (`@bbhraghad`)
