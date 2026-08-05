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

## Project structure

```
observatory/
├── .venv/                  # virtual environment (not committed)
├── config/
│   └── indicators.yaml     # disease key -> GHO indicator code mapping
├── data/
│   ├── raw/                # fetched CSVs (Phase 1 output, not committed, kept via .gitkeep)
│   └── analysis/           # stats+anomalies JSON and narrative .md (Phase 2 output, not committed, kept via .gitkeep)
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
│   └── agents/
│       ├── llm.py          # local Ollama LLM config + readiness check
│       └── crew.py         # the two agents, their tasks, and the crew
├── fetch.py                # Phase 1 CLI entry point
├── analyze.py              # Phase 2 CLI entry point
├── requirements.txt
├── .gitignore
└── SETUP_NOTES.md
```

This layout leaves room for what comes next without building it now:
**Phase 3** (HTML/Word reports) will likely add `src/reports/` and an
`output/` directory, consuming `data/raw/` and `data/analysis/`.

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
| process | sequential (`Process.sequential`) | one agent runs, then the other — no extra coordination overhead |
| memory | off (`memory=False`) | nothing needs to persist between runs |
| embedder | none | not needed since memory is off |
| tools | none (`tools=[]` on both agents) | agents only read the JSON handed to them via task context — they can't fetch, browse, or calculate |

Two agents, one task each, run in this order:

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
