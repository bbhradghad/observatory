"""Turn an indicator code into a usable, validated CSV in data/raw/.

By default, reuse the most recent cached CSV for the indicator - no network
call. Only hits the WHO API when refresh=True or no cache exists yet. If the
API is unreachable and a cached CSV exists, falls back to it with a clear
notice instead of failing outright.
"""

import sys

import pandas as pd
import requests

from src.analysis.data import find_latest_comparison_csv, find_latest_csv
from src.gho_client import fetch_indicator, fetch_spatial_aggregate
from src.output import save_csv
from src.validate import TOTAL_DIM1_VALUES, ValidationError, select_dimension, validate

# WHO region Saudi Arabia belongs to, and the global aggregate, used for the
# comparison chart (see src/reports/charts.py). Not user-configurable - this
# project is scoped to Saudi Arabia (see config/country.yaml).
COMPARISON_GEOGRAPHIES = [
    ("REGION", "EMR"),  # WHO Eastern Mediterranean region
    ("GLOBAL", "GLOBAL"),
]


def _cached_date(csv_path) -> str:
    """A cached CSV is named '<indicator_code>_<date>.csv' - pull the date
    back out for user-facing messages."""
    return csv_path.stem.rsplit("_", 1)[-1]


def _reduce_to_total(df: pd.DataFrame) -> pd.DataFrame:
    """Non-interactive counterpart to validate.select_dimension(), used only
    for the comparison fetch below: keep an unambiguous combined total (e.g.
    SEX_BTSX) when a Dim1 breakdown is present, otherwise drop the rows -
    there's no user to prompt here, and the comparison chart already skips
    missing series silently, so an ambiguous geography is just left out
    rather than blocking the report.
    """
    if "Dim1" not in df.columns:
        return df
    with_dim = df[df["Dim1"].notna()]
    if with_dim.empty:
        return df
    distinct = with_dim["Dim1"].unique().tolist()
    if len(distinct) <= 1:
        return df
    dim1_type = with_dim["Dim1Type"].dropna().iloc[0] if "Dim1Type" in with_dim.columns else None
    total_value = TOTAL_DIM1_VALUES.get(dim1_type)
    if total_value and total_value in distinct:
        return df[df["Dim1"] == total_value]
    return df.iloc[0:0]


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


def get_comparison_csv(indicator_code: str, refresh: bool = False):
    """Return the path to a cached CSV of this indicator's WHO-region and
    global aggregate series, for the comparison chart (src/reports/charts.py).

    Reuses the most recent cache unless refresh=True. Unlike
    get_indicator_csv(), this never raises or exits: a geography that fails
    to fetch, comes back empty, or has an ambiguous dimension breakdown is
    just left out of the CSV, so the comparison chart draws with whatever
    series exist - including an empty file, which is itself cached so a
    repeat run doesn't re-hit the network to learn the same indicator has no
    region/global data.
    """
    cached = find_latest_comparison_csv(indicator_code)
    if cached and not refresh:
        print(f"Using cached comparison data: {cached.name}")
        return cached

    frames = []
    for spatial_dim_type, spatial_dim in COMPARISON_GEOGRAPHIES:
        try:
            df = fetch_spatial_aggregate(indicator_code, spatial_dim_type, spatial_dim)
        except requests.RequestException:
            continue
        if df.empty:
            continue
        df = _reduce_to_total(df)
        if not df.empty:
            frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["SpatialDim", "TimeDim", "NumericValue"])
    path = save_csv(combined, indicator_code, suffix="comparison")
    print(f"Saved comparison data ({len(combined)} rows) to {path}")
    return path
