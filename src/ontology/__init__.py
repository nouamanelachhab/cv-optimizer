"""Ontology loading and alias resolution.

Loads ``data/ontology/skills.yaml`` (validated against ``schema.json`` via
jsonschema) into frozen pydantic models, and provides an alias index for the
(not-yet-built) ``match`` module to resolve surface terms to canonical
skills. Unrecognized terms are never invented here; they simply are not
present in the index, and callers are expected to bucket them as
"unmapped_terms" (handled in the ``match`` module).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import validate as jsonschema_validate

from src.normalize import canonicalize
from src.ontology.models import Ontology, SkillDef

__all__ = ["Ontology", "SkillDef", "load_ontology", "build_alias_index"]

_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "ontology" / "skills.yaml"
)
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"


def load_ontology(path: Path | None = None) -> Ontology:
    """Load and validate the skills ontology from a YAML file."""
    data_path = path or _DEFAULT_DATA_PATH
    raw_yaml = data_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_yaml) or []

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema_validate(instance=data, schema=schema)

    skills = [SkillDef(**entry) for entry in data]
    return Ontology(skills=skills)


def build_alias_index(ontology: Ontology) -> dict[str, SkillDef]:
    """Map every canonicalized alias/label to its owning SkillDef.

    Later duplicate aliases across skills would silently overwrite earlier
    ones; ontology seed data is expected to keep aliases unique per skill.
    """
    index: dict[str, SkillDef] = {}
    for skill in ontology.skills:
        index[canonicalize(skill.label)] = skill
        for alias in skill.aliases:
            index[canonicalize(alias)] = skill
    return index
