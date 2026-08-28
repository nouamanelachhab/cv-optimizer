"""Parseability audit public API."""

from __future__ import annotations

from src.ingest.models import Document
from src.parseability.checks import (
    check_chronological_order,
    check_date_format_consistency,
    check_double_parser_diff,
    check_hyperlink_mismatch,
    check_multi_column_layout,
    check_out_of_flow_content,
    check_unrecognized_headings,
)
from src.parseability.models import ParseabilityIssue, ParseabilityReport, ParseabilitySeverity

__all__ = [
    "ParseabilityIssue",
    "ParseabilityReport",
    "ParseabilitySeverity",
    "run_parseability_audit",
]


def run_parseability_audit(doc: Document, docx_bytes: bytes | None = None) -> ParseabilityReport:
    """Run all parseability checks and return a combined report.

    ``docx_bytes`` is optional: checks that need raw XML access (multi-column
    layout, hyperlink mismatch, double-parser diff) are skipped if it is not
    provided.
    """
    issues: list[ParseabilityIssue] = []
    issues += check_out_of_flow_content(doc)
    issues += check_unrecognized_headings(doc)
    issues += check_date_format_consistency(doc)
    issues += check_chronological_order(doc)
    if docx_bytes is not None:
        issues += check_multi_column_layout(docx_bytes)
        issues += check_hyperlink_mismatch(docx_bytes)
        issues += check_double_parser_diff(docx_bytes)
    return ParseabilityReport(issues=issues)
