# -*- coding: utf-8 -*-
"""Ingestion : parsing .docx -> arbre Document type (voir `models.py`)."""

from .models import Bullet, BlockKind, Document, Entry, Section, make_block_id
from .parser import parse_docx

__all__ = [
    "Bullet", "BlockKind", "Document", "Entry", "Section", "make_block_id",
    "parse_docx",
]
