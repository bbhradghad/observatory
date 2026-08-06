"""Load project configuration: the curated shortlist of favourite indicators
(config/indicators.yaml), and resolution of arbitrary open-catalogue codes
into the same shape.
"""

import re
from pathlib import Path

import yaml

from src.catalogue import get_indicator_name

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
INDICATORS_FILE = CONFIG_DIR / "indicators.yaml"


def load_diseases() -> dict:
    """Return the full disease-key -> indicator-info mapping."""
    with open(INDICATORS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["diseases"]


def get_disease(key: str) -> dict:
    """Return the config entry for one shortlist disease key, or raise KeyError."""
    diseases = load_diseases()
    if key not in diseases:
        available = ", ".join(sorted(diseases))
        raise KeyError(f"Unknown disease '{key}'. Available: {available}")
    return diseases[key]


def resolve_indicator(code: str) -> dict:
    """Resolve any WHO GHO indicator code (not necessarily in the shortlist)
    into the same {'name', 'indicator_code', 'indicator_name'} shape as
    get_disease(), using the cached catalogue for its display name."""
    name = get_indicator_name(code) or code
    return {"name": name, "indicator_code": code, "indicator_name": name}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:40] or "indicator"


def add_favourite(name: str, indicator_code: str, indicator_name: str) -> str:
    """Append a validated indicator to config/indicators.yaml as a new
    shortlist favourite, keyed by a slug derived from its name (de-duplicated
    against existing keys). Appends as plain text rather than a full YAML
    re-dump, so the file's header comment and formatting survive. Returns the
    key used.
    """
    diseases = load_diseases()
    base_key = _slugify(name)
    key = base_key
    n = 1
    while key in diseases:
        n += 1
        key = f"{base_key}_{n}"

    block = f"\n  {key}:\n    name: {name}\n    indicator_code: {indicator_code}\n    indicator_name: {indicator_name}\n"
    with open(INDICATORS_FILE, "a", encoding="utf-8") as f:
        f.write(block)
    return key
