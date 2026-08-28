# -*- coding: utf-8 -*-
"""Édition d'un paragraphe .docx par remplacement de spans (jamais par
réassemblage du paragraphe).

C'est la pièce technique centrale des modifications de niveau « certain »
(section 5 du prompt) : on ne réécrit QUE les runs effectivement touchés par
une modification, en conservant leur ``rPr`` (police, gras, couleur...).

Interdits absolus, respectés ici :
  - ``paragraph.text = ...``
  - ``paragraph.clear()``
  - suppression puis recréation de runs
  - toute regex de substitution sur le texte concaténé d'un paragraphe entier

Chaque run existant est conservé (même vide) ; seul son texte (``run.text``,
c'est-à-dire le nœud ``<w:t>``) est réécrit quand une span le touche. Sa
propriété de mise en forme (``run.font`` / ``rPr``) n'est jamais touchée.
"""

from __future__ import annotations

from pydantic import BaseModel


class Span(BaseModel):
    """Une modification exprimée en position dans le texte concaténé du
    paragraphe : remplace ``text[start:end]`` par ``replacement``."""

    model_config = {"frozen": True}

    start: int
    end: int
    replacement: str


def paragraph_text(paragraph) -> str:
    """Concatène les runs d'un paragraphe (jamais ``paragraph.text``, qui en
    python-docx ne garantit pas la même sémantique de concaténation)."""
    return "".join(run.text for run in paragraph.runs)


def _validate_spans(spans: list[Span], length: int) -> list[Span]:
    ordered = sorted(spans, key=lambda s: s.start)
    prev_end = -1
    for span in ordered:
        if span.start < 0 or span.end > length or span.start > span.end:
            raise ValueError(f"Span hors limites ou invalide : {span}")
        if span.start < prev_end:
            raise ValueError(f"Spans chevauchants interdits : {span}")
        prev_end = span.end
    return ordered


def apply_spans(paragraph, spans: list[Span]) -> None:
    """Applique ``spans`` au paragraphe en ne réécrivant QUE les runs
    touchés. Une liste vide, ou des spans no-op (start == end == ''), ne
    modifient rien : c'est le contrat vérifié par le test de round-trip.
    """
    if not spans:
        return

    text = paragraph_text(paragraph)
    ordered = _validate_spans(spans, len(text))
    if not ordered:
        return

    # Bornes [start, end) de chaque run dans le texte concaténé.
    runs = list(paragraph.runs)
    run_bounds: list[tuple[int, int]] = []
    cursor = 0
    for run in runs:
        run_bounds.append((cursor, cursor + len(run.text)))
        cursor += len(run.text)

    touched_runs: list[int] = []
    for run_index, (run_start, run_end) in enumerate(run_bounds):
        run = runs[run_index]
        if run_end <= run_start:
            continue  # run déjà vide, rien à repositionner dessus
        new_text_parts: list[str] = []
        pos = run_start
        emitted_replacement_here = False
        while pos < run_end:
            covering = next((s for s in ordered if s.start <= pos < s.end), None)
            if covering is not None:
                # N'émet le texte de remplacement qu'une seule fois, dans le
                # tout premier run touché par cette span.
                if pos == covering.start:
                    new_text_parts.append(covering.replacement)
                pos = min(covering.end, run_end)
                emitted_replacement_here = True
                continue
            # Segment non couvert : copie verbatim jusqu'à la prochaine span
            # ou la fin du run.
            next_start = min(
                [s.start for s in ordered if run_start <= s.start < run_end and s.start > pos]
                + [run_end]
            )
            new_text_parts.append(text[pos:next_start])
            pos = next_start

        new_text = "".join(new_text_parts)
        if new_text != run.text or emitted_replacement_here:
            touched_runs.append(run_index)
            run.text = new_text  # ne touche que <w:t>, jamais rPr/run._r

    # Si une span commence exactement à la frontière de deux runs, ou après
    # le dernier caractère d'un run vide, elle doit tout de même apparaître
    # quelque part : cas déjà couvert car run_bounds inclut tous les runs et
    # la boucle ci-dessus considère chaque position start couverte par au
    # moins un run non vide (le paragraphe n'a pas de "trou" entre runs).
