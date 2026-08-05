"""Minimal client for the WHO Global Health Observatory (GHO) OData API.

No API key or registration required.
Docs: https://www.who.int/data/gho/info/gho-odata-api
"""

from typing import Optional

import pandas as pd
import requests

BASE_URL = "https://ghoapi.azureedge.net/api"
TIMEOUT = 30


def fetch_indicator(indicator_code: str, country: Optional[str] = None) -> pd.DataFrame:
    """Fetch raw records for one indicator, optionally filtered to one country.

    country: ISO3 code (e.g. "SAU"). If None, returns data for all
    countries/regions the API has for this indicator.
    """
    url = f"{BASE_URL}/{indicator_code}"
    params = {}
    if country:
        params["$filter"] = f"SpatialDim eq '{country.upper()}'"

    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    records = response.json().get("value", [])

    return pd.DataFrame.from_records(records)
