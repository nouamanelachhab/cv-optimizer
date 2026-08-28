"""Pydantic data contracts for the extract module."""

from __future__ import annotations

from pydantic import BaseModel

from src.ontology.models import SkillCategory


class ExtractedSkill(BaseModel):
    model_config = {"frozen": True}

    skill_id: str
    label: str
    category: SkillCategory
    surface_text: str
    """The exact original substring that matched (never canonicalized)."""
