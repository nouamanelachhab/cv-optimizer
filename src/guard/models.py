"""Pydantic data contracts for the guard module.

The guard module never writes to the document. It only validates a proposed
set of rendered blocks *before* they are allowed to reach the final output.

``RenderedBlock`` is intentionally decoupled from the (not-yet-built) render
module's own operation types: guard must be usable and testable in isolation,
per the mandated delivery order (guard G1-G3 must exist and be tested before
any module that writes). The render module will later construct
``RenderedBlock`` instances from its typed operations (KeepBlock,
ReorderBlocks, DropBlock, InsertTemplateBlock) and hand them to guard.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Operation(str, Enum):
    """The provenance of a rendered block's text."""

    KEEP = "keep"
    """Text must be byte-identical to the original source block."""

    INSERT = "insert"
    """Text originates from a pre-validated template, not from the original."""


class RenderedBlock(BaseModel):
    """A single block as it will appear in the final rendered document."""

    model_config = {"frozen": True}

    block_id: str
    operation: Operation
    output_text: str
    source_text: str | None = None
    """Original text for KEEP blocks. Must be None for INSERT blocks."""


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class GuardFinding(BaseModel):
    model_config = {"frozen": True}

    rule_id: str
    severity: Severity
    message: str
    block_id: str | None = None


class GuardReport(BaseModel):
    model_config = {"frozen": True}

    findings: list[GuardFinding] = []

    @property
    def passed(self) -> bool:
        return not any(f.severity == Severity.ERROR for f in self.findings)

    @property
    def errors(self) -> list[GuardFinding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[GuardFinding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]
