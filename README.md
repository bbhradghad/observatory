# Observatory

A small pipeline that pulls WHO health indicators for Saudi Arabia and turns them into a report worth reading — charts, a plain-English trend summary, anomaly flags — without an API key and without sending any data off the machine.

## How it works

Three entry points, one pipeline:

1. **`fetch.py`** — pulls a WHO GHO indicator for Saudi Arabia and caches it as a CSV.
2. **`analyze.py`** — computes stats and anomalies in plain python, then asks a local LLM to explain them in plain English.
3. **`report.py`** — runs the whole thing end to end and writes an HTML + Word report with charts.

The LLM never touches the numbers. Trend, year-over-year changes, z-score anomalies — all of it is computed in `src/analysis` with plain python. The model only turns those numbers into readable text: a one-line definition, a short executive summary, a caption per chart. It's given the finished JSON, not the raw data, and it never calculates anything itself. That's on purpose — the numbers in the report should be exactly reproducible without the model in the loop.

Report status (green/amber/red) works the same way: `src/reports/status.py` derives it from the anomaly flags, and the model just reports it.

## Why a local model

It runs on Ollama with `qwen2.5:3b`, tuned for an 8GB RAM machine — small context window, capped output length. No API key, no per-request cost, nothing leaves your machine.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

ollama pull qwen2.5:3b
ollama serve
```

## Usage

```bash
python fetch.py --disease tb        # just fetch and cache the data
python analyze.py --disease tb      # fetch + stats + narrative (JSON + markdown)
python report.py --disease tb       # full report: HTML + Word, with charts
```

Run any of them with no arguments to get an interactive menu of the shortlist in `config/indicators.yaml` (TB, malaria, HIV, hepatitis B, measles, life expectancy at birth). You're not limited to the shortlist, though — any WHO GHO indicator works:

```bash
python fetch.py --search tuberculosis
python fetch.py --indicator MDG_0000000020
python fetch.py --indicator MDG_0000000020 --add-favourite   # save it to the shortlist
```

`report.py` also pulls regional (EMR) and global series when available, so the charts show Saudi Arabia against context rather than in isolation.

## Layout

```
fetch.py, analyze.py, report.py    entry points
src/
  catalogue.py, config.py, country.py,
  data_pipeline.py, gho_client.py      fetching from the WHO API + config loading
  analysis/                            stats + anomaly detection — plain python, no LLM
  agents/                              CrewAI agents that narrate the stats (local Ollama)
  reports/                             charts, HTML and DOCX rendering
config/                              indicators.yaml (disease shortlist), country.yaml
data/raw/                            cached CSVs (gitignored)
output/                              generated reports + chart assets (gitignored)
```
