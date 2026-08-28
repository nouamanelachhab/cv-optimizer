"""Import-lint: ``unidecode`` must only ever be imported from ``src/normalize``,
and ``rapidfuzz`` must only ever be imported from ``src/match``.

This directly guards against the class of bug where diacritic-stripping or
fuzzy/edit-distance logic leaks into other modules (e.g. render, extract)
and silently corrupts proper nouns, accented text, or produces a fuzzy match
that reaches the written document (defect D3/D4/D6).
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
_NORMALIZE_MODULE = SRC_ROOT / "normalize" / "__init__.py"
_MATCH_MODULE = SRC_ROOT / "match" / "__init__.py"

_UNIDECODE_IMPORT = re.compile(r"^\s*(from unidecode|import unidecode)\b", re.MULTILINE)
_RAPIDFUZZ_IMPORT = re.compile(r"^\s*(from rapidfuzz|import rapidfuzz)\b", re.MULTILINE)


def test_unidecode_only_imported_in_normalize_module():
    offenders: list[str] = []
    for py_file in SRC_ROOT.rglob("*.py"):
        if py_file.resolve() == _NORMALIZE_MODULE.resolve():
            continue
        content = py_file.read_text(encoding="utf-8")
        if _UNIDECODE_IMPORT.search(content):
            offenders.append(str(py_file.relative_to(SRC_ROOT.parent)))

    assert offenders == [], (
        "unidecode must only be imported in src/normalize/__init__.py, "
        f"but was found in: {offenders}"
    )


def test_rapidfuzz_only_imported_in_match_module():
    offenders: list[str] = []
    for py_file in SRC_ROOT.rglob("*.py"):
        if py_file.resolve() == _MATCH_MODULE.resolve():
            continue
        content = py_file.read_text(encoding="utf-8")
        if _RAPIDFUZZ_IMPORT.search(content):
            offenders.append(str(py_file.relative_to(SRC_ROOT.parent)))

    assert offenders == [], (
        "rapidfuzz must only be imported in src/match/__init__.py, "
        f"but was found in: {offenders}"
    )

