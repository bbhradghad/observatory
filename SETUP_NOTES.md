# Local Epidemiological Observatory — Setup Notes

## What this is

- **Phase 1** — a pure-Python, no-LLM, no-API-key tool that fetches health
  indicator data from the WHO Global Health Observatory (GHO) OData API
  (https://ghoapi.azureedge.net/api/) and saves it as a clean CSV.
- **Phase 2** — pure-Python analysis (stats + anomaly detection) on top of
  that CSV, plus two local CrewAI agents (running on Ollama) that turn the
  computed numbers into a plain-English narrative. The agents never
  calculate anything themselves; they only interpret numbers Python already
  computed.
- **Phase 3** — turns the analysis + narrative into a polished, non-technical
  report: matplotlib charts, a third "Report Writer" agent that writes an
  executive summary and chart captions, and a self-contained HTML report plus
  a Word document. Section status (green/amber/red) is computed in Python
  from the anomaly flags, never decided by a model.

## Project structure

```
observatory/
├── .venv/                  # virtual environment (not committed)
├── config/
│   └── indicators.yaml     # disease key -> GHO indicator code mapping
├── data/
│   ├── raw/                # fetched CSVs (Phase 1 output, not committed, kept via .gitkeep)
│   └── analysis/           # stats+anomalies JSON and narrative .md (Phase 2 output, not committed, kept via .gitkeep)
├── output/
│   ├── assets/              # chart PNGs (Phase 3 output, not committed, kept via .gitkeep)
│   └── *.html, *.docx       # final reports (Phase 3 output, not committed, kept via .gitkeep)
├── src/
│   ├── config.py           # loads config/indicators.yaml
│   ├── gho_client.py       # thin wrapper around the GHO OData API
│   ├── validate.py         # sanity checks before saving a fetched CSV
│   ├── output.py           # writes the clean CSV to data/raw/
│   ├── analysis/
│   │   ├── data.py         # loads a fetched CSV into a year/value series
│   │   ├── stats.py        # latest value, 5y/10y trend, YoY changes, min/max years
│   │   ├── anomalies.py    # YoY-threshold and baseline z-score flags
│   │   └── report.py       # assembles/saves the JSON + narrative .md
│   ├── agents/
│   │   ├── llm.py          # local Ollama LLM config + readiness check
│   │   └── crew.py         # the three agents, their tasks, and the crew
│   └── reports/
│       ├── charts.py       # matplotlib line + bar charts -> output/assets/*.png
│       ├── status.py       # green/amber/red section status, derived from anomaly flags
│       ├── html.py         # self-contained HTML report (charts embedded as base64)
│       └── docx.py         # same report content as a Word document
├── fetch.py                # Phase 1 CLI entry point
├── analyze.py              # Phase 2 CLI entry point
├── report.py                # Phase 3 CLI entry point (full pipeline -> output/)
├── requirements.txt
├── .gitignore
└── SETUP_NOTES.md
```

## Setup (already done, for reference)

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
git init
```

Dependencies (`requirements.txt`): `requests`, `pandas`, `pyyaml` (Phase 1),
plus `crewai` (Phase 2). No `litellm` or `crewai-tools` needed — this crewai
version talks to Ollama natively over its OpenAI-compatible endpoint, and the
agents don't use tools.

**Phase 2 also needs [Ollama](https://ollama.com) installed and running,
with the model pulled:**

```powershell
ollama pull wizardlm2:7b
ollama serve          # or just open the Ollama desktop app
```

`analyze.py` checks both of these before starting the agents and prints a
clear message telling you what to run if either is missing (see
"Troubleshooting" below) — it does not silently fail or hang.

## How to run

Activate the virtual environment first:

```powershell
.\.venv\Scripts\Activate.ps1
```

**Direct mode** — specify disease and country:

```powershell
python fetch.py --disease tb --country SAU
```

`--country` is optional; omitting it fetches data for all countries/regions
the API has for that indicator.

**Interactive mode** — run with no arguments to get a menu:

```powershell
python fetch.py
```

You'll be prompted to pick a disease by number and type an ISO3 country
code (or leave it blank for all countries).

## Available diseases (config/indicators.yaml)

| key | disease | GHO indicator code |
|---|---|---|
| `tb` | Tuberculosis | `MDG_0000000020` |
| `malaria` | Malaria | `MALARIA_EST_INCIDENCE` |
| `hiv` | HIV | `HIV_0000000001` |
| `hepatitis_b` | Hepatitis B | `HEPATITIS_HBV_PREVALENCE_PER100` |
| `measles` | Measles | `WHS3_62` |

Each code was queried against the live API and confirmed to return real
country-level data before being added. To add a new disease, find its
indicator code by searching the API, e.g.:

```
https://ghoapi.azureedge.net/api/Indicator?$filter=contains(IndicatorName,'Cholera')
```

then add a new entry to `config/indicators.yaml` following the existing
pattern. No code changes are needed — `fetch.py` reads the config at
runtime.

## Output

Each run writes one CSV to `data/raw/`, named `<indicator_code>_<date>.csv`,
e.g. `MDG_0000000020_2026-08-05.csv`. Columns:

| column | meaning |
|---|---|
| `country` | ISO3 country code |
| `year` | year of observation |
| `value` | indicator value |
| `low` / `high` | confidence interval bounds, when the indicator provides them |

Before saving, `src/validate.py` checks that:
- the API returned at least one row,
- the expected columns (`SpatialDim`, `TimeDim`, `NumericValue`) are present,
- years are numeric and fall within a sane range (1950 – current year + 1),
- at least some values are valid numbers.

If validation fails, no file is written and the script exits with an error
message.

## Phase 2 — analysis + narrative

`analyze.py` runs the full pipeline for one disease/country:

```powershell
python analyze.py --disease tb --country SAU
python analyze.py                                # interactive menu
```

Unlike `fetch.py`, `--country` is required here — the analysis assumes one
country's time series. Steps:

1. **Get the data.** Reuses the most recent matching CSV in `data/raw/` if
   one exists for that country; otherwise fetches fresh via the same
   `src/gho_client` used by `fetch.py` and saves it, so `analyze.py` also
   works as a first command with no prior `fetch.py` run.
2. **Compute stats (python only, `src/analysis/stats.py`):** latest
   value/year, trend over the last 5 and 10 years (direction + % change),
   year-over-year changes (capped at the most recent 15 to keep the JSON
   small), and the data's min/max years.
3. **Detect anomalies (python only, `src/analysis/anomalies.py`):** flags a
   year if either (a) its year-over-year change exceeds 20%, or (b) it's
   more than 2 standard deviations from the mean of the previous 5 years.
   Each flag includes a plain-English `reason` string, already written by
   python — the LLM only elaborates on it, never recomputes it.
4. **Save the JSON** to `data/analysis/<indicator_code>_<date>.json` — this
   is the *only* thing the LLM agents read; they never see the raw CSV.
5. **Run the two local agents** (see below) and save their output to
   `data/analysis/<indicator_code>_<date>_narrative.md`.

### Agent configuration (`src/agents/`)

Tuned for an 8GB RAM, CPU-only Windows machine:

| setting | value | why |
|---|---|---|
| model | `ollama/wizardlm2:7b` | small enough to run on CPU with 8GB RAM |
| `num_ctx` | 4096 | keeps the model's memory footprint small |
| `max_tokens` (response) | 800 | bounds generation time; long enough not to truncate a multi-flag anomaly review |
| process | sequential (`Process.sequential`) | one agent runs, then the next — no extra coordination overhead |
| memory | off (`memory=False`) | nothing needs to persist between runs |
| embedder | none | not needed since memory is off |
| tools | none (`tools=[]` on all agents) | agents only read the JSON/context handed to them via task context — they can't fetch, browse, or calculate |

Two agents in Phase 2, one task each, run in this order (a third, the Report
Writer, is added in Phase 3 — see below):

1. **Public Health Data Analyst** — reads the stats JSON, writes a 5-8
   sentence plain-English interpretation of the latest value and trends.
2. **Epidemiological Anomaly Reviewer** — reads the anomaly flags JSON,
   explains each one in plain English and rates it low/medium/high concern.

Both task prompts explicitly forbid inventing or recalculating numbers, and
tell the agent to describe trend direction/size factually rather than
guessing whether a rising or falling value is "good" or "bad" news (the JSON
doesn't say which direction is favorable for a given indicator, so an early
test run had the model wrongly call a *falling* TB incidence rate a "decline
in health" — the prompt now explicitly rules this out).

### Troubleshooting

`analyze.py` checks Ollama before running the agents (the JSON is already
saved by this point, so nothing is lost):

- **Ollama not running:** prints `Could not reach Ollama at
  http://localhost:11434` with the exact command to start it
  (`ollama serve`).
- **Model not pulled:** prints that `wizardlm2:7b` isn't installed, with the
  exact `ollama pull wizardlm2:7b` command to fix it.

## Phase 3 — polished report (HTML + Word)

`report.py` runs the full pipeline for one disease/country — fetch if needed
→ analyze → agents → charts → HTML + DOCX — into `output/`:

```powershell
python report.py --disease tb --country SAU
python report.py                                  # interactive menu
```

Steps, building on Phase 2:

1. Get the data, compute stats/anomalies, save the analysis JSON — identical
   to `analyze.py` (same `src/analysis` modules, same reused-CSV logic).
2. **Generate charts (python only, `src/reports/charts.py`, matplotlib):** a
   line chart of the indicator's value over the recent years with
   anomaly-flagged years marked (red = high severity, amber = medium), and a
   bar chart of year-over-year % change colored by the same severity
   threshold `anomalies.py` uses (`YOY_PCT_THRESHOLD`, imported directly so
   the two never drift apart). Saved as PNGs to `output/assets/`.
3. **Derive section status (python only, `src/reports/status.py`):** green
   if no anomaly flags apply, amber if the worst applicable flag is medium
   severity, red if any is high. The Trend section's status only looks at
   flags within the 5-year trend window; the Year-over-year change and
   Anomaly review sections (and the executive summary) use the full flag
   list. These ratings are computed before any agent runs and handed to the
   Report Writer as a given fact — the model reports them, it never decides
   or reinterprets them.
4. **Run three local agents in sequence** (`src/agents/crew.py`): the two
   from Phase 2, plus a new **Report Writer**, which reads the analyst's
   interpretation and anomaly review (via CrewAI's task `context=[...]`, not
   string interpolation — see below) plus the stats JSON and the two status
   ratings, and writes three marker-delimited sections: `EXECUTIVE SUMMARY`
   (3-4 sentences), `TREND CAPTION`, and `CHANGE CAPTION` (one sentence each,
   captioning the two charts). This is the *only* agent call added beyond
   Phase 2 — still one model, still sequential.
5. **Save the HTML report** (`src/reports/html.py`) — a single self-contained
   file, charts embedded as base64 `data:` URIs, no external CSS/JS or
   server needed. Status badges (green/amber/red pill, e.g. "Needs
   attention") appear next to each section heading and color the executive
   summary card's accent border.
6. **Save the same content as a Word document** (`src/reports/docx.py`) via
   `python-docx` — same sections, status lines, embedded chart images, and
   anomaly table.

Both `output/*.html` and `output/*.docx` are named
`<indicator_code>_<country>_<date>.{html,docx}`.

### Report Writer prompt parsing

`wizardlm2:7b` doesn't reliably emit plain `EXECUTIVE SUMMARY:` markers — in
testing it wrapped them in markdown bold (`**EXECUTIVE SUMMARY:**`) and
sometimes echoed the status ratings back at the end despite being told not
to add extra sections. `_parse_report_sections()` in `src/agents/crew.py`
tolerates leading `*`/`#` around each marker and trims any trailing
`----------` separator or echoed "Section Status" line. If a section still
can't be found, the executive summary falls back to the full raw text and
the captions fall back to a generic sentence, so a formatting slip never
breaks the HTML/DOCX build.

### Inter-agent context

The Report Writer's task description references the analyst's and anomaly
reviewer's output, but **not** via `{placeholder}` interpolation — CrewAI
only fills `{...}` placeholders from the `inputs` dict passed to
`crew.kickoff()`, which is rendered once *before* any task runs, so an
upstream task's output can't be injected that way. Instead the Report Writer
task is given `context=[analyst_task, anomaly_task]`, which CrewAI appends
to the prompt actually sent to the agent at execution time.

### Chart and report styling

Colors follow a validated palette (checked against the `dataviz` skill's
color-formula validator): categorical blue (`#2a78d6`) for the single data
series, and the fixed status palette (green `#0ca30c` / amber `#fab219` /
red `#d03b3b`) for anomaly severity and section status — so a chart's red
dot and a report's red badge are always the same red. The HTML report
supports light and dark mode (`prefers-color-scheme` + a `data-theme`
override) and has `@media print` rules so it prints cleanly; chart images
themselves stay on a white card in both modes since they're static PNGs.

## Verified test runs

```
python fetch.py --disease tb --country SAU        -> MDG_0000000020_2026-08-05.csv (25 rows)
python fetch.py --disease measles --country EGY    -> WHS3_62_2026-08-05.csv (52 rows)
python fetch.py  (interactive: malaria / NGA)      -> MALARIA_EST_INCIDENCE_2026-08-05.csv (25 rows)

python analyze.py --disease tb --country SAU
  -> reused MDG_0000000020_2026-08-05.csv
  -> data/analysis/MDG_0000000020_2026-08-05.json (stats + 6 anomaly flags)
  -> data/analysis/MDG_0000000020_2026-08-05_narrative.md (both agents ran; every
     number in the text cross-checked against the JSON, no invented figures)

python report.py --disease tb --country SAU
  -> reused MDG_0000000020_2026-08-05.csv, saved data/analysis/MDG_0000000020_2026-08-06.json
  -> output/assets/MDG_0000000020_SAU_2026-08-06_{line,bar}.png
  -> all three agents ran (analyst, anomaly reviewer, report writer)
  -> output/MDG_0000000020_SAU_2026-08-06.html and .docx
  -> opened the HTML in a browser: executive summary, trend/change captions,
     and both narratives render as clean plain-English prose with correct
     numbers, colored status badges, and no leaked markdown or JSON
```

Also verified directly: the "Ollama not reachable" and "model not installed"
messages both print correctly instead of crashing with a stack trace.

## Notes

- Git for Windows was not present on this machine and was installed via
  `winget install --id Git.Git` as part of this setup.
- The GHO API needs no key/registration; a plain `requests.get` is enough.
- This crewai version has no `litellm` dependency — it talks to Ollama's
  OpenAI-compatible endpoint (`http://localhost:11434/v1`) directly. Extra
  Ollama options (like `num_ctx`) are passed via `extra_body={"options": {...}}`
  on the `LLM(...)` call.
- On its first-ever run, crewai asks an interactive yes/no question about
  enabling execution tracing (20s timeout, defaults to no). This only
  happens once per machine — the preference is saved after that.
- Local CPU inference is slow: each agent call took roughly 30-90 seconds
  in testing. A full `analyze.py` run (two agents, sequential) takes a few
  minutes — this is expected on 8GB RAM with no GPU, not a bug.
