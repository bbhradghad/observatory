#!/usr/bin/env python
"""Generate a chart-first, non-technical health indicator report for Saudi Arabia.

Full pipeline: fetch if needed (country series + region/global comparison
series) -> analyze -> charts -> agents -> HTML + DOCX, written to output/.

Numbers are computed ONLY in python (src/analysis). The LLM agents only turn
those numbers into short supporting copy - a one-line definition, a 2-3
sentence executive summary, and one caption per chart - and never invent or
recalculate anything. Section status (green/amber/red) is derived from the
anomaly flags in python (src/reports/status.py) - the agents report it, they
don't decide it. Country is fixed to Saudi Arabia (see config/country.yaml);
indicators can be a shortlist key or any open WHO GHO code.

Examples:
    python report.py --disease tb
"""

import argparse
import sys

from analyze import get_series, interactive_select
from src.agents.crew import run_narrative
from src.agents.llm import check_ollama_ready
from src.analysis.anomalies import detect_anomalies
from src.analysis.data import load_series
from src.analysis.report import build_report, save_narrative, save_report
from src.analysis.stats import compute_stats
from src.config import get_disease, resolve_indicator
from src.country import load_country
from src.data_pipeline import get_comparison_csv
from src.reports.charts import generate_charts
from src.reports.docx import save_docx
from src.reports.html import save_html
from src.reports.status import derive_status


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a polished HTML/DOCX health indicator report for Saudi Arabia."
    )
    parser.add_argument("--disease", help="Disease key from config/indicators.yaml (shortlist shortcut)")
    parser.add_argument("--indicator", help="Any WHO GHO indicator code (open catalogue)")
    parser.add_argument("--refresh", action="store_true", help="Bypass the cached CSV and re-fetch from the API")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.disease:
        try:
            disease = get_disease(args.disease)
        except KeyError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.indicator:
        disease = resolve_indicator(args.indicator)
    else:
        disease = get_disease(interactive_select())

    df = get_series(disease, refresh=args.refresh)
    if df.empty:
        print(f"No usable data for {disease['name']}.")
        sys.exit(1)

    comparison_csv = get_comparison_csv(disease["indicator_code"], refresh=args.refresh)
    region_df = load_series(comparison_csv, "EMR")
    global_df = load_series(comparison_csv, "GLOBAL")
    has_region, has_global = not region_df.empty, not global_df.empty

    stats = compute_stats(df)
    anomalies = detect_anomalies(df)

    country = load_country()
    report = build_report(disease.get("indicator_code"), disease, country, stats, anomalies)
    json_path = save_report(report)
    print(f"Saved analysis JSON to {json_path}")

    print("Generating charts...")
    chart_paths = generate_charts(report, df, region_df, global_df)
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
    narrative = run_narrative(
        stats,
        anomalies,
        trend_status,
        anomaly_status,
        indicator_name=report["indicator_name"],
        country_display=report["country_display"],
        has_region=has_region,
        has_global=has_global,
    )
    save_narrative(report, narrative["analyst"], narrative["anomaly_reviewer"])

    html_path = save_html(
        report, narrative, chart_paths, trend_status, anomaly_status, overall_status, has_region, has_global
    )
    print(f"Saved HTML report to {html_path}")

    docx_path = save_docx(
        report, narrative, chart_paths, trend_status, anomaly_status, overall_status, has_region, has_global
    )
    print(f"Saved Word report to {docx_path}")


if __name__ == "__main__":
    main()
