# -*- coding: utf-8 -*-
"""Tests de round-trip et d'immutabilite du module ingest."""

from src.ingest import parse_docx


def test_parse_produces_all_original_texts(simple_cv_bytes):
    """Chaque ligne non vide du .docx d'origine se retrouve, verbatim, dans
    l'arbre Document (aucune perte, aucune alteration)."""
    doc = parse_docx(simple_cv_bytes, source_name="test.docx")
    all_texts = {b.text for b in doc.all_blocks()}

    expected = [
        "Jean Dupont",
        "jean.dupont@email.com | 06 12 34 56 78 | Paris",
        "Développeur backend avec 5 ans d'expérience en Python et SQL.",
        "Développement et maintenance d'une application de gestion des stocks.",
        "Optimisation des traitements Oracle PL/SQL (-65% de temps).",
        "Python, SQL, Docker, Anglais",
        "Ingénieur diplômé en génie informatique — 2019",
    ]
    for text in expected:
        assert text in all_texts, f"Texte original perdu : {text!r}"


def test_block_ids_are_stable_across_parses(simple_cv_bytes):
    """Reparser le meme document produit exactement les memes block_id."""
    doc1 = parse_docx(simple_cv_bytes, source_name="test.docx")
    doc2 = parse_docx(simple_cv_bytes, source_name="test.docx")
    assert doc1.block_ids() == doc2.block_ids()


def test_sections_detected_with_categories(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="test.docx")
    cats = {s.category for s in doc.sections}
    assert {"profil", "experience", "competences", "formation"} <= cats


def test_name_and_contact_extracted(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="test.docx")
    assert doc.name_block is not None
    assert doc.name_block.text == "Jean Dupont"
    assert any("jean.dupont@email.com" in b.text for b in doc.contact_blocks)


def test_bullets_attached_to_experience_entry(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="test.docx")
    exp = next(s for s in doc.sections if s.category == "experience")
    assert len(exp.entries) == 1
    assert len(exp.entries[0].bullets) == 2


def test_document_model_is_frozen(simple_cv_bytes):
    """Les modeles sont immuables (frozen) : toute tentative de mutation leve."""
    doc = parse_docx(simple_cv_bytes, source_name="test.docx")
    import pydantic

    try:
        doc.source_name = "hacked.docx"  # type: ignore[misc]
        assert False, "La mutation aurait du lever une exception (modele frozen)."
    except (pydantic.ValidationError, AttributeError, TypeError):
        pass
