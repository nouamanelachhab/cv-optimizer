# -*- coding: utf-8 -*-
"""Modeles pydantic du document ingere : Document -> Section -> Entry -> Bullet.

Regle absolue : le texte `text` porte par chaque noeud est le texte ORIGINAL,
exact, jamais modifie. C'est la seule source de verite pour tout module en
aval. Rien dans ce module ne doit alterer ce texte (pas de normalisation, pas
de correction).
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BlockKind(str, Enum):
    """Nature d'un bloc de contenu, pour guider le rendu et le guard."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLET = "bullet"
    CONTACT = "contact"
    UNKNOWN = "unknown"


def make_block_id(*parts: str) -> str:
    """Hash stable et court identifiant un bloc (utilise pour tracer les
    operations de rendu et les preuves de matching)."""
    h = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return h[:12]


class Bullet(BaseModel):
    """Une puce (ligne de detail) au sein d'une Entry (experience, projet...)."""

    block_id: str
    text: str = Field(..., description="Texte original exact, immuable.")
    xml_offset: int = Field(..., description="Position du paragraphe dans le corps du document.")
    style_name: Optional[str] = None
    kind: BlockKind = BlockKind.BULLET

    model_config = {"frozen": True}


class Entry(BaseModel):
    """Une entree d'une section (une experience, une formation, un projet)."""

    block_id: str
    title: Optional[str] = Field(None, description="Intitule de l'entree si detecte (poste, diplome...).")
    text: str = Field("", description="Texte d'introduction de l'entree (hors puces), original exact.")
    xml_offset: int
    style_name: Optional[str] = None
    bullets: list[Bullet] = Field(default_factory=list)

    model_config = {"frozen": True}


class Section(BaseModel):
    """Une rubrique du CV (Profil, Experience, Competences...)."""

    block_id: str
    heading_text: str = Field(..., description="Texte original exact du titre de section.")
    category: str = Field("autre", description="Categorie normalisee (profil, experience, competences...).")
    xml_offset: int
    entries: list[Entry] = Field(default_factory=list)
    # Paragraphes de contenu qui ne sont ni un titre d'entree ni une puce
    # (ex: une ligne de competences en texte libre, un paragraphe de profil).
    free_text_blocks: list[Bullet] = Field(default_factory=list)

    model_config = {"frozen": True}


class Document(BaseModel):
    """Arbre complet d'un CV ingere."""

    source_name: str = ""
    name_block: Optional[Bullet] = Field(None, description="Premiere ligne du CV (nom du candidat), si detectee.")
    contact_blocks: list[Bullet] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    # Blocs hors modele objet python-docx standard (en-tete/pied de page,
    # zones de texte, w:sdt) detectes via lxml. Non modifiables par le
    # render, mais signales par parseability.
    out_of_flow_blocks: list[Bullet] = Field(default_factory=list)

    model_config = {"frozen": True}

    def all_blocks(self) -> list[Bullet]:
        """Retourne tous les blocs textuels (nom, contact, sections, puces)."""
        out: list[Bullet] = []
        if self.name_block:
            out.append(self.name_block)
        out.extend(self.contact_blocks)
        for sec in self.sections:
            out.append(Bullet(
                block_id=sec.block_id, text=sec.heading_text,
                xml_offset=sec.xml_offset, kind=BlockKind.HEADING,
            ))
            for entry in sec.entries:
                if entry.text:
                    out.append(Bullet(
                        block_id=entry.block_id, text=entry.text,
                        xml_offset=entry.xml_offset, style_name=entry.style_name,
                        kind=BlockKind.PARAGRAPH,
                    ))
                out.extend(entry.bullets)
            out.extend(sec.free_text_blocks)
        out.extend(self.out_of_flow_blocks)
        return out

    def block_ids(self) -> set[str]:
        return {b.block_id for b in self.all_blocks()}
