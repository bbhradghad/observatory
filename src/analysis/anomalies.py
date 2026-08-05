"""Flag unusual points in an indicator/country series using simple, explainable
statistical rules - no LLM involved. Each flag already includes a plain-English
reason string; the LLM's job later is only to elaborate on it, not compute it.

Two independent checks:
- Year-over-year change beyond a percentage threshold.
- Deviation from a rolling baseline (z-score against the previous N years).
"""

import statistics
from typing import List

import pandas as pd

YOY_PCT_THRESHOLD = 20.0  # flag if |YoY % change| exceeds this
BASELINE_WINDOW = 5  # years used to compute the rolling baseline
ZSCORE_THRESHOLD = 2.0  # flag if |z-score| exceeds this


def _check_yoy(years: List[int], values: List[float]) -> List[dict]:
    flags = []
    for i in range(1, len(years)):
        prev_value, value = values[i - 1], values[i]
        if prev_value == 0:
            continue
        pct_change = (value - prev_value) / abs(prev_value) * 100
        if abs(pct_change) < YOY_PCT_THRESHOLD:
            continue
        direction = "increased" if pct_change > 0 else "decreased"
        flags.append(
            {
                "year": years[i],
                "value": round(value, 2),
                "type": "yoy_change",
                "severity": "high" if abs(pct_change) >= 2 * YOY_PCT_THRESHOLD else "medium",
                "metric": round(pct_change, 1),
                "reason": (
                    f"Value {direction} {abs(round(pct_change, 1))}% from {years[i - 1]} "
                    f"({round(prev_value, 2)}) to {years[i]} ({round(value, 2)}), more than "
                    f"the {YOY_PCT_THRESHOLD:.0f}% single-year threshold."
                ),
            }
        )
    return flags


def _check_baseline(years: List[int], values: List[float]) -> List[dict]:
    flags = []
    for i in range(BASELINE_WINDOW, len(years)):
        baseline = values[i - BASELINE_WINDOW : i]
        mean = statistics.fmean(baseline)
        stdev = statistics.pstdev(baseline)
        if stdev == 0:
            continue
        z = (values[i] - mean) / stdev
        if abs(z) < ZSCORE_THRESHOLD:
            continue
        flags.append(
            {
                "year": years[i],
                "value": round(values[i], 2),
                "type": "baseline_deviation",
                "severity": "high" if abs(z) >= 1.5 * ZSCORE_THRESHOLD else "medium",
                "metric": round(z, 2),
                "reason": (
                    f"Value {round(values[i], 2)} in {years[i]} is {abs(round(z, 1))} standard "
                    f"deviations from the average of the previous {BASELINE_WINDOW} years "
                    f"({round(mean, 2)})."
                ),
            }
        )
    return flags


def detect_anomalies(df: pd.DataFrame) -> List[dict]:
    """df must have numeric 'year' and 'value' columns. Returns flags sorted by year."""
    clean = df.dropna(subset=["value"]).sort_values("year")
    years = clean["year"].astype(int).tolist()
    values = clean["value"].astype(float).tolist()

    flags = _check_yoy(years, values) + _check_baseline(years, values)
    flags.sort(key=lambda f: f["year"])
    return flags
