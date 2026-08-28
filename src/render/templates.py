"""Template loading and slot validation.

Slots are strictly typed and their values must come from a restricted,
ontology-backed source -- never arbitrary free text. This is what makes
InsertTemplateBlock safe: a template can only ever be filled with values the
system already knows to be correct (an ontology skill label, or a list of
them), so it can never produce an unfilled placeholder (defect D1) or an
invented sentence.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.ontology.models import Ontology
from src.render.french import join_list_fr

__all__ = ["SlotType", "Template", "load_templates", "render_template", "TemplateError"]

_DEFAULT_TEMPLATES_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "bullets.yaml"


class TemplateError(Exception):
    """Raised when a template or its slot values are invalid. Never silently ignored."""


class SlotType(str, Enum):
    SKILL_LABEL = "skill_label"
    SKILL_LABEL_LIST = "skill_label_list"


class Template(BaseModel):
    model_config = {"frozen": True}

    id: str
    text: str
    slots: dict[str, SlotType]


def load_templates(path: Path | None = None) -> dict[str, Template]:
    data_path = path or _DEFAULT_TEMPLATES_PATH
    data = yaml.safe_load(data_path.read_text(encoding="utf-8")) or []
    return {entry["id"]: Template(**entry) for entry in data}


def render_template(
    template: Template, slot_values: dict[str, str | list[str]], ontology: Ontology
) -> str:
    """Render ``template.text`` after strictly validating every slot value."""
    valid_labels = {skill.label for skill in ontology.skills}
    format_values: dict[str, str] = {}

    for slot_name, slot_type in template.slots.items():
        if slot_name not in slot_values:
            raise TemplateError(f"Missing required slot {slot_name!r} for template {template.id!r}.")
        value = slot_values[slot_name]

        if slot_type is SlotType.SKILL_LABEL:
            if not isinstance(value, str) or value not in valid_labels:
                raise TemplateError(
                    f"Slot {slot_name!r} must be a known ontology skill label, got {value!r}."
                )
            format_values[slot_name] = value

        elif slot_type is SlotType.SKILL_LABEL_LIST:
            if not isinstance(value, list) or not value:
                raise TemplateError(f"Slot {slot_name!r} must be a non-empty list of skill labels.")
            for item in value:
                if item not in valid_labels:
                    raise TemplateError(
                        f"Slot {slot_name!r} contains an unknown skill label: {item!r}."
                    )
            format_values[slot_name] = join_list_fr(value)

    rendered = template.text.format(**format_values)
    if "{" in rendered or "}" in rendered:
        raise TemplateError(f"Template {template.id!r} left an unresolved placeholder: {rendered!r}")
    return rendered
