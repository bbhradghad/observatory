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
- **Scoping pass** — the project now targets Saudi Arabia only (`--country`
  removed from every CLI; see "Country scope" below), and indicator selection
  is open rather than limited to the five-disease shortlist (`--search`,
  `--indicator`, `--add-favourite`; see "Open indicator selection" below).
  Both changes are pure Python — no new LLM calls, no change to memory usage.
- **Chart-first redesign** — the report is now built around three
  self-sufficient charts (trend, year-over-year change, and a new
  region/global comparison chart) that each carry their own meaning: a
  confidence band, anomaly markers, and the final value labelled at the line
  end, WHO-chart style. Surrounding text was cut down to match — a one-line
  definition and scope line per chart, one caption sentence, and a 2-3
  sentence executive summary; the fuller Analyst/Anomaly Reviewer narratives
  moved out of the main body into a collapsed "Detailed notes" section. See
  "Phase 3" below.

## Project structure

```
observatory/
├── .venv/                  # virtual environment (not committed)
├── config/
│   ├── country.yaml         # the one target country: SAU (API code) / KSA (display)
│   ├── indicators.yaml      # curated shortlist: disease key -> GHO indicator code
│   └── indicator_catalogue.json  # full ~3,000-indicator cache (not committed, see --refresh-catalogue)
├── data/
│   ├── raw/                # fetched CSVs (Phase 1 output, not committed, kept via .gitkeep)
│   └── analysis/           # stats+anomalies JSON and narrative .md (Phase 2 output, not committed, kept via .gitkeep)
├── output/
│   ├── assets/              # chart PNGs (Phase 3 output, not committed, kept via .gitkeep)
│   └── *.html, *.docx       # final reports (Phase 3 output, not committed, kept via .gitkeep)
├── src/
│   ├── country.py          # loads config/country.yaml (the one place country is read from)
│   ├── config.py           # loads config/indicators.yaml; resolves open --indicator codes; add_favourite()
│   ├── catalogue.py        # full indicator catalogue: refresh/cache/search/name lookup
│   ├── data_pipeline.py    # cache-or-fetch-or-fallback logic; also fetches/caches the region+global comparison series
│   ├── gho_client.py       # thin wrapper around the GHO OData API (country fetch + region/global spatial-aggregate fetch)
│   ├── validate.py         # dimension selection + sanity checks before saving a fetched CSV
│   ├── output.py           # writes a clean CSV to data/raw/ (main series or, with a suffix, the comparison series)
│   ├── analysis/
│   │   ├── data.py         # loads a fetched CSV into a year/value series; finds the latest main or comparison cache file
│   │   ├── stats.py        # latest value, 5y/10y trend, YoY changes, min/max years
│   │   ├── anomalies.py    # YoY-threshold and baseline z-score flags
│   │   └── report.py       # assembles/saves the JSON + narrative .md
│   ├── agents/
│   │   ├── llm.py          # local Ollama LLM config + readiness check
│   │   └── crew.py         # the three agents, their tasks, and the crew
│   └── reports/
│       ├── charts.py       # matplotlib trend/YoY/comparison charts -> output/assets/*.png (endpoint labels, confidence band)
│       ├── status.py       # green/amber/red section status, derived from anomaly flags
│       ├── html.py         # self-contained HTML report: chart cards + collapsed "Detailed notes"
│       └── docx.py         # same report content as a Word document, with a "Detailed notes" appendix page
├── fetch.py                # Phase 1 CLI entry point (+ --search/--indicator/--refresh-catalogue/--add-favourite)
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
ollama pull qwen2.5:3b
ollama serve          # or just open the Ollama desktop app
```

`analyze.py` checks both of these before starting the agents and prints a
clear message telling you what to run if either is missing (see
"Troubleshooting" below) — it does not silently fail or hang.

## Country scope

Saudi Arabia is the only country this project targets — `--country` has been
removed from `fetch.py`, `analyze.py`, and `report.py`. It's read from exactly
one place, `config/country.yaml`, via `src/country.py`:

```yaml
api_code: SAU        # what every WHO GHO API call must use
display_name: KSA     # what every title, heading, and filename shows
full_name: Kingdom of Saudi Arabia
```

**These two codes must not be conflated — this was verified directly against
the live API, not assumed:**

```
GET .../api/MDG_0000000020?$filter=SpatialDim eq 'KSA'  -> 0 rows
GET .../api/MDG_0000000020?$filter=SpatialDim eq 'SAU'  -> 25 rows
```

`SAU` is the ISO 3166-1 alpha-3 code the WHO GHO API requires and must stay
exactly that — **do not "fix" this by swapping in `KSA`, it will silently
break every fetch.** `KSA` is a display-only label: it shows up in report/chart
titles, HTML/DOCX headings, and output filenames (e.g.
`MDG_0000000020_KSA_2026-08-06.html`), but is never sent to the API. Both
`config/country.yaml` and `src/country.py` carry this warning inline as a
second line of defense.

The lower-level modules (`src/gho_client.py`, `src/analysis/data.py`) still
accept an arbitrary country code as a parameter — only the three CLI entry
points stopped exposing `--country`, so the code path for other countries
still exists internally if this ever needs to expand.

## How to run

Activate the virtual environment first:

```powershell
.\.venv\Scripts\Activate.ps1
```

**Direct mode** — specify a disease from the shortlist:

```powershell
python fetch.py --disease tb
```

**Interactive mode** — run with no arguments to get a menu:

```powershell
python fetch.py
```

You'll be prompted to pick a disease by number from the shortlist. To reach
any indicator outside the shortlist, use `--search`/`--indicator` instead —
see "Open indicator selection" below.

## Shortlist (config/indicators.yaml)

A curated set of verified favourites for quick access — not the full set of
what's available (see "Open indicator selection" below for that):

| key | disease | GHO indicator code |
|---|---|---|
| `tb` | Tuberculosis | `MDG_0000000020` |
| `malaria` | Malaria | `MALARIA_EST_INCIDENCE` |
| `hiv` | HIV | `HIV_0000000001` |
| `hepatitis_b` | Hepatitis B | `HEPATITIS_HBV_PREVALENCE_PER100` |
| `measles` | Measles | `WHS3_62` |

Each code was queried against the live API and confirmed to return real
Saudi Arabia data before being added. Entries can be added by hand, or
appended automatically via `fetch.py --indicator <code> --add-favourite`
(see below) — either way, no code changes are needed; `fetch.py` reads the
file at runtime.

## Open indicator selection

Indicator selection isn't limited to the five-disease shortlist. The full WHO
GHO indicator catalogue (~3,000 entries, from `/api/Indicator`) is fetched
once and cached locally, so search and code lookups work offline after that:

```powershell
python fetch.py --refresh-catalogue          # fetch/refresh the ~3,000-indicator cache (needs network)
python fetch.py --search diabetes            # search the local cache, ranked by relevance
python fetch.py --indicator WHOSIS_000001    # fetch any code directly, shortlist or not
python fetch.py --indicator WHOSIS_000001 --add-favourite   # ...and save it to the shortlist
```

`--search` and `--indicator` never touch the network themselves (beyond the
indicator fetch itself) — only `--refresh-catalogue` does, and only when run
explicitly. `analyze.py` and `report.py` also accept `--indicator <code>` as
an alternative to `--disease <key>`, so the full pipeline works on any
indicator, not just the shortlist.

This is pure Python throughout (`src/catalogue.py`, `src/config.py`) — no LLM
involvement, and no change to the project's memory footprint.

### Validation gate

Since `--indicator` now accepts any code, `src/validate.py` guards against
indicators that don't actually produce a usable Saudi Arabia series:

- **Dimension breakdowns.** Some indicators split rows by a `Dim1` dimension
  (e.g. sex, age group) instead of one row per year. `select_dimension()`
  picks the unambiguous combined total when one exists (currently: `SEX` ->
  `SEX_BTSX`, "both sexes" — confirmed against the live API), otherwise it
  lists the available breakdowns and asks interactively which to use. It
  never silently picks one. In a non-interactive session (no stdin), this
  fails cleanly with a message rather than crashing on `EOFError`.
- **Multi-year requirement.** After any dimension is resolved, `validate()`
  requires at least 2 distinct years of numeric data for Saudi Arabia — a
  trend can't be computed from one point. Indicators that are single-year,
  policy-flag-only, or simply have no Saudi data fail here with a clear
  message naming the indicator, and no file is written.
- **Bad codes vs. an unreachable API** get different messages: a 404 (bad
  code) suggests re-running `--search`; a network failure falls back to a
  cached CSV if one exists, or fails clearly if not (see "Offline behaviour"
  below) — a bad code is never silently treated as "API is down."

## Output

Each run writes one CSV to `data/raw/`, named `<indicator_code>_<date>.csv`,
e.g. `MDG_0000000020_2026-08-05.csv`. Columns:

| column | meaning |
|---|---|
| `country` | ISO3 country code (always `SAU`) |
| `year` | year of observation |
| `value` | indicator value |
| `low` / `high` | confidence interval bounds, when the indicator provides them |

Before saving, `src/validate.py` checks that:
- the API returned at least one row,
- the expected columns (`SpatialDim`, `TimeDim`, `NumericValue`) are present,
- years are numeric and fall within a sane range (1950 – current year + 1),
- at least some values are valid numbers,
- at least 2 distinct years have a valid numeric value (see "Validation
  gate" above).

If validation fails, no file is written and the script exits with an error
message.

`report.py` additionally writes a second, smaller CSV for the comparison
chart: `<indicator_code>_comparison_<date>.csv`, holding whatever rows exist
for the WHO Eastern Mediterranean region (`country=EMR`) and the global
aggregate (`country=GLOBAL`) — see "Region/global comparison" below. This
file is exempt from the validation gate above (it can legitimately be empty)
and `find_latest_csv()` explicitly excludes it via a date-shaped glob, so it
can never be picked up as the main indicator's cache by mistake.

## Offline behaviour

By default, every entry point (`fetch.py`, `analyze.py`, `report.py`) reuses
the most recent cached CSV in `data/raw/` for the indicator — no network call.
Pass `--refresh` to bypass the cache and re-fetch. This logic lives in one
place, `src/data_pipeline.py`, used by all three scripts:

- **Cache exists, no `--refresh`:** used as-is, prints `Using cached data: <file>`.
- **`--refresh`, or no cache exists:** fetches fresh from the API.
- **API unreachable and a cache exists:** falls back to the cache with a
  clear notice naming the cached file and its date, instead of failing.
- **API unreachable and no cache exists:** fails with a clear message; no
  file is written.

## Region/global comparison

`report.py` fetches two more series for the same indicator, used only by the
comparison chart (`src/reports/charts.py`, "Phase 3" below):

- WHO Eastern Mediterranean region — `SpatialDimType eq 'REGION' and
  SpatialDim eq 'EMR'` (the region Saudi Arabia belongs to)
- Global aggregate — `SpatialDimType eq 'GLOBAL' and SpatialDim eq 'GLOBAL'`

Both live in `src/gho_client.fetch_spatial_aggregate()` and are orchestrated
by `src/data_pipeline.get_comparison_csv()`, cached to
`<indicator_code>_comparison_<date>.csv` (reused on later runs exactly like
the main CSV — see "Offline behaviour" above).

This path is deliberately **never fatal**, unlike the main country fetch:

- A network failure on either geography, an empty response, or a `Dim1`
  breakdown with no unambiguous combined total (`_reduce_to_total()`, a
  non-interactive counterpart to `validate.select_dimension()` — there's no
  user to prompt here) just drops that geography from the CSV instead of
  raising. Many indicators genuinely have no region/global rows at all
  (verified directly: `NTD_LEISHCNUM`, cutaneous leishmaniasis case counts,
  returns 0 rows for both).
- Even a fully empty result is still cached, so a repeat run doesn't re-hit
  the API just to learn the same thing again.
- `charts.py`'s comparison chart draws with whatever series survive — one
  line (Saudi Arabia only) if both are missing, up to three if both exist —
  and `html.py`/`docx.py` note whichever is missing directly in that chart's
  scope line rather than silently showing an incomplete chart.

## Phase 2 — analysis + narrative

`analyze.py` runs the full pipeline for one indicator (Saudi Arabia is
implicit — see "Country scope" above):

```powershell
python analyze.py --disease tb
python analyze.py --indicator WHOSIS_000001       # any open indicator code
python analyze.py                                 # interactive shortlist menu
python analyze.py --disease tb --refresh            # bypass the local cache
```

Steps:

1. **Get the data.** Reuses the most recent cached CSV in `data/raw/` for
   this indicator unless `--refresh` is passed or none exists (see "Offline
   behaviour" above); otherwise fetches fresh via `src/data_pipeline.py` and
   saves it, so `analyze.py` also works as a first command with no prior
   `fetch.py` run.
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
| model | `ollama/qwen2.5:3b` | small enough to run on CPU with 8GB RAM |
| `num_ctx` | 4096 | keeps the model's memory footprint small |
| `max_tokens` (Analyst/Anomaly Reviewer) | 800 | bounds generation time; long enough not to truncate a multi-flag anomaly review - their output length is unchanged by the Phase 3 chart-first redesign |
| `max_tokens` (Report Writer) | 350 | tightened separately (`build_llm(max_tokens=...)`) once its output shrank to five short, fixed-length sections instead of paragraphs - see "Phase 3" below |
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
- **Model not pulled:** prints that `qwen2.5:3b` isn't installed, with the
  exact `ollama pull qwen2.5:3b` command to fix it.

## Phase 3 — polished report (HTML + Word)

`report.py` runs the full pipeline for one indicator (Saudi Arabia is
implicit) — fetch if needed → analyze → agents → charts → HTML + DOCX — into
`output/`:

```powershell
python report.py --disease tb
python report.py --indicator WHOSIS_000001        # any open indicator code
python report.py                                  # interactive shortlist menu
python report.py --disease tb --refresh             # bypass the local cache
```

The report is **chart-first**: the charts carry the meaning, and the text
around them is short, supporting copy, not prose. Steps, building on Phase 2:

1. Get the country data, compute stats/anomalies, save the analysis JSON —
   identical to `analyze.py` (same `src/analysis` modules, same reused-CSV
   logic). Also fetch/cache the region+global comparison series (see
   "Region/global comparison" above).
2. **Generate three charts (python only, `src/reports/charts.py`,
   matplotlib):**
   - **Trend** — the indicator's value over the recent years, with
     anomaly-flagged years marked (red = high severity, amber = medium), a
     shaded confidence band behind the line when the API supplied Low/High
     bounds for that year (skipped silently otherwise), and the final point
     labelled with its value next to the line end, WHO-chart style.
   - **Year-over-year change** — a bar chart of % change, colored by the
     same severity threshold `anomalies.py` uses (`YOY_PCT_THRESHOLD`,
     imported directly so the two never drift apart). Unchanged from before.
   - **Comparison** — Saudi Arabia plotted against the WHO Eastern
     Mediterranean region and the global aggregate (clipped to the trend
     chart's own year range), each line end-labelled with its value and a
     legend naming the three series. Draws with whatever series exist -
     never fails if region/global data is missing for an indicator.

   All charts saved as PNGs to `output/assets/`. Colors follow the
   validated categorical palette (see "Chart and report styling" below).
3. **Derive section status (python only, `src/reports/status.py`):** green
   if no anomaly flags apply, amber if the worst applicable flag is medium
   severity, red if any is high. The Trend section's status only looks at
   flags within the 5-year trend window; the Year-over-year change section
   (and the executive summary) use the full flag list. These ratings are
   computed before any agent runs and handed to the Report Writer as a given
   fact — the model reports them, it never decides or reinterprets them.
4. **Run three local agents in sequence** (`src/agents/crew.py`): the two
   from Phase 2 (Analyst, Anomaly Reviewer — unchanged, still 5-8 sentences
   / one explanation per flag), plus a **Report Writer** with its own
   tighter `max_tokens` (see the agent config table above), which reads the
   analyst's interpretation and anomaly review (via CrewAI's task
   `context=[...]`, not string interpolation — see below) plus the stats
   JSON, the two status ratings, the indicator name, and whether
   region/global comparison data exists, and writes five marker-delimited
   sections: `DEFINITION` (one sentence, plain-language, paraphrasing only
   the indicator's own name — no invented facts), `EXECUTIVE SUMMARY` (2-3
   sentences max), `TREND CAPTION`, `CHANGE CAPTION`, and `COMPARISON
   CAPTION` (one sentence each, captioning the three charts - the
   comparison caption is told explicitly whether region/global data exists,
   so it never claims a comparison that isn't there). This is the *only*
   agent call added beyond Phase 2 — still one model, still sequential.
5. **Save the HTML report** (`src/reports/html.py`) — a single self-contained
   file, charts embedded as base64 `data:` URIs, no external CSS/JS or
   server needed. Each chart sits in its own card, in a fixed order: the
   indicator's official name, the one-line definition, a scope line
   ("Saudi Arabia (KSA), \<first year\> - \<last year\>", with a note appended
   for the comparison chart if region or global data is missing), the chart,
   and the one caption sentence - nothing else in the card. Anomalies appear
   as a compact three-column table (Year, Change, Severity) rather than
   prose. The Analyst/Anomaly Reviewer's fuller text lives in a collapsed
   `<details>` "Detailed notes" section at the end, out of the main reading
   path. The executive summary keeps its status badge and stat tiles above
   the chart cards.
6. **Save the same content as a Word document** (`src/reports/docx.py`) via
   `python-docx` — same chart cards, same compact anomaly table. The
   Analyst/Anomaly Reviewer text moves to a final "Detailed notes" appendix
   page (`doc.add_page_break()`) instead of the main body.

Both `output/*.html` and `output/*.docx` are named
`<indicator_code>_KSA_<date>.{html,docx}` — the display name, not `SAU` (see
"Country scope" above; `report['country_display']` is what charts.py,
html.py, and docx.py all read for titles/headings/filenames).

### Report Writer prompt parsing

`qwen2.5:3b` doesn't reliably emit plain marker lines (now `DEFINITION:`,
`EXECUTIVE SUMMARY:`, `TREND CAPTION:`, `CHANGE CAPTION:`, `COMPARISON
CAPTION:`) — in testing it wrapped them in markdown bold (`**EXECUTIVE
SUMMARY:**`) and sometimes echoed the status ratings back at the end despite
being told not to add extra sections. `_parse_report_sections()` in
`src/agents/crew.py` tolerates leading `*`/`#` around each marker and trims
any trailing `----------` separator or echoed "Section Status" line. If a
section still can't be found, the executive summary falls back to the full
raw text, the definition falls back to the indicator's own name, and the
captions fall back to a generic sentence, so a formatting slip never breaks
the HTML/DOCX build.

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
color-formula validator): categorical blue (`#2a78d6`, slot 1) for Saudi
Arabia's own line on every chart, extended with slot 2 (orange, `#eb6834`)
for the WHO region and slot 3 (aqua, `#1baf7a`) for the global aggregate on
the comparison chart specifically - these three slots are the ones that
clear the palette's all-pairs CVD/contrast gates together. The fixed status
palette (green `#0ca30c` / amber `#fab219` / red `#d03b3b`) is used for
anomaly severity and section status — so a chart's red dot and a report's
red badge are always the same red, and never collide with a categorical
series color. Per the palette's mark rules, end-point value labels stay in
neutral ink text rather than the series color - identity comes from the
colored end-dot beside the label, not from coloring the text itself. The
HTML report supports light and dark mode (`prefers-color-scheme` + a
`data-theme` override) and has `@media print` rules so it prints cleanly;
chart images themselves stay on a white card in both modes since they're
static PNGs.

## Verified test runs

Phase 1-3 (original CLI, before the scoping pass — same underlying fetch/
analyze/report logic, `--country` has since been removed):

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
  -> full pipeline, all three agents ran, HTML + DOCX opened in a browser and
     confirmed presentable (executive summary, captions, status badges,
     no leaked markdown or JSON)
```

Also verified directly: the "Ollama not reachable" and "model not installed"
messages both print correctly instead of crashing with a stack trace.

### Country scope + open indicator selection

```
Verified live against the WHO API directly (see "Country scope"):
  SpatialDim eq 'KSA' -> 0 rows
  SpatialDim eq 'SAU' -> 25 rows

python fetch.py --refresh-catalogue
  -> cached 3082 indicators to config/indicator_catalogue.json

python fetch.py --search diabetes
  -> 16 ranked matches (NCD_DIABETES_TREATMENT_CRUDE, NCD_DIABETES_PREVALENCE_CRUDE, ...)

python fetch.py --indicator WHOSIS_000001   (never in the shortlist; has a SEX dimension)
  -> "'WHOSIS_000001' is broken down by sex; using the combined total (SEX_BTSX)."
  -> saved 22 rows
  -> re-ran with no flags: "Using cached data: ..." (no network call)
  -> re-ran with --refresh: re-fetched and re-validated from the API

python fetch.py --indicator WHOSIS_000001 --add-favourite
  -> appended 'life_expectancy_at_birth_years' to config/indicators.yaml,
     file's header comment and existing entries left untouched

python report.py --indicator WHOSIS_000001
  -> full pipeline on a never-preconfigured indicator, all three agents ran
  -> output/WHOSIS_000001_KSA_2026-08-06.html and .docx (KSA, not SAU)
  -> opened in a browser: page title, <h1>, and both chart titles all read
     "... in KSA"; data was fetched using SAU internally throughout

python fetch.py --indicator EMFLIMITPOWERDENSITY   (real code, no usable SAU data)
  -> prompted for a dimension breakdown (EMFEXPOSED, no unambiguous total) -
     answering it, validation still correctly failed: "NumericValue column
     has no valid numeric data." No file written.
  -> re-ran with stdin closed (non-interactive): failed cleanly on the
     breakdown prompt instead of raising EOFError, no file written

python fetch.py --indicator NOT_A_REAL_INDICATOR_CODE
  -> "Error: 'NOT_A_REAL_INDICATOR_CODE' is not a valid WHO GHO indicator
     code (404 ...). Try: python fetch.py --search <keyword>"

Simulated API-unreachable-with-cache (mocked fetch_indicator to raise
ConnectionError): fell back to the cached CSV with a clear notice naming the
file and its date, instead of failing. Simulated unreachable-with-no-cache:
failed cleanly with sys.exit(1), no traceback.

Real-world bonus: the live WHO API happened to go down mid-testing (every
request timed out, including previously-cached indicators and a bare
`requests.get` with no wrapper code). Confirmed this wasn't a bug on our
end - the cached-CSV path kept working throughout, and the same
NOT_A_REAL_INDICATOR_CODE test had already produced the clean 404 message
above before the outage started.
```

Bug found and fixed during this pass: `run_narrative()` (Phase 3) had
changed to always require `trend_status`/`anomaly_status` and always run the
Report Writer agent, but `analyze.py` (Phase 2) still called it with the old
2-argument form - this would have crashed on the very next `analyze.py` run.
Fixed by making the two arguments optional: omitting them runs only the
original two-agent Phase 2 narrative, so the Report Writer stays an opt-in
extra call rather than a fixed cost.

### Chart-first redesign

Tested on two indicators chosen specifically to exercise both branches of
the region/global comparison path - verified directly against the live API
first (`SpatialDimType eq 'REGION'/'GLOBAL'`) before picking them:

```
python report.py --disease tb --refresh
  -> MDG_0000000020: region 25 rows (EMR), global 25 rows, both with Low/High bounds
  -> comparison CSV: 50 rows cached to MDG_0000000020_comparison_2026-08-06.csv
  -> HTML opened in a browser: trend chart shows a shaded confidence band and
     "8.4" labelled at the line end; comparison chart shows all three lines
     (KSA/Eastern Mediterranean Region/Global), each end-labelled, with a
     legend; every chart card reads on its own without the surrounding text

python report.py --indicator NTD_LEISHCNUM --refresh
  -> cutaneous leishmaniasis case counts: confirmed live no Low/High, no
     region, no global data for this indicator
  -> comparison CSV: 0 rows, still cached (re-running without --refresh
     reused it, no network call)
  -> HTML opened in a browser: comparison chart drew with only the KSA line
     (no legend, single series), scope line read "SAUDI ARABIA (KSA), 2010 -
     2024 (REGIONAL AND GLOBAL COMPARISON DATA NOT AVAILABLE FOR THIS
     INDICATOR)", comparison caption correctly said only Saudi Arabia's data
     was shown - the report never failed or showed a misleading comparison

python report.py --disease tb   (no --refresh, immediately after the run above)
  -> "Using cached data" and "Using cached comparison data" for both files,
     no network calls, confirming offline re-runs work end to end
```

Also confirmed: `find_latest_csv('MDG_0000000020')` returns the main CSV, not
the same-day `_comparison_` file - the date-shaped-glob fix in
`src/analysis/data.py` was added after noticing the two filenames share a
prefix and would otherwise collide once comparison caching existed.

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
