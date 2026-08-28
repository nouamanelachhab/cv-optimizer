"""Tests for the match module."""

from __future__ import annotations

from src.match import match
from src.ontology import load_ontology


def _ontology():
    return load_ontology()


def test_exact_match_pass_finds_common_skills():
    ontology = _ontology()
    result = match(
        cv_skill_ids={"python", "sql", "docker"},
        offer_skill_ids={"python", "docker", "kubernetes"},
        cv_keywords=[],
        offer_keywords=[],
        ontology=ontology,
    )
    matched_ids = {m.skill_id for m in result.matched}
    missing_ids = {m.skill_id for m in result.missing}
    extra_ids = {m.skill_id for m in result.extra}
    assert matched_ids == {"python", "docker"}
    assert missing_ids == {"kubernetes"}
    assert extra_ids == {"sql"}


def test_alias_pass_resolves_offer_keyword_missed_by_extract():
    ontology = _ontology()
    result = match(
        cv_skill_ids={"sql"},
        offer_skill_ids=set(),
        cv_keywords=[],
        offer_keywords=["pl/sql"],
        ontology=ontology,
    )
    matched_ids = {m.skill_id for m in result.matched}
    assert "sql" in matched_ids


def test_fuzzy_pass_only_produces_review_candidates_not_matches():
    ontology = _ontology()
    result = match(
        cv_skill_ids=set(),
        offer_skill_ids=set(),
        cv_keywords=["gestion de projet agile"],
        offer_keywords=["gestion de projets agiles"],
        ontology=ontology,
    )
    assert result.matched == []
    assert result.missing == []
    assert result.extra == []
    assert any(c.offer_term == "gestion de projets agiles" for c in result.fuzzy_candidates)


def test_fuzzy_pass_ignores_short_terms():
    ontology = _ontology()
    result = match(
        cv_skill_ids=set(),
        offer_skill_ids=set(),
        cv_keywords=["ab"],
        offer_keywords=["ba"],
        ontology=ontology,
    )
    assert result.fuzzy_candidates == []


def test_match_labels_are_populated_from_ontology():
    ontology = _ontology()
    result = match(
        cv_skill_ids=set(),
        offer_skill_ids={"kubernetes"},
        cv_keywords=[],
        offer_keywords=[],
        ontology=ontology,
    )
    assert result.missing[0].label == "Kubernetes"
