"""Guard: blocking pre-write validation for the deterministic render pipeline.

Public API:
    run_guard(blocks) -> GuardReport
"""

from __future__ import annotations

from src.guard.checks import (
    check_g1_integrity,
    check_g2_orphaned_placeholders,
    check_g3_diacritic_ratio,
    check_g4_dictionary,
    check_g5_grammar,
    check_g6_keyword_density,
    check_g7_entity_casing,
    check_g8_typography,
    check_g9_fact_attribution,
)
from src.guard.models import GuardFinding, GuardReport, Operation, RenderedBlock, Severity

__all__ = [
    "GuardFinding",
    "GuardReport",
    "Operation",
    "RenderedBlock",
    "Severity",
    "run_guard",
]


def run_guard(
    blocks: list[RenderedBlock],
    dictionary_path=None,
    language_tool_client=None,
    skill_terms: list[str] | None = None,
    max_keyword_occurrences: int = 3,
    proper_nouns: list[str] | None = None,
    facts=None,
    skill_labels: list[str] | None = None,
) -> GuardReport:
    """Run all guard checks (G1-G9) and return a combined report.

    G4-G9 accept optional context; when omitted, each degrades to reporting
    no findings rather than failing (see ``checks.py`` docstrings).
    """
    findings: list[GuardFinding] = []
    findings += check_g1_integrity(blocks)
    findings += check_g2_orphaned_placeholders(blocks)
    findings += check_g3_diacritic_ratio(blocks)
    findings += check_g4_dictionary(blocks, dictionary_path=dictionary_path)
    findings += check_g5_grammar(blocks, language_tool_client=language_tool_client)
    findings += check_g6_keyword_density(
        blocks, skill_terms=skill_terms, max_occurrences=max_keyword_occurrences
    )
    findings += check_g7_entity_casing(blocks, proper_nouns=proper_nouns)
    findings += check_g8_typography(blocks)
    findings += check_g9_fact_attribution(blocks, facts=facts, skill_labels=skill_labels)
    return GuardReport(findings=findings)
