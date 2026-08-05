"""Render simple, clean charts from the analysis JSON - no LLM involved.

Both charts plot numbers already computed by src/analysis (stats.py,
anomalies.py); nothing here performs new calculations beyond a direct
threshold comparison that mirrors src/analysis/anomalies.py's own constant.

- Line chart: indicator value over the recent years in the report, with
  anomaly-flagged years marked.
- Bar chart: year-over-year % change for the same recent years, colored by
  whether it crosses the anomaly threshold.
"""

import matplotlib

matplotlib.use("Agg")  # headless - no display, no GUI backend needed

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt

from src.analysis.anomalies import YOY_PCT_THRESHOLD

OUTPUT_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "assets"

# Validated palette (dataviz skill): categorical slot 1 (blue) for the single
# series, and the fixed status palette for anomaly severity so chart colors
# match the report's green/amber/red status badges.
COLOR_LINE = "#2a78d6"
COLOR_NORMAL = "#2a78d6"
COLOR_HIGH = "#d03b3b"  # status: critical
COLOR_MEDIUM = "#fab219"  # status: warning
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_INK = "#0b0b0b"
COLOR_MUTED = "#52514e"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": COLOR_AXIS,
        "axes.labelcolor": COLOR_MUTED,
        "text.color": COLOR_INK,
        "xtick.color": COLOR_MUTED,
        "ytick.color": COLOR_MUTED,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _severity_color(severity: str) -> str:
    return COLOR_HIGH if severity == "high" else COLOR_MEDIUM


def _line_chart(report: dict, path: Path) -> None:
    yoy = report["stats"]["yoy_changes"]
    years = [p["year"] for p in yoy]
    values = [p["value"] for p in yoy]

    anomaly_by_year = {a["year"]: a for a in report["anomalies"]}

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    ax.plot(years, values, color=COLOR_LINE, linewidth=2, marker="o", markersize=6, zorder=2)

    for year, value in zip(years, values):
        flag = anomaly_by_year.get(year)
        if flag:
            color = _severity_color(flag["severity"])
            ax.scatter([year], [value], color=color, s=110, zorder=3, edgecolors="white", linewidths=1.5)

    ax.set_title(f"{report['disease']} in {report['country']} - trend", fontsize=13, fontweight="bold", pad=12, color=COLOR_INK)
    ax.set_ylabel(report["indicator_name"], fontsize=9)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.8, zorder=0)
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _bar_chart(report: dict, path: Path) -> None:
    yoy = report["stats"]["yoy_changes"]
    years = [p["year"] for p in yoy]
    pct_changes = [p["pct_change"] if p["pct_change"] is not None else 0.0 for p in yoy]

    colors = [COLOR_HIGH if abs(p) >= YOY_PCT_THRESHOLD else COLOR_NORMAL for p in pct_changes]

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    ax.bar(years, pct_changes, color=colors, zorder=2)
    ax.axhline(0, color=COLOR_AXIS, linewidth=0.8, zorder=1)

    ax.set_title(f"{report['disease']} in {report['country']} - year-over-year change", fontsize=13, fontweight="bold", pad=12, color=COLOR_INK)
    ax.set_ylabel("% change from previous year", fontsize=9)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.8, zorder=0)
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def generate_charts(report: dict) -> Dict[str, Path]:
    """Save the line and bar charts as PNGs in output/assets/, return their paths."""
    OUTPUT_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{report['indicator_code']}_{report['country']}_{report['generated_date']}"

    line_path = OUTPUT_ASSETS_DIR / f"{stem}_line.png"
    bar_path = OUTPUT_ASSETS_DIR / f"{stem}_bar.png"

    _line_chart(report, line_path)
    _bar_chart(report, bar_path)

    return {"line_chart": line_path, "bar_chart": bar_path}
