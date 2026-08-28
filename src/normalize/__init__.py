"""Normalize: the ONLY module allowed to strip diacritics / lowercase text.

Produces a *canonical* text representation used exclusively for matching,
extraction, and scoring. The canonical form must NEVER reach the render
module or the final document -- only the original *surface* text (as
ingested) may be written back out.

``unidecode`` is intentionally confined to this module. An import-lint test
(tests/test_import_lint.py) enforces that no other module under ``src/``
imports it.
"""

from __future__ import annotations

import re
import unicodedata

from unidecode import unidecode

__all__ = ["to_nfc", "strip_diacritics", "canonicalize", "canonical_tokens"]


def to_nfc(text: str) -> str:
    """Unicode-normalize to NFC (composed form)."""
    return unicodedata.normalize("NFC", text)


def strip_diacritics(text: str) -> str:
    """Remove diacritics/accents, transliterating to plain ASCII where possible."""
    return unidecode(text)


def canonicalize(text: str) -> str:
    """Produce a canonical form for matching purposes only.

    Steps: NFC normalize -> strip diacritics -> lowercase -> strip punctuation
    -> collapse whitespace. This output must never be written back to a
    document; it exists solely so that ``match``/``extract``/``ontology`` can
    compare terms robustly regardless of accents, case, or punctuation.
    """
    result = to_nfc(text)
    result = strip_diacritics(result)
    result = result.lower()
    result = re.sub(r"[^\w\s]", " ", result, flags=re.UNICODE)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def canonical_tokens(text: str) -> list[str]:
    """Tokenize the canonical form on whitespace."""
    canonical = canonicalize(text)
    if not canonical:
        return []
    return canonical.split(" ")
