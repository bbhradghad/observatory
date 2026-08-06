#!/usr/bin/env python
"""Analyze a WHO GHO health indicator for Saudi Arabia: compute stats/anomalies
in python, then generate a plain-English narrative using local CrewAI agents
(Ollama).

Numbers are computed ONLY in python (src/analysis). The LLM agents only
interpret the resulting JSON - they never see raw data and never calculate
anything themselves. Country is fixed to Saudi Arabia (see
config/country.yaml); indicators can be a shortlist key or any open WHO GHO
code.

Examples:
    python analyze.py --disease tb
    python analyze.py --indicator MDG_0000000020
    python analyze.py                                # interactive shortlist menu
    python analyze.py --disease tb --refresh           # bypass the local cache
"""

import argparse
import sys

from src.agents.crew import run_narrative
from src.agents.llm import check_ollama_ready
from src.analysis.anomalies import detect_anomalies
from src.analysis.data import load_series
from src.analysis.report import build_report, save_narrative, save_report
from src.analysis.stats import compute_stats
from src.config import get_disease, load_diseases, resolve_indicator
from src.country import load_country
from src.data_pipeline import get_indicator_csv


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze a WHO GHO health indicator for Saudi Arabia and generate a narrative."
    )
    parser.add_argument("--disease", help="Disease key from config/indicators.yaml (shortlist shortcut)")
    parser.add_argument("--indicator", help="Any WHO GHO indicator code (open catalogue)")
    parser.add_argument("--refresh", action="store_true", help="Bypass the cached CSV and re-fetch from the API")
    return parser.parse_args()


def interactive_select():
    diseases = load_diseases()
    keys = sorted(diseases)

    print("Shortlist (config/indicators.yaml):")
    for i, key in enumerate(keys, start=1):
        print(f"  {i}. {key} - {diseases[key]['name']}")

    choice = input(f"Select a disease [1-{len(keys)}]: ").strip()
    try:
        return keys[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        sys.exit(1)


def get_series(disease: dict, refresh: bool = False):
    """Return a (year, value) DataFrame for Saudi Arabia, reusing a cached
    CSV in data/raw/ unless refresh is True or none exists."""
    country = load_country()
    csv_path = get_indicator_csv(disease["indicator_code"], country["api_code"], refresh=refresh)
    return load_series(csv_path, country["api_code"])


def main():
    args = parse_args()

    if args.disease:
        try:
            disease = get_disease(args.disease)
        except KeyError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.indicator:
        disease = resolve_indicator(args.indicator)
    else:
        disease = get_disease(interactive_select())

    df = get_series(disease, refresh=args.refresh)
    if df.empty:
        print(f"No usable data for {disease['name']}.")
        sys.exit(1)

    stats = compute_stats(df)
    anomalies = detect_anomalies(df)

    country = load_country()
    report = build_report(disease.get("indicator_code"), disease, country, stats, anomalies)
    json_path = save_report(report)
    print(f"Saved analysis JSON to {json_path}")

    ready_error = check_ollama_ready()
    if ready_error:
        print("\nNarrative generation skipped - Ollama is not ready:")
        print(ready_error)
        sys.exit(1)

    print("Running local agents (this can take a few minutes on CPU)...")
    narrative = run_narrative(stats, anomalies)
    md_path = save_narrative(report, narrative["analyst"], narrative["anomaly_reviewer"])
    print(f"Saved narrative to {md_path}")


if __name__ == "__main__":
    main()
