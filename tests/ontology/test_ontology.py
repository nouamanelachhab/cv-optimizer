"""Tests for the ontology module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from src.ontology import build_alias_index, load_ontology
from src.ontology.models import SkillCategory, SkillType


def test_load_seed_ontology_succeeds():
    ontology = load_ontology()
    assert len(ontology.skills) > 0


def test_seed_ontology_contains_expected_skills():
    ontology = load_ontology()
    ids = {s.id for s in ontology.skills}
    assert {"python", "sql", "docker", "kubernetes", "oracle", "iso_27001", "anglais"} <= ids


def test_alias_index_resolves_accented_and_case_variants():
    ontology = load_ontology()
    index = build_alias_index(ontology)
    assert index["python"].id == "python"
    assert index["pl sql"].id == "sql"
    assert index["iso 27001"].id == "iso_27001"


def test_ambiguous_flag_set_on_java():
    ontology = load_ontology()
    java = next(s for s in ontology.skills if s.id == "java")
    assert java.ambiguous is True


def test_spoken_language_category_distinguished_from_programming():
    ontology = load_ontology()
    anglais = next(s for s in ontology.skills if s.id == "anglais")
    python = next(s for s in ontology.skills if s.id == "python")
    assert anglais.category == SkillCategory.SPOKEN_LANGUAGE
    assert python.category == SkillCategory.PROGRAMMING_LANGUAGE


def test_skill_type_distinguishes_hard_soft_language():
    ontology = load_ontology()
    python = next(s for s in ontology.skills if s.id == "python")
    anglais = next(s for s in ontology.skills if s.id == "anglais")
    organisation = next(s for s in ontology.skills if s.id == "organisation")
    assert python.type == SkillType.HARD_SKILL
    assert anglais.type == SkillType.LANGUAGE
    assert organisation.type == SkillType.SOFT_SKILL


def test_esco_uri_present_for_esco_backed_skills():
    ontology = load_ontology()
    python = next(s for s in ontology.skills if s.id == "python")
    docker = next(s for s in ontology.skills if s.id == "docker")
    assert python.esco_uri is not None
    assert docker.esco_uri is None  # IT-specific tool, not in ESCO per addendum


def test_invalid_ontology_data_fails_schema_validation(tmp_path):
    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text(
        "- id: broken\n  label: Broken\n  category: not_a_real_category\n  aliases: [broken]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_ontology(bad_path)


def test_ontology_models_are_frozen():
    ontology = load_ontology()
    with pytest.raises(Exception):
        ontology.skills[0].label = "changed"
