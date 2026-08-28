"""Match: compare CV skills against job-offer requirements in three passes.

  1. Exact canonical: skill ids already resolved by ``extract`` (via the
     ontology) are compared directly -- no fuzziness at all.
  2. Ontology alias: free-text keywords (from ``extract_keywords``, not
     already recognized by ``extract_skills``) are looked up *deterministically*
     against the ontology alias index (still zero fuzziness, just a second
     lookup pass over keywords extract's n-gram window may have missed).
  3. Fuzzy (guarded): remaining free-text keywords are compared with
     rapidfuzz against the *other side's* free-text keywords. Results are
     never promoted to matched/missing/extra -- they are only ever surfaced
     as ``FuzzyCandidate`` for manual human review, with a strict score
     threshold and a minimum term length to avoid short-string false
     positives (defect D3).
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from src.match.models import FuzzyCandidate, MatchResult, MatchStatus, SkillMatch
from src.normalize import canonicalize
from src.ontology import Ontology, build_alias_index

__all__ = ["match"]

_MIN_FUZZY_TERM_LENGTH = 4
_DEFAULT_FUZZY_THRESHOLD = 90.0


def _label_for(skill_id: str, ontology: Ontology) -> str:
    skill = ontology.find(skill_id)
    return skill.label if skill is not None else skill_id


def match(
    cv_skill_ids: set[str],
    offer_skill_ids: set[str],
    cv_keywords: list[str],
    offer_keywords: list[str],
    ontology: Ontology,
    fuzzy_threshold: float = _DEFAULT_FUZZY_THRESHOLD,
) -> MatchResult:
    """Run the 3-pass match between a CV's and a job offer's skills/keywords."""
    alias_index = build_alias_index(ontology)

    cv_ids = set(cv_skill_ids)
    offer_ids = set(offer_skill_ids)

    # Pass 2: deterministic ontology-alias resolution over free-text keywords.
    for term in offer_keywords:
        skill = alias_index.get(canonicalize(term))
        if skill is not None:
            offer_ids.add(skill.id)
    for term in cv_keywords:
        skill = alias_index.get(canonicalize(term))
        if skill is not None:
            cv_ids.add(skill.id)

    matched_ids = cv_ids & offer_ids
    missing_ids = offer_ids - cv_ids
    extra_ids = cv_ids - offer_ids

    # Pass 3: guarded fuzzy free-text candidates, for manual review only.
    fuzzy_candidates: list[FuzzyCandidate] = []
    canonical_cv_keywords = [canonicalize(k) for k in cv_keywords]
    if canonical_cv_keywords:
        for offer_term in offer_keywords:
            canonical_offer_term = canonicalize(offer_term)
            if canonical_offer_term in alias_index:
                continue  # already resolved deterministically in pass 2
            if len(canonical_offer_term) < _MIN_FUZZY_TERM_LENGTH:
                continue
            best = process.extractOne(
                canonical_offer_term, canonical_cv_keywords, scorer=fuzz.ratio
            )
            if best is not None and best[1] >= fuzzy_threshold:
                fuzzy_candidates.append(
                    FuzzyCandidate(
                        offer_term=offer_term, cv_term=best[0], score=float(best[1])
                    )
                )

    matched = [
        SkillMatch(skill_id=i, label=_label_for(i, ontology), status=MatchStatus.MATCHED)
        for i in sorted(matched_ids)
    ]
    missing = [
        SkillMatch(skill_id=i, label=_label_for(i, ontology), status=MatchStatus.MISSING)
        for i in sorted(missing_ids)
    ]
    extra = [
        SkillMatch(skill_id=i, label=_label_for(i, ontology), status=MatchStatus.EXTRA)
        for i in sorted(extra_ids)
    ]

    return MatchResult(
        matched=matched, missing=missing, extra=extra, fuzzy_candidates=fuzzy_candidates
    )
