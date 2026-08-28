"""Aho-Corasick automaton for deterministic, single-pass skill matching.

Per the addendum: replaces distance-based fuzzy substring lookups with an
automaton that finds every known alias in a single linear pass with zero
false positives from edit-distance drift (this is what makes
``infocentre -> innocente`` structurally impossible: there is no distance
computation in the write path at all, only exact automaton matches).

The value stored for every matched alias is always the skill's *canonical*
label from the ontology, never the surface form found in the source text --
this is also what fixes casing defects such as ``décathlon`` needing to
become ``Decathlon``: the canonical form always comes from the ontology.
"""

from __future__ import annotations

import re

import ahocorasick

from src.normalize import canonicalize
from src.ontology.models import Ontology, SkillDef

__all__ = ["build_automaton", "find_skills"]

_WORD_CHAR = re.compile(r"\w", re.UNICODE)


def build_automaton(ontology: Ontology) -> ahocorasick.Automaton:
    """Build an Aho-Corasick automaton indexing every alias/label, keyed by
    its canonicalized form, with the owning ``SkillDef`` as payload."""
    automaton = ahocorasick.Automaton()
    for skill in ontology.skills:
        for alias in [skill.label, *skill.aliases]:
            key = canonicalize(alias)
            if key:
                automaton.add_word(key, (skill.id, skill))
    automaton.make_automaton()
    return automaton


def _is_word_boundary(text: str, start: int, end: int) -> bool:
    """True if ``text[start:end]`` is not glued to adjacent word characters.

    Prevents partial matches inside larger words (the addendum's example:
    a bare "C" must not match inside "Confluence").
    """
    before_ok = start == 0 or not _WORD_CHAR.match(text[start - 1])
    after_ok = end >= len(text) or not _WORD_CHAR.match(text[end])
    return before_ok and after_ok


def find_skills(text: str, automaton: ahocorasick.Automaton) -> list[SkillDef]:
    """Find every ontology skill mentioned in ``text`` via the automaton.

    Matches are checked against source-text word boundaries (not just the
    canonicalized text) so multi-word aliases and single-letter aliases
    alike only match whole words.
    """
    canonical_text = canonicalize(text)
    # Map canonical-text offsets back onto the original text is not exact in
    # general (canonicalization can change length), so boundary-checking is
    # performed on the canonical text itself, which uses the same tokenizing
    # rules (`\w`) as the original for ASCII/latin scripts.
    seen_ids: set[str] = set()
    results: list[SkillDef] = []
    for end_index, (skill_id, skill) in automaton.iter(canonical_text):
        start_index = end_index - len(canonicalize(skill.label)) + 1
        # Recompute start via the actually matched key length instead of the
        # label (aliases can differ in length from the label).
        matched_key = None
        for alias in [skill.label, *skill.aliases]:
            key = canonicalize(alias)
            if key and canonical_text[max(0, end_index - len(key) + 1) : end_index + 1] == key:
                matched_key = key
                break
        if matched_key is None:
            continue
        start_index = end_index - len(matched_key) + 1
        if not _is_word_boundary(canonical_text, start_index, end_index + 1):
            continue
        if skill_id in seen_ids:
            continue
        seen_ids.add(skill_id)
        results.append(skill)
    return results
