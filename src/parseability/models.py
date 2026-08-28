"""Pydantic data contracts for the parseability module."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ParseabilitySeverity(str, Enum):
    WARNING = "warning"
    INFO = "info"


class ParseabilityIssue(BaseModel):
    model_config = {"frozen": True}

    code: str
    severity: ParseabilitySeverity
    message: str


class ParseabilityReport(BaseModel):
    model_config = {"frozen": True}

    issues: list[ParseabilityIssue] = []
