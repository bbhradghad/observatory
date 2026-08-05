#!/usr/bin/env python
"""Generate a polished, non-technical health indicator report.

Full pipeline: fetch if needed -> analyze -> agents -> charts -> HTML + DOCX,
written to output/.

Numbers are computed ONLY in python (src/analysis). The LLM agents only turn
those numbers into prose, and never invent or recalculate anything. Section
status (green/amber/red) is derived from the anomaly flags in python
(src/reports/status.py) - the agents report it, they don't decide it.

Examples:
    python report.py --disease tb --country SAU
    python report.py                                 # interactive menu
"""

import argparse
import sys

from analyze import get_series, interactive_select
from src.agents.crew import run_narrative
from src.agents.llm import check_ollama_ready
from src.analysis.anomalies import detect_anomalies
from src.analysis.report import build_report, save_narrative, save_report
from src.analysis.stats import compute_stats
from src.config import get_disease
from src.reports.charts import generate_charts
from src.reports.docx import save_docx
from src.reports.html import save_html
from src.reports.status import derive_status


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a polished HTML/DOCX health indicator report."
    )
    parser.add_argument("--disease", help="Disease key from config/indicators.yaml (e.g. tb)")
    parser.add_argument("--country", help="ISO3 country code (e.g. SAU)")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.disease:
        if not args.country:
            print("Error: --country is required when --disease is given.")
            sys.exit(1)
        disease_key, country = args.disease, args.country
    else:
        disease_key, country = interactive_select()

    try:
        disease = get_disease(disease_key)
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)

    df = get_series(disease, country)
    if df.empty:
        print(f"No usable data for {disease['name']} in {country}.")
        sys.exit(1)

    stats = compute_stats(df)
    anomalies = detect_anomalies(df)

    report = build_report(disease_key, disease, country, stats, anomalies)
    json_path = save_report(report)
    print(f"Saved analysis JSON to {json_path}")

    print("Generating charts...")
    chart_paths = generate_charts(report)
    print(f"Saved charts to {chart_paths['line_chart'].parent}")

    trend_5y = stats.get("trend_5y")
    trend_status = derive_status(anomalies, since_year=trend_5y["start_year"] if trend_5y else None)
    anomaly_status = derive_status(anomalies)
    overall_status = anomaly_status

    ready_error = check_ollama_ready()
    if ready_error:
        print("\nReport generation stopped - Ollama is not ready (JSON and charts were already saved):")
        print(ready_error)
        sys.exit(1)

    print("Running local agents (this can take a few minutes on CPU)...")
    narrative = run_narrative(stats, anomalies, trend_status, anomaly_status)
    save_narrative(report, narrative["analyst"], narrative["anomaly_reviewer"])

    html_path = save_html(report, narrative, chart_paths, trend_status, anomaly_status, overall_status)
    print(f"Saved HTML report to {html_path}")

    docx_path = save_docx(report, narrative, chart_paths, trend_status, anomaly_status, overall_status)
    print(f"Saved Word report to {docx_path}")


if __name__ == "__main__":
    main()
