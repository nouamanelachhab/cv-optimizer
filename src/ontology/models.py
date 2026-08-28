"""Pydantic data contracts for the skills ontology."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SkillCategory(str, Enum):
    PROGRAMMING_LANGUAGE = "programming_language"
    SPOKEN_LANGUAGE = "spoken_language"
    TOOL = "tool"
    FRAMEWORK = "framework"
    DATABASE = "database"
    METHODOLOGY = "methodology"
    SOFT_SKILL = "soft_skill"
    CERTIFICATION = "certification"
    CLOUD = "cloud"
    OTHER = "other"


class SkillType(str, Enum):
    """ESCO-style distinction: a hard skill (technology, tool, framework...)
    versus a transversal/soft skill. Used by extract to enforce that a term
    without ESCO/local backing (defect D7, e.g. "Technique") is never
    promoted to a matched skill."""

    HARD_SKILL = "hard_skill"
    SOFT_SKILL = "soft_skill"
    LANGUAGE = "language"


class SkillDef(BaseModel):
    """A single canonical skill entry with its known surface-form aliases."""

    model_config = {"frozen": True}

    id: str
    label: str
    category: SkillCategory
    aliases: list[str] = []
    ambiguous: bool = False
    """If True, a bare alias match is not sufficient on its own (defect D7):
    downstream (extract/match) must require additional technical context."""
    type: SkillType = SkillType.HARD_SKILL
    esco_uri: str | None = None
    """Reference URI into the ESCO skills taxonomy, when this entry maps to
    a known ESCO concept. None for IT-specific entries (frameworks, precise
    tooling) that the addendum notes ESCO is weak on and that this local
    ontology maintains by hand as a surcouche."""


class Ontology(BaseModel):
    model_config = {"frozen": True}

    skills: list[SkillDef]

    def find(self, skill_id: str) -> SkillDef | None:
        for skill in self.skills:
            if skill.id == skill_id:
                return skill
        return None
