"""Tests for the docgen module (step 1: docxtpl-based identity regeneration).

Objective per the addendum: regenerating a CV from its own ingested model,
using the original block texts as context, must reproduce the same textual
content -- no optimization/enrichment logic is exercised here.
"""

from __future__ import annotations

import io

import pytest
from docx import Document as DocxDocument
from jinja2.exceptions import UndefinedError

from src.docgen import baseline_context, build_template, render, tag_name
from src.ingest import parse_docx


def _paragraph_texts(docx_bytes: bytes) -> list[str]:
    return [p.text for p in DocxDocument(io.BytesIO(docx_bytes)).paragraphs]


def test_identity_regeneration_reproduces_all_original_texts(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="cv.docx")

    template_bytes = build_template(doc)
    context = baseline_context(doc)
    output_bytes = render(template_bytes, context)

    output_texts = _paragraph_texts(output_bytes)
    original_texts = {block.text for block in doc.all_blocks()}

    for text in original_texts:
        assert text in output_texts


def test_tag_name_is_valid_jinja_identifier_even_for_digit_prefixed_ids():
    assert tag_name("123abc").isidentifier()
    assert tag_name("123abc") == "block_123abc"


def test_render_raises_on_missing_context_key_strict_undefined(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="cv.docx")
    template_bytes = build_template(doc)

    incomplete_context = {}  # nothing provided: every tag is undefined
    with pytest.raises(UndefinedError):
        render(template_bytes, incomplete_context)


def test_render_raises_when_one_block_missing_from_context(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="cv.docx")
    template_bytes = build_template(doc)

    context = baseline_context(doc)
    # Drop exactly one required tag to prove StrictUndefined catches partial gaps.
    dropped_key = next(iter(context))
    del context[dropped_key]

    with pytest.raises(UndefinedError):
        render(template_bytes, context)


def test_baseline_context_contains_a_tag_for_every_block(simple_cv_bytes):
    doc = parse_docx(simple_cv_bytes, source_name="cv.docx")
    context = baseline_context(doc)
    expected_keys = {tag_name(block.block_id) for block in doc.all_blocks()}
    assert set(context.keys()) == expected_keys
