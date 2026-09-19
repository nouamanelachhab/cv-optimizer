# -*- coding: utf-8 -*-
"""PDF-specific implementations of the adversarial injection techniques.

All overlay techniques draw new, additional text objects on top of the
existing page content; nothing already on the page is removed, moved, or
resized, so the original visible rendering is preserved exactly. No new PDF
page is ever appended: the payload is always drawn into the existing last
page, extending the drawing area vertically (even past the visible/printable
region) if the payload is long, instead of creating extra pages.
"""

from __future__ import annotations

import io

import pymupdf as fitz

__all__ = ["inject", "extract_naive_text", "render_first_page_png", "page_count"]

_FONT = "helv"
_MARGIN = 36.0  # ~0.5 inch


def _wrap_lines(text: str, fontsize: float, max_width: float) -> list[str]:
    """Greedy word-wrap using real glyph metrics, preserving blank lines
    between paragraphs of the source text."""
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        if not words or para == "":
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = current + " " + word
            if fitz.get_text_length(candidate, fontname=_FONT, fontsize=fontsize) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_onpage(
    doc: "fitz.Document",
    payload: str,
    *,
    fontsize: float,
    color: tuple,
    render_mode: int = 0,
    oc: int = 0,
) -> None:
    """Draws payload on the CV's existing last page only. The drawing rect
    starts in the top margin band and, if the payload is too long to fit in
    one page's height, simply extends further down past the bottom of the
    page -- never onto a new page object. Because these techniques are all
    invisible/imperceptible by design, drawing past the visible area (or
    stacked underneath existing content) never alters what a human sees."""
    last_page = doc[-1]
    width, height = last_page.rect.width, last_page.rect.height
    max_width = width - 2 * _MARGIN

    lines = _wrap_lines(payload, fontsize, max_width)
    line_height = fontsize * 1.2
    # Generous rect: tall enough for any realistic job description without
    # ever needing a second page.
    needed_height = max(height - 2 * _MARGIN, len(lines) * line_height + 2 * _MARGIN)

    rect = fitz.Rect(_MARGIN, _MARGIN, width - _MARGIN, _MARGIN + needed_height)
    last_page.insert_textbox(
        rect,
        "\n".join(lines),
        fontname=_FONT,
        fontsize=fontsize,
        color=color,
        render_mode=render_mode,
        oc=oc,
    )


def _draw_offpage(doc: "fitz.Document", payload: str, *, fontsize: float) -> None:
    """Draws payload in a single block positioned entirely below the
    visible/printable area of the last page (outside its MediaBox)."""
    last_page = doc[-1]
    width, height = last_page.rect.width, last_page.rect.height
    max_width = width - 2 * _MARGIN

    lines = _wrap_lines(payload, fontsize, max_width)
    needed_height = max(1.0, len(lines) * fontsize * 1.2 + 2 * _MARGIN)

    rect = fitz.Rect(_MARGIN, height + 10, width - _MARGIN, height + 10 + needed_height)
    last_page.insert_textbox(
        rect,
        "\n".join(lines),
        fontname=_FONT,
        fontsize=fontsize,
        color=(0, 0, 0),
    )



def inject(cv_bytes: bytes, payload: str, technique_id: str) -> bytes:
    """Returns a new PDF (bytes) equal to ``cv_bytes`` plus ``payload``
    injected using ``technique_id``. Never mutates existing page content."""
    doc = fitz.open(stream=cv_bytes, filetype="pdf")

    if technique_id == "metadata":
        _inject_metadata(doc, payload)
    elif technique_id == "white_text":
        _draw_onpage(doc, payload, fontsize=6, color=(1, 1, 1))
    elif technique_id == "tiny_font":
        _draw_onpage(doc, payload, fontsize=0.4, color=(0, 0, 0))
    elif technique_id == "offpage":
        _draw_offpage(doc, payload, fontsize=8)
    elif technique_id == "transparent":
        # Invisible text render mode (Tr 3): the same mechanism used by
        # OCR-derived hidden text layers. Text is never painted.
        _draw_onpage(doc, payload, fontsize=6, color=(0, 0, 0), render_mode=3)
    elif technique_id == "hidden_layer":
        ocg_xref = doc.add_ocg("ATS-Test-Hidden-Layer", on=False)
        _draw_onpage(doc, payload, fontsize=6, color=(0, 0, 0), oc=ocg_xref)
    else:
        raise ValueError(f"Technique inconnue : {technique_id}")

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def _inject_metadata(doc: "fitz.Document", payload: str) -> None:
    meta = dict(doc.metadata or {})
    meta["keywords"] = ((meta.get("keywords") or "") + " " + payload).strip()
    meta["subject"] = ((meta.get("subject") or "") + " " + payload).strip()
    doc.set_metadata(meta)


def extract_naive_text(cv_bytes: bytes) -> str:
    """Reproduces what most naive ATS/PDF parsers extract: the full text
    layer of every page (PyMuPDF's ``get_text`` reads all text-show
    operators, regardless of color, render mode, position, or OCG on/off
    state). This is the reference used to compute how much injected content
    a typical text extractor would pick up."""
    doc = fitz.open(stream=cv_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def render_first_page_png(cv_bytes: bytes, *, zoom: float = 1.5) -> bytes:
    """Renders the first page to a PNG image, for a real visual preview of
    what a human would see (should look identical to the original CV)."""
    doc = fitz.open(stream=cv_bytes, filetype="pdf")
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
    finally:
        doc.close()


def page_count(cv_bytes: bytes) -> int:
    """Returns the number of pages in a PDF (used to assert that injection
    never adds or removes a page)."""
    doc = fitz.open(stream=cv_bytes, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()

