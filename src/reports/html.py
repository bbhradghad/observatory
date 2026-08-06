"""Render a single, self-contained HTML report - charts embedded as base64,
no external CSS/JS, no server needed. This is the primary report interface.

Chart-first design: each chart sits in its own card (indicator name, a
one-line plain-language definition, a scope line, the chart, one caption) and
carries its own meaning - the surrounding text is supporting copy, not the
main content. The Analyst/Anomaly Reviewer's fuller narratives live in a
collapsed "Detailed notes" <details> section at the end, out of the main
reading path.
"""

import base64
import html
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

STATUS_LABEL = {"green": "On track", "amber": "Worth a look", "red": "Needs attention"}

_CSS = """
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-secondary: #52514e;
  --ink-muted: #898781;
  --border: rgba(11,11,11,0.10);
  --accent: #2a78d6;
  --good: #0ca30c;
  --warning: #b8790f;
  --critical: #d03b3b;
  --good-bg: #e6f6e6;
  --warning-bg: #fdf1dc;
  --critical-bg: #fbe7e7;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page: #0d0d0d;
    --surface: #1a1a19;
    --ink: #ffffff;
    --ink-secondary: #c3c2b7;
    --ink-muted: #898781;
    --border: rgba(255,255,255,0.10);
    --accent: #3987e5;
    --good: #0ca30c;
    --warning: #fab219;
    --critical: #e66767;
    --good-bg: #113311;
    --warning-bg: #3a2c0e;
    --critical-bg: #3a1414;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d;
  --surface: #1a1a19;
  --ink: #ffffff;
  --ink-secondary: #c3c2b7;
  --ink-muted: #898781;
  --border: rgba(255,255,255,0.10);
  --accent: #3987e5;
  --good: #0ca30c;
  --warning: #fab219;
  --critical: #e66767;
  --good-bg: #113311;
  --warning-bg: #3a2c0e;
  --critical-bg: #3a1414;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 48px 24px;
  background: var(--page);
  color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.6;
}
.report {
  max-width: 760px;
  margin: 0 auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 48px 56px;
}
header { margin-bottom: 32px; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0 0 8px;
}
h1 { font-size: 28px; margin: 0 0 6px; font-weight: 700; }
.subtitle { color: var(--ink-secondary); font-size: 14px; margin: 0; }
section { margin: 40px 0; }
h2 {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-muted);
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
p { margin: 0 0 12px; color: var(--ink); }
.exec-summary {
  font-size: 17px;
  padding: 20px 24px;
  background: var(--good-bg);
  border-radius: 10px;
  border-left: 4px solid var(--good);
}
.exec-summary.amber { background: var(--warning-bg); border-left-color: var(--warning); }
.exec-summary.red { background: var(--critical-bg); border-left-color: var(--critical); }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  padding: 3px 10px;
  border-radius: 999px;
  text-transform: none;
}
.badge.green { background: var(--good-bg); color: var(--good); }
.badge.amber { background: var(--warning-bg); color: var(--warning); }
.badge.red { background: var(--critical-bg); color: var(--critical); }
.badge::before { content: "\\25CF"; font-size: 9px; }
.chart-card { margin: 40px 0; }
.chart-card .card-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 4px;
  color: var(--ink);
}
.chart-def { font-size: 14px; color: var(--ink-secondary); margin: 0 0 4px; }
.chart-scope {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0 0 14px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
figure { margin: 0 0 12px; }
img.chart {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 8px;
  background: #fcfcfb;
  border: 1px solid var(--border);
}
figcaption {
  font-size: 14px;
  color: var(--ink-secondary);
  margin-top: 10px;
  font-style: italic;
}
.stat-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin: 4px 0 20px;
}
.stat {
  flex: 1 1 140px;
  padding: 14px 16px;
  background: var(--page);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.stat .label { font-size: 11px; color: var(--ink-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }
.stat .value { font-size: 20px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 8px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { color: var(--ink-muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; }
td.severity-high { color: var(--critical); font-weight: 600; }
td.severity-medium { color: var(--warning); font-weight: 600; }
details.detailed-notes {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
details.detailed-notes summary {
  cursor: pointer;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-muted);
  font-weight: 600;
}
details.detailed-notes .notes-body { margin-top: 18px; }
details.detailed-notes h3 { font-size: 14px; margin: 20px 0 8px; color: var(--ink); }
details.detailed-notes h3:first-child { margin-top: 0; }
footer {
  margin-top: 48px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--ink-muted);
}
@media print {
  body { padding: 0; background: white; }
  .report { border: none; border-radius: 0; max-width: 100%; padding: 0; }
  section, .chart-card { page-break-inside: avoid; }
}
"""


def _img_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _badge(status: str) -> str:
    return f'<span class="badge {status}">{STATUS_LABEL[status]}</span>'


def _fmt_trend(trend: dict) -> str:
    if not trend:
        return "Not enough data"
    arrow = {"up": "↑", "down": "↓", "flat": "→"}[trend["direction"]]
    pct = f"{trend['pct_change']:+.1f}%" if trend["pct_change"] is not None else "n/a"
    return f"{arrow} {pct} ({trend['start_year']}–{trend['end_year']})"


def _fmt_anomaly_change(a: dict) -> str:
    """Compact "Change" column for the anomaly table: a % for a year-over-year
    flag, a standard-deviation count for a baseline-deviation flag - the two
    anomaly checks in src/analysis/anomalies.py measure different things, so
    they get different units rather than a misleading shared one."""
    if a["type"] == "yoy_change":
        return f"{a['metric']:+.1f}%"
    return f"{a['metric']:+.1f}σ vs baseline"


def _anomaly_rows(anomalies: list) -> str:
    if not anomalies:
        return '<tr><td colspan="3">No anomalies detected.</td></tr>'
    rows = []
    for a in anomalies:
        rows.append(
            f'<tr><td>{a["year"]}</td><td>{html.escape(_fmt_anomaly_change(a))}</td>'
            f'<td class="severity-{a["severity"]}">{a["severity"].title()}</td></tr>'
        )
    return "\n".join(rows)


def _scope_line(report: dict, first_year: int, last_year: int, note: str = None) -> str:
    base = f"Saudi Arabia ({report['country_display']}), {first_year} - {last_year}"
    return f"{base} ({note})" if note else base


def _comparison_note(has_region: bool, has_global: bool) -> str:
    if has_region and has_global:
        return None
    missing = []
    if not has_region:
        missing.append("regional")
    if not has_global:
        missing.append("global")
    return f"{' and '.join(missing)} comparison data not available for this indicator"


def _chart_card(title: str, definition: str, scope: str, img_src: str, alt: str, caption: str) -> str:
    return f"""
  <div class="chart-card">
    <p class="card-title">{html.escape(title)}</p>
    <p class="chart-def">{html.escape(definition)}</p>
    <p class="chart-scope">{html.escape(scope)}</p>
    <figure>
      <img class="chart" src="{img_src}" alt="{html.escape(alt)}">
      <figcaption>{html.escape(caption)}</figcaption>
    </figure>
  </div>
"""


def render_html(
    report: dict,
    narrative: dict,
    chart_paths: dict,
    trend_status: str,
    anomaly_status: str,
    overall_status: str,
    has_region: bool,
    has_global: bool,
) -> str:
    stats = report["stats"]
    latest = stats["latest"]
    yoy_years = [p["year"] for p in stats["yoy_changes"]]
    first_year, last_year = yoy_years[0], yoy_years[-1]

    stat_tiles = f"""
    <div class="stat-row">
      <div class="stat"><div class="label">Latest value ({latest['year']})</div><div class="value">{latest['value']}</div></div>
      <div class="stat"><div class="label">5-year change</div><div class="value">{_fmt_trend(stats.get('trend_5y'))}</div></div>
      <div class="stat"><div class="label">10-year change</div><div class="value">{_fmt_trend(stats.get('trend_10y'))}</div></div>
    </div>
    """

    indicator_name = report["indicator_name"]
    trend_card = _chart_card(
        indicator_name,
        narrative["definition"],
        _scope_line(report, first_year, last_year),
        _img_data_uri(chart_paths["line_chart"]),
        "Trend chart",
        narrative["trend_caption"],
    )
    change_card = _chart_card(
        indicator_name,
        narrative["definition"],
        _scope_line(report, first_year, last_year),
        _img_data_uri(chart_paths["bar_chart"]),
        "Year-over-year change chart",
        narrative["change_caption"],
    )
    comparison_card = _chart_card(
        indicator_name,
        narrative["definition"],
        _scope_line(report, first_year, last_year, _comparison_note(has_region, has_global)),
        _img_data_uri(chart_paths["comparison_chart"]),
        "Comparison chart",
        narrative["comparison_caption"],
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(report['disease'])} in {html.escape(report['country_display'])} - {report['generated_date']}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="report">
  <header>
    <p class="eyebrow">Health Indicator Report</p>
    <h1>{html.escape(report['disease'])} in {html.escape(report['country_display'])}</h1>
    <p class="subtitle">{html.escape(report['indicator_name'])} &middot; generated {report['generated_date']}</p>
  </header>

  <section>
    <h2>Executive summary {_badge(overall_status)}</h2>
    <div class="exec-summary {overall_status}">
      <p>{html.escape(narrative['executive_summary'])}</p>
    </div>
    {stat_tiles}
  </section>

  {trend_card}
  {change_card}
  {comparison_card}

  <section>
    <h2>Anomalies {_badge(anomaly_status)}</h2>
    <table>
      <thead><tr><th>Year</th><th>Change</th><th>Severity</th></tr></thead>
      <tbody>{_anomaly_rows(report['anomalies'])}</tbody>
    </table>
  </section>

  <details class="detailed-notes">
    <summary>Detailed notes</summary>
    <div class="notes-body">
      <h3>Analyst interpretation</h3>
      <p>{html.escape(narrative['analyst'])}</p>
      <h3>Anomaly review</h3>
      <p>{html.escape(narrative['anomaly_reviewer'])}</p>
    </div>
  </details>

  <footer>
    Source: WHO Global Health Observatory (indicator {html.escape(report['indicator_code'])}).
    This report is generated automatically from statistical analysis and is not medical advice.
  </footer>
</div>
</body>
</html>
"""


def save_html(
    report: dict,
    narrative: dict,
    chart_paths: dict,
    trend_status: str,
    anomaly_status: str,
    overall_status: str,
    has_region: bool,
    has_global: bool,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{report['indicator_code']}_{report['country_display']}_{report['generated_date']}"
    path = OUTPUT_DIR / f"{stem}.html"
    content = render_html(
        report, narrative, chart_paths, trend_status, anomaly_status, overall_status, has_region, has_global
    )
    path.write_text(content, encoding="utf-8")
    return path
