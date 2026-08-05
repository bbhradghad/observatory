# Local Epidemiological Observatory — Setup Notes

## What this is (Phase 1)

A pure-Python, no-LLM, no-API-key tool that fetches health indicator data
from the WHO Global Health Observatory (GHO) OData API
(https://ghoapi.azureedge.net/api/) and saves it as a clean CSV.

## Project structure

```
observatory/
├── .venv/                  # virtual environment (not committed)
├── config/
│   └── indicators.yaml     # disease key -> GHO indicator code mapping
├── data/
│   └── raw/                # fetched CSVs land here (not committed, dir is kept via .gitkeep)
├── src/
│   ├── config.py           # loads config/indicators.yaml
│   ├── gho_client.py       # thin wrapper around the GHO OData API
│   ├── validate.py         # sanity checks before saving
│   └── output.py           # writes the clean CSV to data/raw/
├── fetch.py                # CLI entry point
├── requirements.txt
├── .gitignore
└── SETUP_NOTES.md
```

This layout leaves room for what comes next without building it now:
- **Phase 2** (CrewAI agents + local Ollama) will likely add `src/agents/`
  and read from `data/raw/` as its data source — no changes needed to
  Phase 1 code.
- **Phase 3** (HTML/Word reports) will likely add `src/reports/` and an
  `output/` directory, consuming the same CSVs.

## Setup (already done, for reference)

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
git init
```

Dependencies (`requirements.txt`): `requests`, `pandas`, `pyyaml` — nothing else.

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

## Verified test runs

```
python fetch.py --disease tb --country SAU        -> MDG_0000000020_2026-08-05.csv (25 rows)
python fetch.py --disease measles --country EGY    -> WHS3_62_2026-08-05.csv (52 rows)
python fetch.py  (interactive: malaria / NGA)      -> MALARIA_EST_INCIDENCE_2026-08-05.csv (25 rows)
```

## Notes

- Git for Windows was not present on this machine and was installed via
  `winget install --id Git.Git` as part of this setup.
- The GHO API needs no key/registration; a plain `requests.get` is enough.
