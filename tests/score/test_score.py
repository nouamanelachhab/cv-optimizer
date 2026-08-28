"""Tests for the score module."""

from __future__ import annotations

from src.match.models import MatchResult, MatchStatus, SkillMatch
from src.score import compute_score


def test_coverage_and_precision_computed_correctly():
    match_result = MatchResult(
        matched=[
            SkillMatch(skill_id="python", label="Python", status=MatchStatus.MATCHED),
            SkillMatch(skill_id="docker", label="Docker", status=MatchStatus.MATCHED),
        ],
        missing=[
            SkillMatch(skill_id="kubernetes", label="Kubernetes", status=MatchStatus.MISSING)
        ],
        extra=[SkillMatch(skill_id="sql", label="SQL", status=MatchStatus.EXTRA)],
    )
    score = compute_score(match_result)
    coverage = next(s for s in score.sub_scores if s.name == "coverage")
    precision = next(s for s in score.sub_scores if s.name == "precision")

    assert round(coverage.value, 2) == round(100 * 2 / 3, 2)
    assert round(precision.value, 2) == round(100 * 2 / 3, 2)
    assert "Kubernetes" in coverage.explanation
    assert "Python" in coverage.explanation


def test_total_is_weighted_average():
    match_result = MatchResult(
        matched=[SkillMatch(skill_id="python", label="Python", status=MatchStatus.MATCHED)],
        missing=[],
        extra=[],
    )
    score = compute_score(match_result)
    assert score.total == 100.0


def test_no_required_skills_yields_full_coverage():
    match_result = MatchResult(matched=[], missing=[], extra=[])
    score = compute_score(match_result)
    coverage = next(s for s in score.sub_scores if s.name == "coverage")
    assert coverage.value == 100.0


def test_explain_returns_readable_strings():
    match_result = MatchResult(
        matched=[SkillMatch(skill_id="python", label="Python", status=MatchStatus.MATCHED)],
        missing=[SkillMatch(skill_id="sql", label="SQL", status=MatchStatus.MISSING)],
        extra=[],
    )
    score = compute_score(match_result)
    lines = score.explain()
    assert len(lines) == 2
    assert all("poids" in line for line in lines)
