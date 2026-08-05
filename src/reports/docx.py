"""Render the same report content as a Word document."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

STATUS_LABEL = {"green": "On track", "amber": "Worth a look", "red": "Needs attention"}
STATUS_COLOR = {
    "green": RGBColor(0x0C, 0xA3, 0x0C),
    "amber": RGBColor(0xB8, 0x79, 0x0F),
    "red": RGBColor(0xD0, 0x3B, 0x3B),
}
INK_SECONDARY = RGBColor(0x52, 0x51, 0x4E)
INK_MUTED = RGBColor(0x89, 0x87, 0x81)


def _status_line(doc: Document, status: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"Status: {STATUS_LABEL[status]}")
    run.bold = True
    run.font.color.rgb = STATUS_COLOR[status]
    run.font.size = Pt(10)


def _caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = True
    run.font.size = Pt(10)
    run.font.color.rgb = INK_SECONDARY


def _fmt_trend(trend: dict) -> str:
    if not trend:
        return "Not enough data"
    arrow = {"up": "up", "down": "down", "flat": "flat"}[trend["direction"]]
    pct = f"{trend['pct_change']:+.1f}%" if trend["pct_change"] is not None else "n/a"
    return f"{arrow} {pct} ({trend['start_year']}-{trend['end_year']})"


def _add_stats_table(doc: Document, stats: dict) -> None:
    latest = stats["latest"]
    table = doc.add_table(rows=2, cols=3)
    table.style = "Light Grid Accent 1"
    headers = [f"Latest value ({latest['year']})", "5-year change", "10-year change"]
    values = [str(latest["value"]), _fmt_trend(stats.get("trend_5y")), _fmt_trend(stats.get("trend_10y"))]
    for i, text in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.paragraphs[0].add_run(text).bold = True
    for i, text in enumerate(values):
        table.rows[1].cells[i].paragraphs[0].add_run(text)


def _add_anomaly_table(doc: Document, anomalies: list) -> None:
    if not anomalies:
        doc.add_paragraph("No anomalies detected.")
        return
    table = doc.add_table(rows=1 + len(anomalies), cols=4)
    table.style = "Light Grid Accent 1"
    for i, header in enumerate(["Year", "Value", "Concern", "Reason"]):
        table.rows[0].cells[i].paragraphs[0].add_run(header).bold = True
    for r, a in enumerate(anomalies, start=1):
        row = table.rows[r]
        row.cells[0].text = str(a["year"])
        row.cells[1].text = str(a["value"])
        severity_run = row.cells[2].paragraphs[0].add_run(a["severity"].title())
        if a["severity"] in ("high", "medium"):
            severity_run.font.color.rgb = STATUS_COLOR["red" if a["severity"] == "high" else "amber"]
            severity_run.bold = True
        row.cells[3].text = a["reason"]


def render_docx(
    report: dict,
    narrative: dict,
    chart_paths: dict,
    trend_status: str,
    anomaly_status: str,
    overall_status: str,
) -> Document:
    doc = Document()

    title = doc.add_heading(f"{report['disease']} in {report['country']}", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    subtitle = doc.add_paragraph()
    run = subtitle.add_run(f"{report['indicator_name']} · generated {report['generated_date']}")
    run.font.color.rgb = INK_MUTED
    run.font.size = Pt(10)

    doc.add_heading("Executive summary", level=1)
    _status_line(doc, overall_status)
    doc.add_paragraph(narrative["executive_summary"])
    _add_stats_table(doc, report["stats"])

    doc.add_heading("Trend", level=1)
    _status_line(doc, trend_status)
    doc.add_picture(str(chart_paths["line_chart"]), width=Inches(6))
    _caption(doc, narrative["trend_caption"])
    doc.add_paragraph(narrative["analyst"])

    doc.add_heading("Year-over-year change", level=1)
    _status_line(doc, anomaly_status)
    doc.add_picture(str(chart_paths["bar_chart"]), width=Inches(6))
    _caption(doc, narrative["change_caption"])

    doc.add_heading("Anomaly review", level=1)
    _status_line(doc, anomaly_status)
    doc.add_paragraph(narrative["anomaly_reviewer"])
    _add_anomaly_table(doc, report["anomalies"])

    doc.add_paragraph()
    footer = doc.add_paragraph()
    footer_run = footer.add_run(
        f"Source: WHO Global Health Observatory (indicator {report['indicator_code']}). "
        "This report is generated automatically from statistical analysis and is not medical advice."
    )
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = INK_MUTED

    return doc


def save_docx(
    report: dict,
    narrative: dict,
    chart_paths: dict,
    trend_status: str,
    anomaly_status: str,
    overall_status: str,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{report['indicator_code']}_{report['country']}_{report['generated_date']}"
    path = OUTPUT_DIR / f"{stem}.docx"
    doc = render_docx(report, narrative, chart_paths, trend_status, anomaly_status, overall_status)
    doc.save(str(path))
    return path
