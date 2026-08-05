#!/usr/bin/env python
"""Analyze a WHO GHO health indicator: compute stats/anomalies in python,
then generate a plain-English narrative using local CrewAI agents (Ollama).

Numbers are computed ONLY in python (src/analysis). The LLM agents only
interpret the resulting JSON - they never see raw data and never calculate
anything themselves.

Examples:
    python analyze.py --disease tb --country SAU
    python analyze.py                                # interactive menu
"""

import argparse
import sys

from src.agents.crew import run_narrative
from src.agents.llm import check_ollama_ready
from src.analysis.anomalies import detect_anomalies
from src.analysis.data import find_latest_csv, load_series
from src.analysis.report import build_report, save_narrative, save_report
from src.analysis.stats import compute_stats
from src.config import get_disease, load_diseases
from src.gho_client import fetch_indicator
from src.output import save_csv
from src.validate import ValidationError, validate


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze a WHO GHO health indicator and generate a narrative."
    )
    parser.add_argument("--disease", help="Disease key from config/indicators.yaml (e.g. tb)")
    parser.add_argument("--country", help="ISO3 country code (e.g. SAU)")
    return parser.parse_args()


def interactive_select():
    diseases = load_diseases()
    keys = sorted(diseases)

    print("Available diseases:")
    for i, key in enumerate(keys, start=1):
        print(f"  {i}. {key} - {diseases[key]['name']}")

    choice = input(f"Select a disease [1-{len(keys)}]: ").strip()
    try:
        disease_key = keys[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        sys.exit(1)

    country = input("Country ISO3 code (e.g. SAU, USA, EGY): ").strip()
    if not country:
        print("A country is required for analysis.")
        sys.exit(1)
    return disease_key, country


def get_series(disease: dict, country: str):
    """Return a (year, value) DataFrame for one country, reusing an existing
    fetched CSV in data/raw/ if one covers it, otherwise fetching fresh."""
    indicator_code = disease["indicator_code"]

    csv_path = find_latest_csv(indicator_code)
    if csv_path:
        df = load_series(csv_path, country)
        if not df.empty:
            print(f"Using existing data: {csv_path.name}")
            return df
        print(f"No rows for {country} in {csv_path.name}; fetching fresh data...")

    print(f"Fetching '{disease['name']}' ({indicator_code}) for {country}...")
    raw_df = fetch_indicator(indicator_code, country)
    try:
        validate(raw_df)
    except ValidationError as e:
        print(f"Validation failed: {e}")
        sys.exit(1)
    save_csv(raw_df, indicator_code)

    return load_series(find_latest_csv(indicator_code), country)


def main():
    args = parse_args()

    if args.disease:
        if not args.country:
            print("Error: --country is required when --disease is given.")
            sys.exit(1)
        disease_key, country = args.disease, args.country
    else:
        disease_key, country = interactive_select()

    try:
        disease = get_disease(disease_key)
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)

    df = get_series(disease, country)
    if df.empty:
        print(f"No usable data for {disease['name']} in {country}.")
        sys.exit(1)

    stats = compute_stats(df)
    anomalies = detect_anomalies(df)

    report = build_report(disease_key, disease, country, stats, anomalies)
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
