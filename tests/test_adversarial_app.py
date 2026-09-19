# -*- coding: utf-8 -*-
"""End-to-end test of the ATS Red-Team CV Generator Streamlit app: drives the
actual UI (file upload, job description textarea, technique selector,
Generate / Generate again buttons) through several successive generations,
using Streamlit's AppTest harness (no real browser needed).
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf as fitz
from streamlit.testing.v1 import AppTest

PDF_MIME = "application/pdf"
APP_PATH = str(Path(__file__).resolve().parent.parent / "adversarial_app.py")


def _make_cv_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Jean Dupont", fontsize=14)
    page.insert_text((72, 130), "Développeur Python — 5 ans d'expérience.", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if b.label == label:
            b.click()
            return
    raise AssertionError(f"Bouton introuvable : {label!r}")


def test_full_ui_workflow_multiple_successive_generations():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception

    cv_bytes = _make_cv_bytes()

    # --- 1) Charger le CV, coller une premiere offre, renseigner les champs requis ---
    at.file_uploader[0].set_value(("mon_cv.pdf", cv_bytes, PDF_MIME))
    at.text_input(key="company_name").set_value("Acme Corp")
    at.text_input(key="offer_title").set_value("Développeur Python Senior")
    at.text_area(key="job_description").set_value(
        "Recherche Ingénieur Python Senior : Django, Kubernetes, AWS."
    )
    at.run(timeout=30)
    assert not at.exception

    _click_button(at, "🎯 Generate adversarial CV")
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["generation_count"] == 1
    result1 = at.session_state["last_result"]
    assert result1.filename.lower().endswith(".pdf")
    assert "acme" in result1.filename.lower()
    assert "python" in result1.filename.lower()
    assert "senior" in result1.filename.lower()
    assert result1.page_count_after == result1.page_count_before
    assert result1.page_count_before > 0

    # --- 2) Modifier l'offre et regenerer via "Generate again" ---
    at.text_area(key="job_description").set_value(
        "Offre modifiée : Data Scientist, SQL, Spark, MLOps."
    )
    at.run(timeout=30)
    _click_button(at, "🔁 Generate again")
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["generation_count"] == 2
    result2 = at.session_state["last_result"]
    assert result2.injected_chars == len("Offre modifiée : Data Scientist, SQL, Spark, MLOps.")
    assert result2.page_count_after == result2.page_count_before

    # --- 3) Changer de technique et regenerer une 3e fois ---
    at.selectbox(key="technique_id").set_value("hidden_layer")
    at.run(timeout=30)
    _click_button(at, "🎯 Generate adversarial CV")
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["generation_count"] == 3
    result3 = at.session_state["last_result"]
    assert result3.technique_id == "hidden_layer"
    assert result3.page_count_after == result3.page_count_before

    # --- 4) Remplacer le CV par un autre fichier et generer a nouveau ---
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Marie Curie", fontsize=14)
    page.insert_text((72, 130), "Chercheuse en physique.", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    new_cv_bytes = buf.getvalue()

    at.file_uploader[0].set_value(("autre_cv.pdf", new_cv_bytes, PDF_MIME))
    at.run(timeout=30)
    _click_button(at, "🎯 Generate adversarial CV")
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["generation_count"] == 4
    result4 = at.session_state["last_result"]
    assert result4.filename.lower().endswith(".pdf")
    assert result4.page_count_after == result4.page_count_before


def test_generate_without_cv_shows_error():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    at.text_input(key="company_name").set_value("Acme Corp")
    at.text_input(key="offer_title").set_value("Data Engineer")
    at.text_area(key="job_description").set_value("Une offre quelconque.")
    at.run(timeout=30)
    _click_button(at, "🎯 Generate adversarial CV")
    at.run(timeout=30)
    assert not at.exception
    assert any("Veuillez charger un CV" in e.value for e in at.error)


def test_clear_description_button_empties_textarea():
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    at.text_area(key="job_description").set_value("Du texte à vider.")
    at.run(timeout=30)
    _click_button(at, "Vider la description")
    at.run(timeout=30)
    assert not at.exception
    assert at.text_area(key="job_description").value == ""
