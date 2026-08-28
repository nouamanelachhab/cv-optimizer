"""Golden corpus: 3 synthetic CV/offer pairs with fixed, versioned expected
match outcomes. Any change to extract/match logic that alters these results
must be a deliberate, reviewed decision -- these assertions are the
reference snapshot.
"""

from __future__ import annotations

import pytest

from src.extract import extract_skills
from src.ingest import parse_docx
from src.match import match
from src.ontology import load_ontology
from tests.conftest import _make_docx


@pytest.fixture(scope="module")
def ontology():
    return load_ontology()


_CASES = [
    {
        "name": "decathlon_backend",
        "cv_paragraphs": [
            ("Marie Curie", None),
            ("EXPERIENCE", "Heading 1"),
            ("Développement Python, SQL et Docker chez Decathlon.", None),
            ("COMPETENCES", "Heading 1"),
            ("Python, SQL, Docker, Anglais", None),
        ],
        "offer_text": "Recherche développeur Python, Docker, Kubernetes. Anglais requis.",
        "expected_matched": {"python", "docker", "anglais"},
        "expected_missing": {"kubernetes"},
        "expected_extra": {"sql"},
    },
    {
        "name": "oracle_dba",
        "cv_paragraphs": [
            ("Paul Martin", None),
            ("EXPERIENCE", "Heading 1"),
            ("Administration Oracle et PL/SQL, certification ISO 27001.", None),
        ],
        "offer_text": "Poste DBA Oracle, PL/SQL, ISO 27001 exigés.",
        "expected_matched": {"oracle", "sql", "iso_27001"},
        "expected_missing": set(),
        "expected_extra": set(),
    },
    {
        "name": "missing_everything",
        "cv_paragraphs": [
            ("Alex Dupuis", None),
            ("EXPERIENCE", "Heading 1"),
            ("Gestion administrative et accueil client.", None),
        ],
        "offer_text": "Recherche développeur Kubernetes et Docker.",
        "expected_matched": set(),
        "expected_missing": {"kubernetes", "docker"},
        "expected_extra": set(),
    },
]


@pytest.mark.parametrize("case", _CASES, ids=[c["name"] for c in _CASES])
def test_golden_case_produces_expected_match(case, ontology):
    docx_bytes = _make_docx(case["cv_paragraphs"])
    doc = parse_docx(docx_bytes, source_name=f"{case['name']}.docx")
    cv_text = "\n".join(b.text for b in doc.all_blocks())

    cv_skills = extract_skills(cv_text, ontology)
    offer_skills = extract_skills(case["offer_text"], ontology)

    result = match(
        {s.skill_id for s in cv_skills},
        {s.skill_id for s in offer_skills},
        cv_keywords=[],
        offer_keywords=[],
        ontology=ontology,
    )

    assert {m.skill_id for m in result.matched} == case["expected_matched"]
    assert {m.skill_id for m in result.missing} == case["expected_missing"]
    assert {m.skill_id for m in result.extra} == case["expected_extra"]
