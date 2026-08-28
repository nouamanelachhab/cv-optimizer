"""French typography rules (defect D10): narrow-nbsp / nbsp insertion.

Applied only to rendered/generated blocks, never to the user's original
text -- consistent with the rest of ``render``: this is scaffolding around
already-validated content, not a rewrite of arbitrary text.
"""

from __future__ import annotations

import re

NNBSP = "\u202f"  # narrow no-break space
NBSP = "\u00a0"  # no-break space

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[ \u00a0\u202f]*([;:!?])"), NNBSP + r"\1"),
    (re.compile(r"[ \u00a0\u202f]*(»)"), NNBSP + r"\1"),
    (re.compile(r"(«)[ \u00a0\u202f]*"), r"\1" + NNBSP),
    (re.compile(r"[ \u00a0\u202f]*(%)"), NBSP + r"\1"),
    (re.compile(r"(\d)[ \u00a0\u202f](\d{3}\b)"), r"\1" + NBSP + r"\2"),
]


def apply_french_typography(text: str) -> str:
    """Insert narrow/no-break spaces per French typographic convention."""
    result = text
    for pattern, replacement in _RULES:
        result = pattern.sub(replacement, result)
    return result


def has_expected_spacing(text: str) -> bool:
    """G8 helper: True if every ;:!?» is preceded by NNBSP and every % by NBSP."""
    for match in re.finditer(r"[;:!?%»]", text):
        idx = match.start()
        expected = NBSP if match.group(0) == "%" else NNBSP
        if idx == 0 or text[idx - 1] != expected:
            return False
    return True
