# -*- coding: utf-8 -*-
"""Orchestrates adversarial CV generation.

Regardless of the uploaded CV's original format, the output is always a
single PDF that looks pixel-identical to the original: DOCX inputs are
first converted to PDF (preserving layout), then the chosen technique
hides the job description inside the *existing* page(s) of that PDF --
no page is ever added or removed. This module also computes the stats
needed by the UI (characters/words injected, what a naive extractor would
still see, reliability notes, preview) and builds the download filename
from the company name and job title.
"""

from __future__ import annotations

import re

from src.redteam import docx_to_pdf, pdf_injector
from src.redteam.models import GenerationResult
from src.redteam.techniques import get_technique

__all__ = ["generate", "detect_format", "SUPPORTED_FORMATS"]

SUPPORTED_FORMATS = {"docx", "pdf"}


def detect_format(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".docx"):
        return "docx"
    if lower.endswith(".pdf"):
        return "pdf"
    raise ValueError(
        "Format de fichier non supporté : seuls .docx et .pdf sont acceptés."
    )


def _stem(filename: str) -> str:
    for ext in (".docx", ".pdf"):
        if filename.lower().endswith(ext):
            return filename[: -len(ext)]
    return filename


def _slugify(value: str, *, fallback: str) -> str:
    """Sanitizes free text for safe use inside a filename."""
    value = value.strip()
    if not value:
        return fallback
    value = re.sub(r"[^\w\-\s]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value.strip())
    return value[:60] or fallback


def generate(
    cv_bytes: bytes,
    original_filename: str,
    job_description: str,
    technique_id: str,
    company_name: str,
    offer_title: str,
) -> GenerationResult:
    """Injects ``job_description`` into a copy of ``cv_bytes`` using
    ``technique_id`` and returns the generated PDF plus diagnostics.

    The original CV's visible design is never altered and no page is ever
    added: if the CV is a DOCX, it is first converted to PDF (same layout),
    then the payload is hidden inside the existing last page of that PDF.
    """
    file_format = detect_format(original_filename)
    technique = get_technique(technique_id)

    if file_format == "docx":
        pdf_bytes = docx_to_pdf.convert_docx_to_pdf(cv_bytes)
    else:
        pdf_bytes = cv_bytes

    baseline_text = pdf_injector.extract_naive_text(pdf_bytes)
    page_count_before = pdf_injector.page_count(pdf_bytes)

    output_bytes = pdf_injector.inject(pdf_bytes, job_description, technique_id)

    naive_after = pdf_injector.extract_naive_text(output_bytes)
    page_count_after = pdf_injector.page_count(output_bytes)
    naive_injected_chars = max(0, len(naive_after) - len(baseline_text))

    try:
        preview_png = pdf_injector.render_first_page_png(output_bytes)
    except Exception:
        preview_png = None

    company_slug = _slugify(company_name, fallback="Entreprise")
    offer_slug = _slugify(offer_title, fallback="Offre")
    filename = f"{_stem(original_filename)}_{technique_id}_{company_slug}_{offer_slug}.pdf"

    return GenerationResult(
        output_bytes=output_bytes,
        filename=filename,
        technique_id=technique.id,
        technique_label=technique.label,
        reliability=technique.reliability,
        reliability_note=technique.note,
        injected_chars=len(job_description),
        injected_words=len(job_description.split()),
        naive_extract_injected_chars=naive_injected_chars,
        page_count_before=page_count_before,
        page_count_after=page_count_after,
        preview_png=preview_png,
    )

