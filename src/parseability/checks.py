"""Parseability: audit for structural traits that harm ATS readability.

Never modifies the document -- these are diagnostic-only findings meant to
feed the ``report`` module (manual-review recommendations to the user).

Document-based checks (operate on the already-ingested ``Document`` tree):
  - out-of-flow content (headers/footers/text boxes/content controls)
  - unrecognized section headings
  - inconsistent date formats across experience entries
  - non-chronological (not most-recent-first) experience ordering

Raw-docx-based checks (need direct XML access, not exposed by the ingest
tree):
  - multi-column section layout
  - hyperlink visible text / target URL mismatch

Double-parser method (the addendum's core parseability diagnostic):
  - ``check_double_parser_diff`` compares what a naive parser sees
    (``python-docx``, reading only the main document body -- a good stand-in
    for how many real ATS parsers behave) against what a thorough parser
    sees (``docx2python``, which also reads headers/footers/text boxes/
    tables). Anything present in the thorough parse but absent from the
    naive parse is content an ATS is likely to silently drop.
"""

from __future__ import annotations

import io
import re
import zipfile

from docx import Document as DocxDocument
from docx2python import docx2python
from lxml import etree

from src.ingest.models import Document
from src.parseability.models import ParseabilityIssue, ParseabilitySeverity

__all__ = [
    "check_out_of_flow_content",
    "check_unrecognized_headings",
    "check_date_format_consistency",
    "check_chronological_order",
    "check_multi_column_layout",
    "check_hyperlink_mismatch",
    "check_double_parser_diff",
]

_NSMAP = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

_DATE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("MM/AAAA", re.compile(r"\b\d{1,2}/\d{4}\b")),
    (
        "mois texte AAAA",
        re.compile(
            r"\b(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|"
            r"septembre|octobre|novembre|d[ée]cembre)\s+\d{4}\b",
            re.IGNORECASE,
        ),
    ),
    ("AAAA-MM", re.compile(r"\b\d{4}-\d{2}\b")),
]

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def check_out_of_flow_content(doc: Document) -> list[ParseabilityIssue]:
    if not doc.out_of_flow_blocks:
        return []
    return [
        ParseabilityIssue(
            code="out_of_flow_content",
            severity=ParseabilitySeverity.WARNING,
            message=(
                f"{len(doc.out_of_flow_blocks)} bloc(s) de contenu hors flux principal "
                "détecté(s) (en-tête, pied de page ou zone de texte) : ce contenu risque "
                "de ne pas être lu par certains ATS."
            ),
        )
    ]


def check_unrecognized_headings(doc: Document) -> list[ParseabilityIssue]:
    issues = []
    for section in doc.sections:
        if section.category == "autre":
            issues.append(
                ParseabilityIssue(
                    code="unrecognized_heading",
                    severity=ParseabilitySeverity.WARNING,
                    message=(
                        f"En-tête de section non reconnu : {section.heading_text!r}. "
                        "Utilisez un intitulé standard (Expérience, Formation, "
                        "Compétences...) pour une meilleure lecture par les ATS."
                    ),
                )
            )
    return issues


def _find_date_formats(text: str) -> set[str]:
    return {name for name, pattern in _DATE_PATTERNS if pattern.search(text)}


def check_date_format_consistency(doc: Document) -> list[ParseabilityIssue]:
    formats_found: set[str] = set()
    for section in doc.sections:
        for entry in section.entries:
            formats_found |= _find_date_formats(entry.text)
            for bullet in entry.bullets:
                formats_found |= _find_date_formats(bullet.text)

    if len(formats_found) > 1:
        return [
            ParseabilityIssue(
                code="inconsistent_date_format",
                severity=ParseabilitySeverity.WARNING,
                message=(
                    "Plusieurs formats de date différents utilisés dans le document : "
                    f"{', '.join(sorted(formats_found))}. Uniformisez le format."
                ),
            )
        ]
    return []


def check_chronological_order(doc: Document) -> list[ParseabilityIssue]:
    issues = []
    for section in doc.sections:
        if section.category != "experience":
            continue
        years: list[int] = []
        for entry in section.entries:
            match = _YEAR_PATTERN.search(entry.text)
            if match:
                years.append(int(match.group(0)))
        if len(years) >= 2 and years != sorted(years, reverse=True):
            issues.append(
                ParseabilityIssue(
                    code="non_chronological_order",
                    severity=ParseabilitySeverity.WARNING,
                    message=(
                        "Les expériences ne semblent pas classées de la plus récente "
                        f"à la plus ancienne (années détectées dans l'ordre : {years})."
                    ),
                )
            )
    return issues


def check_multi_column_layout(docx_bytes: bytes) -> list[ParseabilityIssue]:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        if "word/document.xml" not in zf.namelist():
            return []
        xml_bytes = zf.read("word/document.xml")
    root = etree.fromstring(xml_bytes)
    for cols in root.iter(f"{{{_NSMAP['w']}}}cols"):
        num_attr = cols.get(f"{{{_NSMAP['w']}}}num")
        if num_attr and num_attr.isdigit() and int(num_attr) > 1:
            return [
                ParseabilityIssue(
                    code="multi_column_layout",
                    severity=ParseabilitySeverity.WARNING,
                    message=(
                        f"Mise en page multi-colonnes détectée ({num_attr} colonnes) : "
                        "de nombreux ATS lisent le texte colonne par colonne, ce qui peut "
                        "mélanger l'ordre de lecture."
                    ),
                )
            ]
    return []


def check_hyperlink_mismatch(docx_bytes: bytes) -> list[ParseabilityIssue]:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        names = zf.namelist()
        if "word/document.xml" not in names:
            return []
        document_xml = zf.read("word/document.xml")
        rels_xml = (
            zf.read("word/_rels/document.xml.rels")
            if "word/_rels/document.xml.rels" in names
            else None
        )

    targets_by_id: dict[str, str] = {}
    if rels_xml is not None:
        rels_root = etree.fromstring(rels_xml)
        for rel in rels_root:
            rel_id = rel.get("Id")
            target = rel.get("Target")
            if rel_id and target:
                targets_by_id[rel_id] = target

    doc_root = etree.fromstring(document_xml)
    issues = []
    for link in doc_root.iter(f"{{{_NSMAP['w']}}}hyperlink"):
        rel_id = link.get(f"{{{_NSMAP['r']}}}id")
        if not rel_id or rel_id not in targets_by_id:
            continue
        target = targets_by_id[rel_id]
        visible_text = "".join(
            node.text or "" for node in link.iter(f"{{{_NSMAP['w']}}}t")
        ).strip()
        if not visible_text.lower().startswith(("http", "www")):
            continue
        normalized_text = re.sub(r"^https?://|^www\.", "", visible_text.lower()).rstrip("/")
        normalized_target = re.sub(r"^https?://|^www\.", "", target.lower()).rstrip("/")
        if normalized_text not in normalized_target and normalized_target not in normalized_text:
            issues.append(
                ParseabilityIssue(
                    code="hyperlink_mismatch",
                    severity=ParseabilitySeverity.WARNING,
                    message=(
                        f"Le texte du lien affiché ({visible_text!r}) ne correspond pas "
                        f"à sa cible réelle ({target!r})."
                    ),
                )
            )
    return issues


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_CRITICAL_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"(?:\+?\d[\d .-]{7,}\d)"),
}


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text)}


def check_double_parser_diff(docx_bytes: bytes) -> list[ParseabilityIssue]:
    """Double-parser method: diff a naive parse against a thorough one.

    ``python-docx`` reading only ``document.paragraphs`` stands in for a
    naive ATS parser (it silently skips headers/footers/text boxes/tables).
    ``docx2python`` reads the whole package. Any token present in the
    thorough parse but missing from the naive one is content an ATS is
    likely to never see. If that lost content contains an email address or
    phone number, this is escalated from a warning to a critical signal.
    """
    naive_document = DocxDocument(io.BytesIO(docx_bytes))
    naive_text = "\n".join(p.text for p in naive_document.paragraphs)

    with docx2python(io.BytesIO(docx_bytes)) as extraction:
        thorough_text = extraction.text

    lost_tokens = _tokens(thorough_text) - _tokens(naive_text)
    if not lost_tokens:
        return []

    lost_sample = ", ".join(sorted(lost_tokens)[:15])
    issues = [
        ParseabilityIssue(
            code="double_parser_content_loss",
            severity=ParseabilitySeverity.WARNING,
            message=(
                f"{len(lost_tokens)} terme(s) présent(s) dans le document mais invisibles "
                f"pour un lecteur qui ne lit que le corps principal (ex: {lost_sample})."
            ),
        )
    ]

    for kind, pattern in _CRITICAL_PATTERNS.items():
        if pattern.search(thorough_text) and not pattern.search(naive_text):
            label = "adresse e-mail" if kind == "email" else "numéro de téléphone"
            issues.append(
                ParseabilityIssue(
                    code="double_parser_critical_content_loss",
                    severity=ParseabilitySeverity.WARNING,
                    message=(
                        f"Une {label} n'apparaît que hors du corps principal du document "
                        "(en-tête, pied de page ou zone de texte) : un ATS risque de ne "
                        "jamais la lire."
                    ),
                )
            )

    return issues
