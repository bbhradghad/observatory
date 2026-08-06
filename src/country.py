"""Load the project's single target country from config/country.yaml.

This is the one place that country is read from. api_code (SAU) is what
every WHO GHO API call must use; display_name (KSA) is what every title,
heading, and filename should show. See config/country.yaml for why the two
must not be conflated.
"""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
COUNTRY_FILE = CONFIG_DIR / "country.yaml"


def load_country() -> dict:
    """Return {'api_code', 'display_name', 'full_name'} for the target country."""
    with open(COUNTRY_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
