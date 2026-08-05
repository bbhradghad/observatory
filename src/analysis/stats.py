"""Compute a compact, purely-numeric summary for one indicator/country series.

No text is generated here - only numbers, already rounded to native Python
types so the result can be json.dumps'd directly and handed to an LLM agent
to interpret later.
"""

from typing import List, Optional

import pandas as pd

YOY_HISTORY_LIMIT = 15  # cap how many yoy entries go into the compact JSON


def _pct_change(start: float, end: float) -> Optional[float]:
    if start == 0:
        return None
    return round((end - start) / abs(start) * 100, 1)


def _trend(years: List[int], values: List[float], years_back: int) -> Optional[dict]:
    """Compare the latest value to the closest value at least years_back earlier."""
    if len(years) < 2:
        return None

    end_year, end_value = years[-1], values[-1]
    target_year = end_year - years_back

    start_idx = None
    for i in range(len(years) - 1, -1, -1):
        if years[i] <= target_year:
            start_idx = i
            break
    if start_idx is None:
        return None

    start_year, start_value = years[start_idx], values[start_idx]
    if end_value > start_value:
        direction = "up"
    elif end_value < start_value:
        direction = "down"
    else:
        direction = "flat"

    return {
        "start_year": start_year,
        "start_value": round(start_value, 2),
        "end_year": end_year,
        "end_value": round(end_value, 2),
        "pct_change": _pct_change(start_value, end_value),
        "direction": direction,
    }


def _yoy_changes(years: List[int], values: List[float]) -> List[dict]:
    changes = []
    for i in range(1, len(years)):
        prev_value, value = values[i - 1], values[i]
        changes.append(
            {
                "year": years[i],
                "value": round(value, 2),
                "abs_change": round(value - prev_value, 2),
                "pct_change": _pct_change(prev_value, value),
            }
        )
    return changes[-YOY_HISTORY_LIMIT:]


def compute_stats(df: pd.DataFrame) -> dict:
    """df must have numeric 'year' and 'value' columns, one row per year.

    Rows are sorted by year before computing; rows with a missing value are
    dropped.
    """
    clean = df.dropna(subset=["value"]).sort_values("year")
    years = clean["year"].astype(int).tolist()
    values = clean["value"].astype(float).tolist()

    if not years:
        raise ValueError("No numeric data points to summarize.")

    return {
        "latest": {"year": years[-1], "value": round(values[-1], 2)},
        "data_range": {
            "min_year": years[0],
            "max_year": years[-1],
            "n_points": len(years),
        },
        "trend_5y": _trend(years, values, 5),
        "trend_10y": _trend(years, values, 10),
        "yoy_changes": _yoy_changes(years, values),
    }
