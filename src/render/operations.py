"""Typed render operations.

These four operations are the *only* way to affect the final document. There
is no operation (and none will ever be added) that edits a substring of an
existing block's text -- KeepBlock preserves it verbatim, DropBlock removes
it wholesale, ReorderBlocks only changes sequence, and InsertTemplateBlock
inserts fully pre-validated template text. This makes free-text rewriting
impossible at the type level, not just by convention.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class KeepBlock(BaseModel):
    model_config = {"frozen": True}

    op: Literal["keep"] = "keep"
    block_id: str


class ReorderBlocks(BaseModel):
    model_config = {"frozen": True}

    op: Literal["reorder"] = "reorder"
    block_ids: list[str]


class DropBlock(BaseModel):
    model_config = {"frozen": True}

    op: Literal["drop"] = "drop"
    block_id: str


class InsertTemplateBlock(BaseModel):
    model_config = {"frozen": True}

    op: Literal["insert_template"] = "insert_template"
    template_id: str
    slots: dict[str, str | list[str]]


RenderOperation = Annotated[
    Union[KeepBlock, ReorderBlocks, DropBlock, InsertTemplateBlock],
    Field(discriminator="op"),
]
