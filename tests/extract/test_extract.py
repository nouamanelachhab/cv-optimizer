"""Tests for the extract module."""

from __future__ import annotations

import pytest

from src.extract import extract_keywords, extract_skills
from src.ontology import load_ontology


@pytest.fixture(scope="module")
def ontology():
    return load_ontology()


def test_extract_finds_multiword_alias_pl_sql(ontology):
    text = "Développement Oracle PL/SQL (-65% de temps de traitement)."
    skills = extract_skills(text, ontology)
    ids = {s.skill_id for s in skills}
    assert "sql" in ids
    assert "oracle" in ids


def test_extract_finds_iso_27001(ontology):
    text = "Certification ISO 27001 obtenue en 2021."
    skills = extract_skills(text, ontology)
    ids = {s.skill_id for s in skills}
    assert "iso_27001" in ids


def test_extract_finds_spoken_language_category(ontology):
    text = "Anglais courant, Python avancé."
    skills = extract_skills(text, ontology)
    anglais = next(s for s in skills if s.skill_id == "anglais")
    assert anglais.category.value == "spoken_language"


def test_ambiguous_skill_excluded_when_alone(ontology):
    text = "Je suis né à Java, une île d'Indonésie."
    skills = extract_skills(text, ontology)
    ids = {s.skill_id for s in skills}
    assert "java" not in ids


def test_ambiguous_skill_included_with_technical_context(ontology):
    text = "Développement Java, Python et Docker sur des projets backend."
    skills = extract_skills(text, ontology)
    ids = {s.skill_id for s in skills}
    assert "java" in ids
    assert "python" in ids
    assert "docker" in ids


def test_extract_skills_no_duplicates(ontology):
    text = "Python Python Python, un langage Python."
    skills = extract_skills(text, ontology)
    ids = [s.skill_id for s in skills]
    assert ids.count("python") == 1


def test_extract_keywords_returns_nonempty_list_for_offer(offer_text_decathlon):
    keywords = extract_keywords(offer_text_decathlon, top_k=10)
    assert len(keywords) > 0
    assert all(isinstance(k, str) for k in keywords)
