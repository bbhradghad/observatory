"""Two-agent CrewAI pipeline that turns python-computed stats/anomalies into
plain-English narrative text.

The agents never see raw CSV data and have no tools - they only read the
JSON handed to them through task context, and only write prose. All numbers
in that JSON were already computed by src/analysis (stats.py, anomalies.py).
"""

import json
from typing import Tuple

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


def _build_agents(llm) -> Tuple[Agent, Agent]:
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
    return analyst, anomaly_reviewer


def run_narrative(stats: dict, anomalies: list) -> dict:
    """Run the two-agent crew and return {'analyst': str, 'anomaly_reviewer': str}."""
    llm = build_llm()
    analyst, anomaly_reviewer = _build_agents(llm)

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

    crew = Crew(
        agents=[analyst, anomaly_reviewer],
        tasks=[analyst_task, anomaly_task],
        process=Process.sequential,
        memory=False,
        verbose=False,
    )

    inputs = {
        "stats_json": json.dumps(stats, indent=2),
        "anomalies_json": json.dumps(anomalies, indent=2),
    }
    result = crew.kickoff(inputs=inputs)
    analyst_text, anomaly_text = (t.raw for t in result.tasks_output)
    return {"analyst": analyst_text, "anomaly_reviewer": anomaly_text}
