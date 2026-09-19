# -*- coding: utf-8 -*-
"""Registry of adversarial text-injection techniques.

The output of the generator is always a PDF (CVs uploaded as DOCX are first
converted to PDF, preserving the original layout, then injected using the
exact same code path as native PDF CVs -- see ``generator.py`` and
``pdf_injector.py``). Each :class:`Technique` therefore only needs a single
reliability rating, so the UI can be honest about methods that are weak or
easily defeated instead of pretending they all work equally well.

Reliability levels:
  - ``"reliable"``: works as intended, and (unless noted) survives naive
                     text extraction the way a real ATS parser would see it.
  - ``"partial"``: works but with caveats -- e.g. depends on assumptions
                     about the renderer/extractor that don't always hold.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Technique:
    id: str
    label: str
    description: str
    reliability: str
    note: str


TECHNIQUES: list[Technique] = [
    Technique(
        id="white_text",
        label="White text",
        description=(
            "Le texte injecté a la même couleur que le fond de page (blanc "
            "sur blanc)."
        ),
        reliability="partial",
        note=(
            "Superposé en remplissage blanc (RGB 1,1,1) sur la dernière page "
            "existante. Invisible seulement si le fond de page est "
            "effectivement blanc à cet endroit."
        ),
    ),
    Technique(
        id="tiny_font",
        label="Minimal font size",
        description=(
            "Le texte injecté est présent mais à une taille de police "
            "quasi nulle."
        ),
        reliability="reliable",
        note="Superposé en taille 0,5 pt sur la dernière page existante.",
    ),
    Technique(
        id="offpage",
        label="Hidden/off-page text",
        description=(
            "Le texte injecté est positionné en dehors de la zone imprimable "
            "de la page."
        ),
        reliability="partial",
        note=(
            "Texte positionné sous la zone visible (hors MediaBox) de la "
            "dernière page existante. Mesuré empiriquement : PyMuPDF/"
            "pdfplumber (comme beaucoup d'extracteurs standards) *rognent* "
            "l'extraction au MediaBox et ne renvoient PAS ce texte -- cette "
            "méthode trompe l'affichage humain mais échoue souvent aussi "
            "contre l'extracteur. Un scanner brut du flux de contenu PDF "
            "(sans passer par une API 'get text') le verrait quand même."
        ),
    ),
    Technique(
        id="transparent",
        label="Transparent text",
        description=(
            "Le texte injecté utilise un mode de rendu invisible (opacité "
            "nulle)."
        ),
        reliability="reliable",
        note=(
            "Mode de rendu de texte invisible (Tr 3) sur la dernière page "
            "existante, le même mécanisme utilisé par les couches OCR : le "
            "texte n'est jamais dessiné mais reste extractible."
        ),
    ),
    Technique(
        id="hidden_layer",
        label="Hidden PDF layer",
        description=(
            "Le texte injecté est placé dans un calque désactivé par défaut."
        ),
        reliability="partial",
        note=(
            "Groupe de contenu optionnel (OCG) créé et désactivé par défaut "
            "sur la dernière page existante. Mesuré empiriquement : PyMuPDF "
            "(comme d'autres bibliothèques conscientes des calques) respecte "
            "l'état OFF de l'OCG et NE renvoie PAS ce texte via une "
            "extraction standard -- exactement comme le ferait un lecteur "
            "PDF. Seuls des extracteurs plus rudimentaires, qui ignorent la "
            "notion de calque optionnel, pourraient encore le renvoyer : la "
            "fiabilité dépend entièrement de la bibliothèque utilisée par "
            "l'ATS cible."
        ),
    ),
    Technique(
        id="metadata",
        label="Metadata/text-layer injection",
        description=(
            "Le texte injecté est stocké dans les métadonnées du document, "
            "pas dans le corps visible."
        ),
        reliability="reliable",
        note=(
            "Injecté dans le dictionnaire Info du PDF (Keywords/Subject). Ne "
            "sera vu que par un ATS qui scanne spécifiquement les métadonnées "
            "-- pas par une extraction classique du corps du texte."
        ),
    ),
]

_BY_ID = {t.id: t for t in TECHNIQUES}


def get_technique(technique_id: str) -> Technique:
    try:
        return _BY_ID[technique_id]
    except KeyError as exc:
        raise ValueError(f"Technique inconnue : {technique_id}") from exc
