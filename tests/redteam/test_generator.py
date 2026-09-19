# -*- coding: utf-8 -*-
"""Tests for the adversarial CV generator (ATS red-team tool).

The generator always outputs a PDF and never adds a page. DOCX inputs are
first converted to PDF (layout preserved) before injection, so DOCX-input
tests require a conversion backend (LibreOffice or Word) to be installed on
the machine running the tests; they are skipped automatically otherwise.
The PDF-input tests (the primary, dependency-free path) always run.
"""

from __future__ import annotations

import io

import pymupdf as fitz
import pytest
from docx import Document as DocxDocument

from src.redteam import generator
from src.redteam.docx_to_pdf import ConversionUnavailableError, _find_soffice
from src.redteam.techniques import TECHNIQUES

JOB_DESCRIPTION = (
    "Recherche Ingénieur Python Senior. Compétences requises : Python, "
    "Django, Kubernetes, Terraform, AWS, CI/CD, PostgreSQL, monitoring "
    "Prometheus/Grafana, tests automatisés, méthodologie Agile/Scrum."
)

COMPANY = "Acme Corp"
OFFER_TITLE = "Développeur Python Senior"

TECHNIQUE_IDS = [t.id for t in TECHNIQUES]

_DOCX_BACKEND_AVAILABLE = _find_soffice() is not None

requires_docx_backend = pytest.mark.skipif(
    not _DOCX_BACKEND_AVAILABLE,
    reason="Aucun moteur de conversion DOCX->PDF (LibreOffice/Word) disponible",
)


@pytest.fixture
def simple_docx_bytes() -> bytes:
    doc = DocxDocument()
    doc.add_paragraph("Jean Dupont")
    doc.add_paragraph("Développeur Python — 5 ans d'expérience.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def simple_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    page.insert_text((72, 100), "Jean Dupont", fontsize=14)
    page.insert_text((72, 130), "Developpeur Python - 5 ans d'experience.", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Output is always PDF, never gains a page, visible content preserved
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("technique_id", TECHNIQUE_IDS)
def test_pdf_injection_preserves_visible_rendering_and_page_count(simple_pdf_bytes, technique_id):
    result = generator.generate(
        simple_pdf_bytes, "cv.pdf", JOB_DESCRIPTION, technique_id, COMPANY, OFFER_TITLE
    )
    assert result.filename.endswith(".pdf")
    assert result.injected_chars == len(JOB_DESCRIPTION)
    assert result.preview_png is not None
    # No page ever added or removed.
    assert result.page_count_before == result.page_count_after == 1

    doc = fitz.open(stream=result.output_bytes, filetype="pdf")
    try:
        assert doc.page_count == 1
        first_page_text = doc[0].get_text()
    finally:
        doc.close()
    assert "Jean Dupont" in first_page_text


def test_filename_ends_with_company_and_offer(simple_pdf_bytes):
    result = generator.generate(
        simple_pdf_bytes, "cv.pdf", JOB_DESCRIPTION, "white_text", "Acme Corp", "Data Engineer"
    )
    stem = result.filename.rsplit(".", 1)[0]
    assert stem.endswith("Acme_Corp_Data_Engineer")
    assert result.filename.endswith(".pdf")


@pytest.mark.parametrize(
    "technique_id,should_appear_in_naive_extract",
    [
        ("white_text", True),
        ("tiny_font", True),
        # PyMuPDF's get_text() clips to the page's MediaBox, so text drawn
        # outside it is invisible to *this* naive extractor too -- a real,
        # useful finding: off-page hiding does not survive extractors that
        # clip to the page boundary (see techniques.py note).
        ("offpage", False),
        ("transparent", True),
        # PyMuPDF respects the OCG's default OFF state, just like a real PDF
        # viewer, so a standard get_text() call does not recover it either
        # (see techniques.py note: reliability depends on the ATS's PDF
        # library).
        ("hidden_layer", False),
        ("metadata", False),
    ],
)
def test_pdf_naive_extraction_signal_matches_technique_intent(
    simple_pdf_bytes, technique_id, should_appear_in_naive_extract
):
    from src.redteam import pdf_injector

    result = generator.generate(
        simple_pdf_bytes, "cv.pdf", JOB_DESCRIPTION, technique_id, COMPANY, OFFER_TITLE
    )
    extracted = pdf_injector.extract_naive_text(result.output_bytes)
    # Whitespace wrapping may reflow the payload across lines, so check a
    # stable substring rather than the exact original string.
    marker = "Kubernetes, Terraform, AWS"
    assert (marker in extracted.replace("\n", " ")) == should_appear_in_naive_extract


def test_multiple_successive_generations_are_independent(simple_pdf_bytes):
    """Simulates the UI workflow: edit job description / technique and
    generate again, several times in a row, from the same original CV."""
    descriptions = [
        JOB_DESCRIPTION,
        "Offre modifiée : recherche Data Scientist, SQL, Spark, MLOps.",
        "Autre offre : Ingénieur DevOps, Docker, Ansible, GCP.",
    ]
    for desc in descriptions:
        for technique_id in ("white_text", "metadata", "hidden_layer"):
            result = generator.generate(
                simple_pdf_bytes, "cv.pdf", desc, technique_id, COMPANY, OFFER_TITLE
            )
            assert result.injected_chars == len(desc)
            assert result.page_count_before == result.page_count_after


def test_long_description_never_adds_a_page(simple_pdf_bytes):
    """Even a very long job description must stay on the existing page."""
    long_description = JOB_DESCRIPTION * 20
    for technique_id in TECHNIQUE_IDS:
        result = generator.generate(
            simple_pdf_bytes, "cv.pdf", long_description, technique_id, COMPANY, OFFER_TITLE
        )
        assert result.page_count_after == result.page_count_before == 1


def test_unknown_technique_raises(simple_pdf_bytes):
    with pytest.raises(ValueError):
        generator.generate(
            simple_pdf_bytes, "cv.pdf", JOB_DESCRIPTION, "nope", COMPANY, OFFER_TITLE
        )


def test_unsupported_format_raises(simple_pdf_bytes):
    with pytest.raises(ValueError):
        generator.generate(
            simple_pdf_bytes, "cv.txt", JOB_DESCRIPTION, "white_text", COMPANY, OFFER_TITLE
        )


# --------------------------------------------------------------------------- #
# DOCX input: converted to PDF first, then goes through the same guarantees
# --------------------------------------------------------------------------- #
@requires_docx_backend
@pytest.mark.parametrize("technique_id", TECHNIQUE_IDS)
def test_docx_input_converts_and_preserves_visible_text(simple_docx_bytes, technique_id):
    result = generator.generate(
        simple_docx_bytes, "cv.docx", JOB_DESCRIPTION, technique_id, COMPANY, OFFER_TITLE
    )
    assert result.filename.endswith(".pdf")
    assert result.page_count_before == result.page_count_after

    doc = fitz.open(stream=result.output_bytes, filetype="pdf")
    try:
        full_text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    assert "Jean Dupont" in full_text


def test_docx_conversion_unavailable_raises_clear_error(simple_docx_bytes, monkeypatch):
    """When no conversion backend is present, the failure must be explicit
    (never a silently degraded/blank PDF)."""
    import src.redteam.docx_to_pdf as docx_to_pdf

    monkeypatch.setattr(docx_to_pdf, "_find_soffice", lambda: None)
    monkeypatch.setattr(
        docx_to_pdf,
        "_convert_with_docx2pdf",
        lambda *a, **k: (_ for _ in ()).throw(
            docx_to_pdf.ConversionUnavailableError("docx2pdf non installé")
        ),
    )
    with pytest.raises(ConversionUnavailableError):
        generator.generate(
            simple_docx_bytes, "cv.docx", JOB_DESCRIPTION, "white_text", COMPANY, OFFER_TITLE
        )
