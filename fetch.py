#!/usr/bin/env python
"""Fetch a WHO GHO health indicator and save it as a CSV in data/raw/.

Examples:
    python fetch.py --disease tb --country SAU
    python fetch.py --disease malaria              # all countries
    python fetch.py                                 # interactive menu
"""

import argparse
import sys

from src.config import get_disease, load_diseases
from src.gho_client import fetch_indicator
from src.output import save_csv
from src.validate import ValidationError, validate


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch a WHO GHO health indicator.")
    parser.add_argument(
        "--disease", help="Disease key from config/indicators.yaml (e.g. tb, malaria)"
    )
    parser.add_argument(
        "--country", help="ISO3 country code (e.g. SAU). Omit for all countries."
    )
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

    country = input(
        "Country ISO3 code (e.g. SAU, USA, EGY) or leave blank for all countries: "
    ).strip()
    return disease_key, (country or None)


def main():
    args = parse_args()

    if args.disease:
        disease_key, country = args.disease, args.country
    else:
        disease_key, country = interactive_select()

    try:
        disease = get_disease(disease_key)
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)

    indicator_code = disease["indicator_code"]
    scope = f"for {country}" if country else "for all countries"
    print(f"Fetching '{disease['name']}' ({indicator_code}) {scope}...")

    df = fetch_indicator(indicator_code, country)

    try:
        validate(df)
    except ValidationError as e:
        print(f"Validation failed: {e}")
        sys.exit(1)

    path = save_csv(df, indicator_code)
    print(f"Saved {len(df)} rows to {path}")


if __name__ == "__main__":
    main()
