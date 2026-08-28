"""Tests for the report module."""

from __future__ import annotations

import json

from src.match.models import MatchResult, MatchStatus, SkillMatch
from src.parseability.models import ParseabilityIssue, ParseabilityReport, ParseabilitySeverity
from src.report import build_report, to_html, to_json
from src.score import compute_score


def _sample_match_result() -> MatchResult:
    return MatchResult(
        matched=[SkillMatch(skill_id="python", label="Python", status=MatchStatus.MATCHED)],
        missing=[SkillMatch(skill_id="docker", label="Docker", status=MatchStatus.MISSING)],
        extra=[SkillMatch(skill_id="sql", label="SQL", status=MatchStatus.EXTRA)],
    )


def _sample_parseability_report() -> ParseabilityReport:
    return ParseabilityReport(
        issues=[
            ParseabilityIssue(
                code="unrecognized_heading",
                severity=ParseabilitySeverity.WARNING,
                message="En-tête non reconnu : 'DIVERS'",
            )
        ]
    )


def test_build_report_and_to_json_roundtrip():
    match_result = _sample_match_result()
    score = compute_score(match_result)
    report = build_report(score, match_result, _sample_parseability_report(), candidate_name="Jean Dupont")

    json_str = to_json(report)
    data = json.loads(json_str)
    assert data["candidate_name"] == "Jean Dupont"
    assert data["match"]["matched"][0]["label"] == "Python"
    assert data["parseability"]["issues"][0]["code"] == "unrecognized_heading"


def test_to_html_contains_expected_content():
    match_result = _sample_match_result()
    score = compute_score(match_result)
    report = build_report(score, match_result, _sample_parseability_report(), candidate_name="Jean Dupont")

    html = to_html(report)
    assert "Python" in html
    assert "Docker" in html
    assert "SQL" in html
    assert "En-tête non reconnu" in html


def test_to_html_escapes_untrusted_candidate_name():
    match_result = _sample_match_result()
    score = compute_score(match_result)
    report = build_report(
        score, match_result, _sample_parseability_report(), candidate_name="<script>alert(1)</script>"
    )
    html = to_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_report_never_modifies_match_or_score_inputs():
    match_result = _sample_match_result()
    score = compute_score(match_result)
    original_matched_len = len(match_result.matched)
    build_report(score, match_result, _sample_parseability_report())
    assert len(match_result.matched) == original_matched_len
