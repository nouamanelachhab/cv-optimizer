"""Report: combine score/match/parseability(/guard) into a JSON or HTML report.

Never writes to the CV document itself -- this module only produces
human-facing output. All recommendations here are for the *user* to act on
manually; nothing here mutates any block text.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.guard.models import GuardReport
from src.match.models import MatchResult
from src.parseability.models import ParseabilityReport
from src.report.models import Report
from src.score.models import Score

__all__ = ["Report", "build_report", "to_json", "to_html"]

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def build_report(
    score: Score,
    match_result: MatchResult,
    parseability_report: ParseabilityReport,
    guard_report: GuardReport | None = None,
    candidate_name: str | None = None,
) -> Report:
    return Report(
        candidate_name=candidate_name,
        score=score,
        match=match_result,
        parseability=parseability_report,
        guard=guard_report,
    )


def to_json(report: Report) -> str:
    return report.model_dump_json(indent=2)


def to_html(report: Report) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "jinja2"]),
    )
    template = env.get_template("report.html.jinja2")
    return template.render(report=report)
