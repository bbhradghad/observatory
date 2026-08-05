"""Load project configuration from config/indicators.yaml."""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
INDICATORS_FILE = CONFIG_DIR / "indicators.yaml"


def load_diseases() -> dict:
    """Return the full disease-key -> indicator-info mapping."""
    with open(INDICATORS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["diseases"]


def get_disease(key: str) -> dict:
    """Return the config entry for one disease key, or raise KeyError."""
    diseases = load_diseases()
    if key not in diseases:
        available = ", ".join(sorted(diseases))
        raise KeyError(f"Unknown disease '{key}'. Available: {available}")
    return diseases[key]
