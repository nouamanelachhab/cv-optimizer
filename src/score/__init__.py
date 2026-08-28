"""Score: explainable, weighted sub-scores computed from a match result.

Every sub-score carries a concrete, traceable explanation (which skills were
found/missing, counts) -- never a vague qualitative statement. This module
does not write to any document; it only produces numbers and text for the
``report`` module.
"""

from __future__ import annotations

from src.match.models import MatchResult
from src.score.models import Score, SubScore

__all__ = ["compute_score"]

_COVERAGE_WEIGHT = 0.7
_PRECISION_WEIGHT = 0.3


def _coverage_subscore(match_result: MatchResult) -> SubScore:
    required = len(match_result.matched) + len(match_result.missing)
    if required == 0:
        return SubScore(
            name="coverage",
            value=100.0,
            weight=_COVERAGE_WEIGHT,
            explanation="Aucune compétence requise détectée dans l'offre.",
        )
    value = 100.0 * len(match_result.matched) / required
    matched_labels = ", ".join(m.label for m in match_result.matched) or "aucune"
    missing_labels = ", ".join(m.label for m in match_result.missing) or "aucune"
    explanation = (
        f"{len(match_result.matched)}/{required} compétences requises trouvées "
        f"(présentes: {matched_labels}; manquantes: {missing_labels})."
    )
    return SubScore(
        name="coverage", value=value, weight=_COVERAGE_WEIGHT, explanation=explanation
    )


def _precision_subscore(match_result: MatchResult) -> SubScore:
    total_cv = len(match_result.matched) + len(match_result.extra)
    if total_cv == 0:
        return SubScore(
            name="precision",
            value=100.0,
            weight=_PRECISION_WEIGHT,
            explanation="Aucune compétence détectée dans le CV.",
        )
    value = 100.0 * len(match_result.matched) / total_cv
    explanation = (
        f"{len(match_result.matched)}/{total_cv} compétences du CV correspondent à "
        f"l'offre ({len(match_result.extra)} compétence(s) hors périmètre de l'offre)."
    )
    return SubScore(
        name="precision", value=value, weight=_PRECISION_WEIGHT, explanation=explanation
    )


def compute_score(match_result: MatchResult) -> Score:
    """Compute the overall explainable score from a match result."""
    return Score(
        sub_scores=[
            _coverage_subscore(match_result),
            _precision_subscore(match_result),
        ]
    )
