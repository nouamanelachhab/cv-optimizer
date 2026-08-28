"""Tests for the normalize module."""

from __future__ import annotations

from src.normalize import canonical_tokens, canonicalize, strip_diacritics, to_nfc


def test_canonicalize_strips_accents_and_lowercases():
    assert canonicalize("Ingénieur Diplômé") == "ingenieur diplome"


def test_canonicalize_removes_punctuation_and_collapses_whitespace():
    assert canonicalize("PL/SQL, (Oracle) !!") == "pl sql oracle"


def test_canonicalize_does_not_mutate_input():
    original = "Sécurité réseau"
    _ = canonicalize(original)
    assert original == "Sécurité réseau"


def test_canonical_tokens_splits_on_whitespace():
    assert canonical_tokens("Python, SQL et Docker") == ["python", "sql", "et", "docker"]


def test_canonical_tokens_empty_string():
    assert canonical_tokens("") == []


def test_strip_diacritics_preserves_ascii():
    assert strip_diacritics("Decathlon") == "Decathlon"


def test_to_nfc_is_idempotent():
    text = "café"
    assert to_nfc(to_nfc(text)) == to_nfc(text)
