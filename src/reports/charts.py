"""Render self-sufficient charts from the analysis JSON - no LLM involved.

Every chart carries its own reading: the final point on each line is labelled
with its value (WHO-chart style), so the latest figure is readable without
prose, and a confidence band is shaded behind the line when the API supplied
Low/High bounds for that year.

Three charts, all plotting numbers already computed by src/analysis or loaded
from the cached CSVs; nothing here performs new calculations beyond a direct
threshold comparison that mirrors src/analysis/anomalies.py's own constant:

- Line chart: indicator value over the recent years in the report, with
  anomaly-flagged years marked and a confidence band if available.
- Bar chart: year-over-year % change for the same recent years, colored by
  whether it crosses the anomaly threshold.
- Comparison chart: Saudi Arabia against the WHO Eastern Mediterranean region
  and the global aggregate, each line end-labelled. Draws with whatever
  series are actually available - never fails if region/global data is
  missing for an indicator.
"""

import matplotlib

matplotlib.use("Agg")  # headless - no display, no GUI backend needed

from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import pandas as pd

from src.analysis.anomalies import YOY_PCT_THRESHOLD

OUTPUT_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "assets"

# Validated palette (dataviz skill): categorical slots 1-3 (blue/orange/aqua)
# are the only three that clear the all-pairs CVD/contrast gates together, so
# they're used for the three comparison-chart series; slot 1 alone is reused
# for the single-series charts. Status palette (green/amber/red) matches the
# report's status badges.
COLOR_LINE = "#2a78d6"  # categorical slot 1 - Saudi Arabia
COLOR_REGION = "#eb6834"  # categorical slot 2 - WHO Eastern Mediterranean region
COLOR_GLOBAL = "#1baf7a"  # categorical slot 3 - global aggregate
COLOR_NORMAL = COLOR_LINE
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


def _fmt_value(value: float) -> str:
    """Compact on-chart number formatting: no trailing ".0", comma thousands."""
    rounded = round(value, 1)
    if rounded == int(rounded):
        return f"{int(rounded):,}"
    return f"{rounded:,.1f}"


def _label_endpoint(ax, x, y, color: str, draw_dot: bool = True) -> None:
    """Mark a line's last point with a colored end-dot and print its value
    next to it (WHO-chart style). The dot carries series identity; the label
    text itself stays neutral ink, per the report's "text never wears the
    data color" rule - identity comes from the dot, not colored text.
    """
    if draw_dot:
        ax.scatter([x], [y], color=color, s=110, zorder=4, edgecolors="white", linewidths=1.5)
    ax.annotate(
        _fmt_value(y),
        xy=(x, y),
        xytext=(8, 0),
        textcoords="offset points",
        fontsize=10,
        fontweight="bold",
        color=COLOR_INK,
        va="center",
        ha="left",
        zorder=5,
    )


def _confidence_band(df: pd.DataFrame) -> Dict[int, Tuple[float, float]]:
    """year -> (low, high) for rows where the API supplied both bounds.
    Returns an empty dict (band skipped silently) if the indicator has no
    Low/High columns at all, or no row has both filled in.
    """
    if df is None or "low" not in df.columns or "high" not in df.columns:
        return {}
    band = {}
    for _, row in df.iterrows():
        low, high = row.get("low"), row.get("high")
        if pd.notna(low) and pd.notna(high):
            band[int(row["year"])] = (float(low), float(high))
    return band


def _line_chart(report: dict, df: pd.DataFrame, path: Path) -> None:
    yoy = report["stats"]["yoy_changes"]
    years = [p["year"] for p in yoy]
    values = [p["value"] for p in yoy]

    anomaly_by_year = {a["year"]: a for a in report["anomalies"]}

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)

    band = _confidence_band(df)
    band_years = [y for y in years if y in band]
    if band_years:
        lows = [band[y][0] for y in band_years]
        highs = [band[y][1] for y in band_years]
        ax.fill_between(band_years, lows, highs, color=COLOR_LINE, alpha=0.12, linewidth=0, zorder=1)

    ax.plot(years, values, color=COLOR_LINE, linewidth=2, marker="o", markersize=6, zorder=2)

    for year, value in zip(years, values):
        flag = anomaly_by_year.get(year)
        if flag:
            color = _severity_color(flag["severity"])
            ax.scatter([year], [value], color=color, s=110, zorder=3, edgecolors="white", linewidths=1.5)

    last_year = years[-1]
    end_flag = anomaly_by_year.get(last_year)
    end_color = _severity_color(end_flag["severity"]) if end_flag else COLOR_LINE
    _label_endpoint(ax, last_year, values[-1], end_color, draw_dot=end_flag is None)

    ax.set_title(f"{report['country_display']} - trend", fontsize=13, fontweight="bold", pad=12, color=COLOR_INK)
    ax.set_ylabel(report["indicator_name"], fontsize=9)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.8, zorder=0)
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=45, ha="right")
    ax.margins(x=0.06)

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

    ax.set_title(f"{report['country_display']} - year-over-year change", fontsize=13, fontweight="bold", pad=12, color=COLOR_INK)
    ax.set_ylabel("% change from previous year", fontsize=9)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.8, zorder=0)
    ax.set_xticks(years)
    ax.set_xticklabels(years, rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _comparison_chart(report: dict, region_df: pd.DataFrame, global_df: pd.DataFrame, path: Path) -> None:
    """Saudi Arabia vs. WHO region vs. global, clipped to the same year range
    as the trend chart. Draws with whatever series exist - if region_df or
    global_df is empty (indicator has no such data), that line is just
    skipped; the chart never fails.
    """
    yoy = report["stats"]["yoy_changes"]
    sau_years = [p["year"] for p in yoy]
    sau_values = [p["value"] for p in yoy]
    year_lo, year_hi = sau_years[0], sau_years[-1]

    series = [(report["country_display"], sau_years, sau_values, COLOR_LINE)]

    if region_df is not None and not region_df.empty:
        r = region_df[region_df["year"].between(year_lo, year_hi)]
        if not r.empty:
            series.append(("Eastern Mediterranean Region", r["year"].tolist(), r["value"].tolist(), COLOR_REGION))

    if global_df is not None and not global_df.empty:
        g = global_df[global_df["year"].between(year_lo, year_hi)]
        if not g.empty:
            series.append(("Global", g["year"].tolist(), g["value"].tolist(), COLOR_GLOBAL))

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)

    all_years = set()
    for name, years, values, color in series:
        ax.plot(years, values, color=color, linewidth=2, marker="o", markersize=5, zorder=2, label=name)
        _label_endpoint(ax, years[-1], values[-1], color)
        all_years.update(years)

    ax.set_title("Saudi Arabia vs. region and world", fontsize=13, fontweight="bold", pad=12, color=COLOR_INK)
    ax.set_ylabel(report["indicator_name"], fontsize=9)
    ax.grid(axis="y", color=COLOR_GRID, linewidth=0.8, zorder=0)
    ticks = sorted(all_years)
    ax.set_xticks(ticks)
    ax.set_xticklabels(ticks, rotation=45, ha="right")
    ax.margins(x=0.08)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=9, loc="best", labelcolor=COLOR_INK)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def generate_charts(report: dict, df: pd.DataFrame, region_df: pd.DataFrame, global_df: pd.DataFrame) -> Dict[str, Path]:
    """Save the line, bar, and comparison charts as PNGs in output/assets/,
    return their paths. df is the Saudi Arabia series (used for the
    confidence band); region_df/global_df are the comparison series, each
    possibly empty.
    """
    OUTPUT_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{report['indicator_code']}_{report['country_display']}_{report['generated_date']}"

    line_path = OUTPUT_ASSETS_DIR / f"{stem}_line.png"
    bar_path = OUTPUT_ASSETS_DIR / f"{stem}_bar.png"
    comparison_path = OUTPUT_ASSETS_DIR / f"{stem}_comparison.png"

    _line_chart(report, df, line_path)
    _bar_chart(report, bar_path)
    _comparison_chart(report, region_df, global_df, comparison_path)

    return {"line_chart": line_path, "bar_chart": bar_path, "comparison_chart": comparison_path}
