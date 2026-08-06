"""Assemble python-computed stats/anomalies (and later, LLM narrative text)
into the analysis-stage output files: one compact JSON, one markdown narrative.
"""

import datetime
import json
from pathlib import Path

DATA_ANALYSIS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "analysis"


def build_report(disease_key: str, disease: dict, country: dict, stats: dict, anomalies: list) -> dict:
    """country is the dict from src.country.load_country(): 'country' below
    stays the ISO3 API code (SAU) for provenance; 'country_display' (KSA) is
    what titles, headings, and filenames should show."""
    return {
        "disease_key": disease_key,
        "disease": disease["name"],
        "indicator_code": disease["indicator_code"],
        "indicator_name": disease["indicator_name"],
        "country": country["api_code"],
        "country_display": country["display_name"],
        "country_full_name": country["full_name"],
        "generated_date": datetime.date.today().isoformat(),
        "stats": stats,
        "anomalies": anomalies,
    }


def save_report(report: dict) -> Path:
    """Write the compact stats+anomalies JSON that the LLM agents will read."""
    DATA_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_ANALYSIS_DIR / f"{report['indicator_code']}_{report['generated_date']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return path


def save_narrative(report: dict, analyst_text: str, anomaly_text: str) -> Path:
    """Write the LLM-generated plain-English narrative alongside the JSON."""
    DATA_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_ANALYSIS_DIR / f"{report['indicator_code']}_{report['generated_date']}_narrative.md"
    content = (
        f"# {report['disease']} in {report['country_display']} - {report['generated_date']}\n\n"
        f"*Indicator: {report['indicator_name']} ({report['indicator_code']})*\n\n"
        f"## Analyst interpretation\n\n{analyst_text.strip()}\n\n"
        f"## Anomaly review\n\n{anomaly_text.strip()}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path
