"""Typer CLI for the deterministic ATS engine.

Usage:
    python -m src.cli analyze cv.docx --offer offre.txt --out rapport.html
"""

from __future__ import annotations

from pathlib import Path

import typer

from src.extract import extract_keywords, extract_skills
from src.ingest import parse_docx
from src.match import match
from src.ontology import load_ontology
from src.parseability import run_parseability_audit
from src.report import build_report, to_html, to_json
from src.score import compute_score

app = typer.Typer(help="Analyse déterministe d'un CV face à une offre d'emploi (sans LLM).")


@app.command()
def analyze(
    cv: Path = typer.Argument(..., exists=True, help="Chemin vers le CV au format .docx"),
    offer: Path = typer.Option(..., "--offer", exists=True, help="Chemin vers le texte de l'offre"),
    out: Path = typer.Option(Path("rapport.html"), "--out", help="Chemin du rapport (.html ou .json)"),
) -> None:
    """Analyse un CV .docx par rapport à une offre et écrit un rapport (jamais le CV lui-même)."""
    cv_bytes = cv.read_bytes()
    offer_text = offer.read_text(encoding="utf-8")

    doc = parse_docx(cv_bytes, source_name=cv.name)
    ontology = load_ontology()

    cv_text = "\n".join(block.text for block in doc.all_blocks())

    cv_skills = extract_skills(cv_text, ontology)
    offer_skills = extract_skills(offer_text, ontology)
    cv_keywords = extract_keywords(cv_text)
    offer_keywords = extract_keywords(offer_text)

    match_result = match(
        {skill.skill_id for skill in cv_skills},
        {skill.skill_id for skill in offer_skills},
        cv_keywords,
        offer_keywords,
        ontology,
    )
    score = compute_score(match_result)
    parseability_report = run_parseability_audit(doc, docx_bytes=cv_bytes)

    candidate_name = doc.name_block.text if doc.name_block else None
    report = build_report(
        score, match_result, parseability_report, candidate_name=candidate_name
    )

    content = to_json(report) if out.suffix.lower() == ".json" else to_html(report)
    out.write_text(content, encoding="utf-8")

    typer.echo(f"Rapport généré : {out} (score global : {score.total:.1f}/100)")


if __name__ == "__main__":
    app()
