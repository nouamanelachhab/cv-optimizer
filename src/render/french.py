"""French-language rendering helpers used by template insertion.

These are narrow, deterministic grammar mechanics -- not free generation.
They never assemble arbitrary sentences; they only adjust fixed template
scaffolding (elision, list punctuation) around ontology-validated slot
values.

Elision needs the *phonetic* nature of the initial sound, not just the
first letter: a naive "starts with a vowel letter" rule writes ``d'héros``
instead of the correct ``de héros`` (h aspiré). A tiny curated seed list of
h-aspiré words stands in for a full Lexique383 phonetic lookup (offline,
no network dependency); anything not in the list falls back to the
vowel-letter heuristic, which is correct for the overwhelming majority of
French words and for acronyms (``d'API`` vs ``de PKI``).
"""

from __future__ import annotations

_ELIDABLE = {"le": "l'", "la": "l'", "de": "d'", "que": "qu'", "ne": "n'", "se": "s'"}
_VOWEL_OR_MUTE_H = set("aeiouyàâäéèêëîïôöùûü") | {"h"}

# Seed list of common h-aspiré words/acronyms (no elision, no liaison).
# Not exhaustive -- a full solution would consult Lexique383's phonetic
# transcription column, per the addendum.
_H_ASPIRE = {
    "héros",
    "hall",
    "hasard",
    "hangar",
    "handicap",
    "hockey",
    "hollande",
    "haricot",
}

# Acronyms/initialisms pronounced as a sequence of consonant-sounding letter
# names in French (e.g. "PKI" -> "pé-ka-i", consonant "P" sound) do NOT elide,
# whereas acronyms starting with a vowel-sounding letter name (e.g. "API" ->
# "a-pé-i") DO elide. This table lists the French pronunciation class of each
# letter when read as an initialism.
_CONSONANT_SOUNDING_LETTERS = set("BCDFGJKLMNPQRSTWXZ") 
_VOWEL_SOUNDING_LETTERS = set("AEHIOUY")


def _starts_with_vowel_sound(word: str) -> bool:
    if not word:
        return False
    lower = word.lower()
    if lower in _H_ASPIRE:
        return False
    # All-uppercase multi-letter token: treat as an acronym/initialism and
    # judge by how its first letter is *named* in French, not how it reads
    # as an ordinary word.
    if len(word) > 1 and word.isupper():
        return word[0] in _VOWEL_SOUNDING_LETTERS
    return lower[0] in _VOWEL_OR_MUTE_H


def elide(word: str, next_word: str) -> str:
    """Apply French elision to ``word`` if ``next_word`` starts with a vowel sound.

    e.g. ``elide("de", "Anglais")`` -> ``"d'"``, but ``elide("de", "héros")``
    stays ``"de"`` (h aspiré), and ``elide("de", "API")`` -> ``"d'"`` while
    ``elide("de", "PKI")`` stays ``"de"`` (acronym pronunciation).
    """
    lower = word.lower()
    if lower not in _ELIDABLE or not next_word:
        return word
    if not _starts_with_vowel_sound(next_word):
        return word
    prefix = _ELIDABLE[lower]
    return prefix.capitalize() if word[:1].isupper() else prefix


def join_list_fr(items: list[str]) -> str:
    """Join items the French way: ``"a, b et c"``."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " et " + items[-1]

