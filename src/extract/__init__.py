"""Extract: find ontology skill mentions and free-text keywords in a text.

Two extraction strategies, kept strictly separate:
  - ``extract_skills``: deterministic Aho-Corasick automaton lookup against
    the ontology's aliases (single linear pass, exact matches only -- no
    edit-distance/fuzzy logic anywhere in this path, which is what makes a
    false match like "infocentre" -> "innocente" structurally impossible).
    Ambiguous skills (e.g. "Java", per defect D7) are only kept if at least
    one unambiguous skill is also found in the same text, guarding against
    false-positive single-word matches out of context.
  - ``extract_keywords``: statistical keyword extraction (yake) over the raw
    text, for terms not present in the ontology at all. These are surfaced
    as free-text candidates only -- never auto-inserted into a document.
"""

from __future__ import annotations

import re

import yake

from src.extract.models import ExtractedSkill
from src.normalize import canonicalize
from src.ontology import Ontology
from src.ontology.automaton import build_automaton, find_skills

__all__ = ["extract_skills", "extract_keywords"]


def _find_surface_text(text: str, skill) -> str:
    """Best-effort recovery of the exact original substring that matched.

    The automaton itself only ever sees the canonicalized text (per the
    addendum's confinement of accent/case folding to ``normalize``); this
    looks the alias back up in the original text so ``surface_text`` stays
    a genuine, unmodified substring rather than a canonicalized or
    ontology-relabeled one.
    """
    for alias in [skill.label, *skill.aliases]:
        pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(0)
    return skill.label


def extract_skills(text: str, ontology: Ontology) -> list[ExtractedSkill]:
    """Find ontology skill mentions in ``text`` via the Aho-Corasick automaton."""
    automaton = build_automaton(ontology)
    matched_skills = find_skills(text, automaton)

    has_unambiguous_match = any(not skill.ambiguous for skill in matched_skills)

    results: list[ExtractedSkill] = []
    for skill in matched_skills:
        if skill.ambiguous and not has_unambiguous_match:
            continue
        results.append(
            ExtractedSkill(
                skill_id=skill.id,
                label=skill.label,
                category=skill.category,
                surface_text=_find_surface_text(text, skill),
            )
        )
    return results


def extract_keywords(text: str, top_k: int = 15, language: str = "fr") -> list[str]:
    """Extract free-text candidate keywords not tied to the ontology (via yake)."""
    extractor = yake.KeywordExtractor(lan=language, n=2, top=top_k)
    scored = extractor.extract_keywords(text)
    # yake: lower score == more relevant.
    return [keyword for keyword, _score in sorted(scored, key=lambda pair: pair[1])]
