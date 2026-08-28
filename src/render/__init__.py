"""Render: apply typed operations to produce guard-ready RenderedBlock output.

This is the only module allowed to construct the final block sequence. It
never edits text -- it only dispatches on one of the four typed operations
(KeepBlock, ReorderBlocks, DropBlock, InsertTemplateBlock) defined in
``src.render.operations``.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.guard.models import Operation, RenderedBlock
from src.ingest.models import make_block_id
from src.ontology.models import Ontology
from src.render.operations import (
    DropBlock,
    InsertTemplateBlock,
    KeepBlock,
    RenderOperation,
    ReorderBlocks,
)
from src.render.templates import Template, TemplateError, load_templates, render_template

__all__ = ["RenderError", "RenderResult", "render"]


class RenderError(Exception):
    """Raised when an operation cannot be safely applied. Never bypassed."""


class RenderResult(BaseModel):
    model_config = {"frozen": True}

    blocks: list[RenderedBlock] = []
    dropped_block_ids: list[str] = []


def render(
    operations: list[RenderOperation],
    source_blocks: dict[str, str],
    ontology: Ontology | None = None,
    templates: dict[str, Template] | None = None,
) -> RenderResult:
    """Apply ``operations`` in order, producing the final rendered block list."""
    if templates is None:
        templates = load_templates()

    rendered: list[RenderedBlock] = []
    dropped: list[str] = []
    insert_counter = 0

    for operation in operations:
        if isinstance(operation, KeepBlock):
            text = source_blocks.get(operation.block_id)
            if text is None:
                raise RenderError(f"Unknown block_id for KeepBlock: {operation.block_id!r}")
            rendered.append(
                RenderedBlock(
                    block_id=operation.block_id,
                    operation=Operation.KEEP,
                    source_text=text,
                    output_text=text,
                )
            )

        elif isinstance(operation, ReorderBlocks):
            for block_id in operation.block_ids:
                text = source_blocks.get(block_id)
                if text is None:
                    raise RenderError(f"Unknown block_id for ReorderBlocks: {block_id!r}")
                rendered.append(
                    RenderedBlock(
                        block_id=block_id,
                        operation=Operation.KEEP,
                        source_text=text,
                        output_text=text,
                    )
                )

        elif isinstance(operation, DropBlock):
            dropped.append(operation.block_id)

        elif isinstance(operation, InsertTemplateBlock):
            template = templates.get(operation.template_id)
            if template is None:
                raise RenderError(f"Unknown template_id: {operation.template_id!r}")
            if ontology is None:
                raise RenderError("An ontology is required to validate InsertTemplateBlock slots.")
            try:
                output_text = render_template(template, operation.slots, ontology)
            except TemplateError as exc:
                raise RenderError(str(exc)) from exc
            insert_counter += 1
            block_id = make_block_id("insert", operation.template_id, str(insert_counter))
            rendered.append(
                RenderedBlock(
                    block_id=block_id,
                    operation=Operation.INSERT,
                    source_text=None,
                    output_text=output_text,
                )
            )

        else:  # pragma: no cover - exhaustive by construction of RenderOperation
            raise RenderError(f"Unsupported render operation: {operation!r}")

    return RenderResult(blocks=rendered, dropped_block_ids=dropped)
