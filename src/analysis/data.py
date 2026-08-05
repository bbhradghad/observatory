"""Load a previously fetched indicator CSV (see src/output.py) for analysis."""

from pathlib import Path
from typing import Optional

import pandas as pd

DATA_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def find_latest_csv(indicator_code: str) -> Optional[Path]:
    """Return the most recently dated CSV for this indicator, if one exists."""
    matches = sorted(DATA_RAW_DIR.glob(f"{indicator_code}_*.csv"))
    return matches[-1] if matches else None


def load_series(csv_path: Path, country: Optional[str] = None) -> pd.DataFrame:
    """Load one country's year/value series from a fetched CSV, sorted by year.

    Rows with missing year or value are dropped. If the CSV has multiple
    countries and `country` is given, it is filtered down to that one.
    """
    df = pd.read_csv(csv_path)
    if country and "country" in df.columns:
        df = df[df["country"] == country.upper()]

    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["year", "value"]).sort_values("year").reset_index(drop=True)
    return df
