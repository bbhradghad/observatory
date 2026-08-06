"""Save validated GHO data as a clean CSV in data/raw/."""

import datetime
from pathlib import Path

import pandas as pd

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# GHO API column -> clean output column. Low/High (confidence interval
# bounds) are kept only when the indicator provides them.
COLUMN_MAP = {
    "SpatialDim": "country",
    "TimeDim": "year",
    "NumericValue": "value",
    "Low": "low",
    "High": "high",
}


def save_csv(df: pd.DataFrame, indicator_code: str, suffix: str = "") -> Path:
    """Write a clean, sorted CSV and return its path.

    suffix, if given, is inserted before the date (e.g. "comparison") so a
    second series for the same indicator - the region/global comparison
    fetch in data_pipeline.py - gets its own cache file instead of
    colliding with the main country-level one.
    """
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    keep = [c for c in COLUMN_MAP if c in df.columns]
    clean = df[keep].rename(columns=COLUMN_MAP) if keep else pd.DataFrame(columns=["country", "year", "value"])
    if not clean.empty:
        clean = clean.sort_values(["country", "year"]).reset_index(drop=True)

    date_str = datetime.date.today().isoformat()
    tag = f"_{suffix}" if suffix else ""
    filename = f"{indicator_code}{tag}_{date_str}.csv"
    path = DATA_RAW_DIR / filename
    clean.to_csv(path, index=False)
    return path
