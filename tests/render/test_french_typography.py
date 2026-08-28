"""Tests for French typography rules (defect D10)."""

from __future__ import annotations

from src.render.french_typography import NBSP, NNBSP, apply_french_typography, has_expected_spacing


def test_narrow_nbsp_inserted_before_punctuation():
    result = apply_french_typography("Vous maîtrisez Python : oui !")
    assert f"{NNBSP}:" in result
    assert f"{NNBSP}!" in result


def test_nbsp_inserted_before_percent():
    result = apply_french_typography("Amélioration de 65%")
    assert f"{NBSP}%" in result


def test_nbsp_inserted_as_thousands_separator():
    result = apply_french_typography("Budget de 12 000 euros")
    assert f"12{NBSP}000" in result


def test_has_expected_spacing_true_after_applying_rules():
    result = apply_french_typography("Score : 90% ; validé !")
    assert has_expected_spacing(result)


def test_has_expected_spacing_false_on_raw_text():
    assert has_expected_spacing("Score : 90%") is False
