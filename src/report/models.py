"""Pydantic data contracts for the report module."""

from __future__ import annotations

from pydantic import BaseModel

from src.guard.models import GuardReport
from src.match.models import MatchResult
from src.parseability.models import ParseabilityReport
from src.score.models import Score


class Report(BaseModel):
    model_config = {"frozen": True}

    candidate_name: str | None = None
    score: Score
    match: MatchResult
    parseability: ParseabilityReport
    guard: GuardReport | None = None
