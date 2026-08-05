"""Derive green/amber/red section status from anomaly flags - no LLM involved.

The Report Writer agent is handed these ratings as already-decided facts; it
never assigns or reinterprets them.
"""

from typing import List, Optional

GREEN, AMBER, RED = "green", "amber", "red"


def derive_status(anomalies: List[dict], since_year: Optional[int] = None) -> str:
    """Red if any high-severity flag is present, amber if any medium-severity
    flag is present, else green. If since_year is given, only flags in or
    after that year are considered.
    """
    relevant = [a for a in anomalies if since_year is None or a["year"] >= since_year]
    if any(a["severity"] == "high" for a in relevant):
        return RED
    if any(a["severity"] == "medium" for a in relevant):
        return AMBER
    return GREEN
