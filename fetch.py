#!/usr/bin/env python
"""Fetch a WHO GHO health indicator for Saudi Arabia and save it as a CSV in
data/raw/.

Indicators are
open: search the full WHO catalogue, fetch any indicator by code, or use the
small curated shortlist in config/indicators.yaml for quick access.

Examples:
    python fetch.py --search tuberculosis
    python fetch.py --indicator MDG_0000000020
    python fetch.py --indicator MDG_0000000020 --add-favourite
    python fetch.py --disease tb                      # shortlist shortcut
    python fetch.py                                    # interactive shortlist menu
    python fetch.py --disease tb --refresh              # bypass the local cache
    python fetch.py --refresh-catalogue                 # re-fetch the indicator list
"""

import argparse
import sys

from src.catalogue import refresh_catalogue, search_catalogue
from src.config import add_favourite, get_disease, load_diseases, resolve_indicator
from src.country import load_country
from src.data_pipeline import get_indicator_csv


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch a WHO GHO health indicator for Saudi Arabia.")
    parser.add_argument("--disease", help="Disease key from config/indicators.yaml (shortlist shortcut)")
    parser.add_argument("--indicator", help="Any WHO GHO indicator code (open catalogue)")
    parser.add_argument("--search", help="Search the local indicator catalogue by keyword")
    parser.add_argument("--refresh", action="store_true", help="Bypass the cached CSV and re-fetch from the API")
    parser.add_argument(
        "--refresh-catalogue", action="store_true", help="Re-fetch the full WHO indicator catalogue from the API"
    )
    parser.add_argument(
        "--add-favourite", action="store_true", help="Save a fetched --indicator to the shortlist (config/indicators.yaml)"
    )
    return parser.parse_args()


def interactive_select():
    diseases = load_diseases()
    keys = sorted(diseases)

    print("Shortlist (config/indicators.yaml):")
    for i, key in enumerate(keys, start=1):
        print(f"  {i}. {key} - {diseases[key]['name']}")
    print("(Use --search <keyword> to find any other WHO indicator.)")

    choice = input(f"Select a disease [1-{len(keys)}]: ").strip()
    try:
        return keys[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        sys.exit(1)


def main():
    args = parse_args()

    if args.refresh_catalogue:
        print("Fetching the full WHO GHO indicator catalogue...")
        count = refresh_catalogue()
        print(f"Cached {count} indicators to config/indicator_catalogue.json")
        return

    if args.search:
        results = search_catalogue(args.search)
        if not results:
            print(f"No indicators found matching '{args.search}'.")
            print("If you haven't fetched the catalogue yet, run: python fetch.py --refresh-catalogue")
            return
        print(f"Indicators matching '{args.search}':")
        for entry in results:
            print(f"  {entry['code']:<40} {entry['name']}")
        return

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

    country = load_country()
    indicator_code = disease["indicator_code"]
    print(f"Fetching '{disease['name']}' ({indicator_code}) for {country['display_name']}...")

    get_indicator_csv(indicator_code, country["api_code"], refresh=args.refresh)

    if args.add_favourite:
        if args.disease:
            print(f"'{args.disease}' is already in the shortlist.")
        else:
            key = add_favourite(disease["name"], indicator_code, disease["indicator_name"])
            print(f"Added '{key}' to config/indicators.yaml as a favourite.")


if __name__ == "__main__":
    main()
