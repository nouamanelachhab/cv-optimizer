"""Tests for the Aho-Corasick automaton (deterministic skill matching)."""

from __future__ import annotations

import pytest

from src.ontology import load_ontology
from src.ontology.automaton import build_automaton, find_skills


@pytest.fixture(scope="module")
def ontology():
    return load_ontology()


@pytest.fixture(scope="module")
def automaton(ontology):
    return build_automaton(ontology)


def test_exact_match_found(ontology, automaton):
    skills = find_skills("Développement Python et Docker.", automaton)
    ids = {s.id for s in skills}
    assert "python" in ids
    assert "docker" in ids


def test_multiword_alias_pl_sql_found(automaton):
    skills = find_skills("Oracle PL/SQL en production.", automaton)
    ids = {s.id for s in skills}
    assert "sql" in ids
    assert "oracle" in ids


def test_no_partial_word_match_inside_larger_word(automaton):
    # "C" must never match as a substring of "Confluence".
    skills = find_skills("Utilisation de Confluence au quotidien.", automaton)
    ids = {s.id for s in skills}
    assert "c" not in ids


def test_accented_and_miscased_variant_resolves_to_canonical_label(automaton):
    skills = find_skills("décathlon et infocentre.", automaton)
    ids = {s.id for s in skills}
    assert "infocentre" in ids
    infocentre = next(s for s in skills if s.id == "infocentre")
    assert infocentre.label == "Infocentre"


def test_no_false_positive_via_edit_distance():
    """Regression for D3: 'infocentre' must never be matched via distance to
    an unrelated word such as 'innocente' -- the automaton only does exact
    canonical-form matching, so there is no distance computation at all."""
    ontology = load_ontology()
    automaton = build_automaton(ontology)
    skills = find_skills("Elle est innocente de cette erreur.", automaton)
    ids = {s.id for s in skills}
    assert "infocentre" not in ids
