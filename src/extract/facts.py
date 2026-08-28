"""cv_facts: skills attested in a CV, each rattache a son bloc d'origine.

Un ``ExtractedSkill`` isole (voir ``src/extract/__init__.py``) ne dit rien sur
*ou* il a ete trouve dans le CV. Ce module ajoute cette ancre : chaque
``CvFact`` porte le ``block_id`` du bloc exact (puce, entree, section) ou le
terme apparait, et la ``scope`` (categorie de section) de ce bloc.

C'est ce qui rend le defaut D12 structurellement impossible : un terme
mentionne uniquement dans la rubrique Competences ne peut jamais etre presente
comme un fait attache a une experience particuliere, puisque son unique
``CvFact`` porte le ``block_id`` du bloc Competences.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.extract import extract_skills
from src.ingest.models import Document
from src.ontology import Ontology


class CvFact(BaseModel):
    model_config = {"frozen": True}

    label: str
    """Forme canonique du fait, issue de l'ontologie (SkillDef.label)."""

    block_id: str
    """Bloc exact (puce/entree/section) ou ce fait est atteste."""

    scope: str
    """Categorie de la section d'origine (ex: 'experience', 'competences')."""


def collect_facts(doc: Document, ontology: Ontology) -> list[CvFact]:
    """Extrait tous les faits (mentions de competences) du CV, chacun
    rattache au bloc precis ou il apparait (jamais a l'echelle du CV entier)."""
    facts: list[CvFact] = []
    for section in doc.sections:
        scope = section.category
        blocks: list[tuple[str, str]] = []
        for entry in section.entries:
            if entry.text:
                blocks.append((entry.block_id, entry.text))
            blocks.extend((b.block_id, b.text) for b in entry.bullets)
        blocks.extend((b.block_id, b.text) for b in section.free_text_blocks)

        for block_id, text in blocks:
            for skill in extract_skills(text, ontology):
                facts.append(CvFact(label=skill.label, block_id=block_id, scope=scope))
    return facts


def facts_for_block(facts: list[CvFact], block_id: str) -> list[CvFact]:
    """Faits autorises pour un bloc donne : uniquement ceux attestes dans ce
    bloc precis, jamais l'ensemble des faits du CV (voir D12)."""
    return [f for f in facts if f.block_id == block_id]
