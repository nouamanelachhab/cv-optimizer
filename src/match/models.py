"""Pydantic data contracts for the match module."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class MatchStatus(str, Enum):
    MATCHED = "matched"
    MISSING = "missing"
    EXTRA = "extra"


class SkillMatch(BaseModel):
    model_config = {"frozen": True}

    skill_id: str
    label: str
    status: MatchStatus


class FuzzyCandidate(BaseModel):
    """A tentative free-text match surfaced for manual review only.

    Never auto-promoted to matched/missing -- this is the strict guard that
    prevents the class of false-positive fuzzy matches described in D3.
    """

    model_config = {"frozen": True}

    offer_term: str
    cv_term: str
    score: float


class MatchResult(BaseModel):
    model_config = {"frozen": True}

    matched: list[SkillMatch] = []
    missing: list[SkillMatch] = []
    extra: list[SkillMatch] = []
    fuzzy_candidates: list[FuzzyCandidate] = []
