"""Turn an indicator code into a usable, validated CSV in data/raw/.

By default, reuse the most recent cached CSV for the indicator - no network
call. Only hits the WHO API when refresh=True or no cache exists yet. If the
API is unreachable and a cached CSV exists, falls back to it with a clear
notice instead of failing outright.
"""

import sys

import requests

from src.analysis.data import find_latest_csv
from src.gho_client import fetch_indicator
from src.output import save_csv
from src.validate import ValidationError, select_dimension, validate


def _cached_date(csv_path) -> str:
    """A cached CSV is named '<indicator_code>_<date>.csv' - pull the date
    back out for user-facing messages."""
    return csv_path.stem.rsplit("_", 1)[-1]


def get_indicator_csv(indicator_code: str, country_api_code: str, refresh: bool = False):
    """Return the path to a usable CSV for this indicator/country."""
    cached = find_latest_csv(indicator_code)

    if cached and not refresh:
        print(f"Using cached data: {cached.name}")
        return cached

    try:
        df = fetch_indicator(indicator_code, country_api_code)
    except requests.HTTPError as e:
        # A 404 here means the code itself is wrong, not that the API is
        # down - falling back to a stale cache (if any) would be misleading.
        print(f"Error: '{indicator_code}' is not a valid WHO GHO indicator code ({e}).")
        print("Try: python fetch.py --search <keyword>")
        sys.exit(1)
    except requests.RequestException as e:
        if cached:
            print(
                f"Could not reach the WHO API ({e}). "
                f"Using cached data from {cached.name} (fetched {_cached_date(cached)}) instead."
            )
            return cached
        print(f"Error: could not reach the WHO API ({e}), and no cached data exists for {indicator_code}.")
        sys.exit(1)

    try:
        df = select_dimension(df, indicator_code)
        validate(df)
    except ValidationError as e:
        print(f"Validation failed: {e}")
        sys.exit(1)

    path = save_csv(df, indicator_code)
    print(f"Saved {len(df)} rows to {path}")
    return path
