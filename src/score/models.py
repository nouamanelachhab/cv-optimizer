"""Pydantic data contracts for the score module."""

from __future__ import annotations

from pydantic import BaseModel


class SubScore(BaseModel):
    model_config = {"frozen": True}

    name: str
    value: float
    """0-100."""
    weight: float
    explanation: str
    """Human-readable justification -- always traceable to concrete facts,
    never a vague qualitative statement."""


class Score(BaseModel):
    model_config = {"frozen": True}

    sub_scores: list[SubScore]

    @property
    def total(self) -> float:
        total_weight = sum(s.weight for s in self.sub_scores)
        if total_weight == 0:
            return 0.0
        return sum(s.value * s.weight for s in self.sub_scores) / total_weight

    def explain(self) -> list[str]:
        return [
            f"{s.name} ({s.value:.1f}/100, poids {s.weight:.2f}): {s.explanation}"
            for s in self.sub_scores
        ]
