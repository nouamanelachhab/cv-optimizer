"""Tests for the typer CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def test_analyze_generates_html_report(tmp_path, simple_cv_bytes, offer_text_decathlon):
    cv_path = tmp_path / "cv.docx"
    cv_path.write_bytes(simple_cv_bytes)
    offer_path = tmp_path / "offer.txt"
    offer_path.write_text(offer_text_decathlon, encoding="utf-8")
    out_path = tmp_path / "rapport.html"

    result = runner.invoke(
        app, [str(cv_path), "--offer", str(offer_path), "--out", str(out_path)]
    )

    assert result.exit_code == 0, result.output
    assert out_path.exists()
    html = out_path.read_text(encoding="utf-8")
    assert "Rapport d'analyse ATS" in html


def test_analyze_generates_json_report(tmp_path, simple_cv_bytes, offer_text_decathlon):
    cv_path = tmp_path / "cv.docx"
    cv_path.write_bytes(simple_cv_bytes)
    offer_path = tmp_path / "offer.txt"
    offer_path.write_text(offer_text_decathlon, encoding="utf-8")
    out_path = tmp_path / "rapport.json"

    result = runner.invoke(
        app, [str(cv_path), "--offer", str(offer_path), "--out", str(out_path)]
    )

    assert result.exit_code == 0, result.output
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "score" in data
    assert "match" in data
    assert "parseability" in data


def test_analyze_fails_gracefully_on_missing_cv(tmp_path, offer_text_decathlon):
    offer_path = tmp_path / "offer.txt"
    offer_path.write_text(offer_text_decathlon, encoding="utf-8")
    out_path = tmp_path / "rapport.html"

    result = runner.invoke(
        app,
        [str(tmp_path / "missing.docx"), "--offer", str(offer_path), "--out", str(out_path)],
    )

    assert result.exit_code != 0
    assert not out_path.exists()
