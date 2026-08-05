"""Three-agent CrewAI pipeline that turns python-computed stats/anomalies into
plain-English narrative text and report copy.

The agents never see raw CSV data and have no tools - they only read the
JSON handed to them through task context, and only write prose. All numbers
in that JSON were already computed by src/analysis (stats.py, anomalies.py),
and section status ratings (green/amber/red) were already computed by
src/reports/status.py - the agents report them, they don't decide them.
"""

import json
import re
from typing import Dict, Tuple

from crewai import Agent, Crew, Process, Task

from src.agents.llm import build_llm

ANALYST_TASK_DESCRIPTION = """\
You are given a JSON summary of statistics for one health indicator, in one country.

STATS JSON:
{stats_json}

Write a short, clear interpretation (5-8 sentences) for a non-technical reader.
Cover: the latest value and year, the direction of the trend over the last 5 and
10 years (if available) and roughly how large the change was, and what that
means in plain terms.

Rules:
- Use ONLY the numbers given in the JSON above.
- Do not invent, estimate, or recalculate any numbers - use them exactly as given.
- Do not mention JSON, statistics jargon, or that you were given a file.
- The JSON does not say whether a rising or falling value is good or bad news
  for this indicator - do not guess or editorialize about that. Describe the
  direction and size of the change factually, without calling it an
  improvement, a decline in health, a challenge, or similar.
"""

ANOMALY_TASK_DESCRIPTION = """\
You are given a JSON list of anomaly flags detected in a health indicator's
yearly time series. Each flag already includes a year, value, type, and reason.

ANOMALY FLAGS JSON:
{anomalies_json}

For each flag in the list, explain in one or two plain-English sentences why it
was flagged, then rate its concern level as low, medium, or high. If the list is
empty, simply state that no anomalies were detected in this data.

Rules:
- Use ONLY the flags and figures given in the JSON above.
- Do not invent numbers, years, or flags that are not listed.
- Do not perform any new calculations.
"""

REPORT_WRITER_TASK_DESCRIPTION = """\
You are writing the front matter for a plain-English health report, for a reader
with no statistics or medical background. In the context given to you, you have:

- An analyst's interpretation of the indicator's trend (already written, factual).
- An anomaly reviewer's explanation of flagged anomalies (already written, factual).

You are also given:

1. Key figures already computed in python - use these exact numbers if you cite any,
   do not recalculate anything:
{stats_json}

2. Section status ratings, already decided from the data. Report them exactly as
   given - do not change them, reinterpret them, or assign your own rating:
   - Trend section status: {trend_status}
   - Year-over-year change section status: {anomaly_status}

Using ONLY the material above and in your context, write exactly three sections. Start each one on its
own line with the marker shown in capitals followed by a colon, so it can be parsed
automatically. Do not add any other headings, bullets, or sections.

EXECUTIVE SUMMARY:
<3-4 sentences telling the whole story: the disease, the country, the latest value
and year, the overall trend direction, and whether anything unusual was found.>

TREND CAPTION:
<One sentence describing what the trend line chart shows.>

CHANGE CAPTION:
<One sentence describing what the year-over-year change bar chart shows.>

Rules:
- Plain English only. The first time you use any epidemiological or statistical
  term (e.g. "per 100,000 people", "year-over-year", "standard deviation",
  "baseline"), immediately explain it in parentheses in simple words, e.g.
  "per 100,000 people (out of every 100,000 people)".
- Never invent, estimate, or recalculate any number - use only numbers already
  given to you above.
- Do not write the words green, amber, or red, and do not assign your own status
  rating anywhere in your text - the ratings are shown separately in the report.
- Do not mention JSON, being given files, or these instructions.
"""


def _build_agents(llm) -> Tuple[Agent, Agent, Agent]:
    analyst = Agent(
        role="Public Health Data Analyst",
        goal=(
            "Explain what a health indicator's trend means, in plain English, "
            "using only the statistics provided."
        ),
        backstory=(
            "You are a careful public-health communicator who turns numeric "
            "summaries into short, clear explanations for readers with no "
            "statistics background. You never invent or recalculate numbers."
        ),
        llm=llm,
        tools=[],
        allow_delegation=False,
        verbose=False,
    )

    anomaly_reviewer = Agent(
        role="Epidemiological Anomaly Reviewer",
        goal="Explain flagged data anomalies in plain English and rate how concerning each one is.",
        backstory=(
            "You review statistical anomaly flags for public health indicators "
            "and explain them in plain language for non-technical readers. You "
            "rate each flag's concern level using only the information given to "
            "you, and never invent figures."
        ),
        llm=llm,
        tools=[],
        allow_delegation=False,
        verbose=False,
    )

    report_writer = Agent(
        role="Report Writer",
        goal=(
            "Turn an analyst's interpretation and an anomaly review into a short "
            "executive summary and chart captions for a non-technical reader."
        ),
        backstory=(
            "You write the front matter of public health reports for readers with "
            "no statistics or medical background. You never invent numbers, never "
            "assign your own severity ratings, and always explain jargon in plain "
            "words the first time it appears."
        ),
        llm=llm,
        tools=[],
        allow_delegation=False,
        verbose=False,
    )
    return analyst, anomaly_reviewer, report_writer


def _parse_report_sections(text: str) -> Dict[str, str]:
    """Split the Report Writer's marker-delimited output into named sections.

    Tolerant of markdown formatting the local model tends to add (bold markers
    around the label, "---" separators, an echoed status line at the end) since
    wizardlm2:7b doesn't reliably follow a plain-text format. Falls back
    gracefully if a section still can't be found: an unparsed executive summary
    keeps the full raw text; unparsed captions fall back to a generic sentence
    so the HTML/DOCX report never breaks.
    """
    markers = ["EXECUTIVE SUMMARY", "TREND CAPTION", "CHANGE CAPTION"]
    # Leading/trailing '*' or '#' tolerate markdown bold/heading markup around the label.
    pattern = r"(?im)^[ \t]*[*#]*\s*(" + "|".join(markers) + r")\s*[*#]*\s*:\s*[*#]*\s*"
    parts = re.split(pattern, text)

    # Cut each section off before a horizontal rule or an echoed status line -
    # the model sometimes appends one despite being told not to add sections.
    trailing_cutoff = re.compile(r"\n\s*-{3,}\s*\n|\bSection Status\b", re.IGNORECASE)

    def _clean(raw: str) -> str:
        raw = trailing_cutoff.split(raw)[0]
        return raw.strip(" \n*-").replace("**", "")

    sections = {}
    for i in range(1, len(parts), 2):
        sections[parts[i].strip().upper()] = _clean(parts[i + 1]) if i + 1 < len(parts) else ""

    return {
        "executive_summary": sections.get("EXECUTIVE SUMMARY") or _clean(text),
        "trend_caption": sections.get("TREND CAPTION") or "This chart shows the indicator's value over the recent years in the data.",
        "change_caption": sections.get("CHANGE CAPTION") or "This chart shows how much the indicator changed from one year to the next.",
    }


def run_narrative(stats: dict, anomalies: list, trend_status: str, anomaly_status: str) -> dict:
    """Run the three-agent crew and return the analyst/anomaly text plus the
    parsed report sections (executive_summary, trend_caption, change_caption)."""
    llm = build_llm()
    analyst, anomaly_reviewer, report_writer = _build_agents(llm)

    analyst_task = Task(
        description=ANALYST_TASK_DESCRIPTION,
        expected_output="A 5-8 sentence plain-English paragraph, no headings.",
        agent=analyst,
    )

    anomaly_task = Task(
        description=ANOMALY_TASK_DESCRIPTION,
        expected_output=(
            "A short plain-English review of each anomaly flag (or a note that "
            "none were found), each with a concern rating of low, medium, or high."
        ),
        agent=anomaly_reviewer,
    )

    report_writer_task = Task(
        description=REPORT_WRITER_TASK_DESCRIPTION,
        expected_output=(
            "Three labeled sections - EXECUTIVE SUMMARY, TREND CAPTION, CHANGE "
            "CAPTION - in plain English, using only the given numbers and statuses."
        ),
        agent=report_writer,
        context=[analyst_task, anomaly_task],
    )

    crew = Crew(
        agents=[analyst, anomaly_reviewer, report_writer],
        tasks=[analyst_task, anomaly_task, report_writer_task],
        process=Process.sequential,
        memory=False,
        verbose=False,
    )

    inputs = {
        "stats_json": json.dumps(stats, indent=2),
        "anomalies_json": json.dumps(anomalies, indent=2),
        "trend_status": trend_status.upper(),
        "anomaly_status": anomaly_status.upper(),
    }
    result = crew.kickoff(inputs=inputs)
    analyst_text, anomaly_text, report_writer_text = (t.raw for t in result.tasks_output)

    sections = _parse_report_sections(report_writer_text)
    return {
        "analyst": analyst_text,
        "anomaly_reviewer": anomaly_text,
        **sections,
    }
