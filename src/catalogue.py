"""The full WHO GHO indicator catalogue (~3,000 entries) - fetched once from
/api/Indicator and cached locally so search and code-to-name lookups work
offline. Refreshed only via an explicit --refresh-catalogue flag; nothing
else here touches the network.
"""

import json
from pathlib import Path
from typing import List, Optional

import requests

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CATALOGUE_FILE = CONFIG_DIR / "indicator_catalogue.json"
INDICATOR_LIST_URL = "https://ghoapi.azureedge.net/api/Indicator"
TIMEOUT = 60


def refresh_catalogue() -> int:
    """Fetch the full indicator list from the API and overwrite the local
    cache. Returns the number of indicators cached."""
    response = requests.get(INDICATOR_LIST_URL, timeout=TIMEOUT)
    response.raise_for_status()
    records = response.json().get("value", [])

    catalogue = [
        {"code": r["IndicatorCode"], "name": r["IndicatorName"]}
        for r in records
        if r.get("IndicatorCode") and r.get("IndicatorName")
    ]

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CATALOGUE_FILE, "w", encoding="utf-8") as f:
        json.dump(catalogue, f, indent=2)
    return len(catalogue)


def load_catalogue() -> List[dict]:
    """Return the cached catalogue as a list of {'code', 'name'} dicts, or an
    empty list with a printed hint if it hasn't been fetched yet."""
    if not CATALOGUE_FILE.exists():
        print(
            "No local indicator catalogue found. Run this once (needs network): "
            "python fetch.py --refresh-catalogue"
        )
        return []
    with open(CATALOGUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def search_catalogue(keyword: str, limit: int = 20) -> List[dict]:
    """Case-insensitive, partial-word search over cached indicator names,
    ranked by relevance (exact/prefix matches and shorter names first)."""
    catalogue = load_catalogue()
    keyword_lower = keyword.lower().strip()
    words = keyword_lower.split()
    if not words:
        return []

    scored = []
    for entry in catalogue:
        name_lower = entry["name"].lower()
        if not all(w in name_lower for w in words):
            continue
        score = 0.0
        if name_lower == keyword_lower:
            score += 100
        if name_lower.startswith(keyword_lower):
            score += 50
        score += name_lower.count(keyword_lower) * 10
        score -= len(name_lower) * 0.01  # prefer shorter, more specific names
        scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


def get_indicator_name(code: str) -> Optional[str]:
    """Look up an indicator's display name from the cached catalogue."""
    for entry in load_catalogue():
        if entry["code"] == code:
            return entry["name"]
    return None
