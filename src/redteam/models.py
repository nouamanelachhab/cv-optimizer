# -*- coding: utf-8 -*-
"""Data model returned by the adversarial CV generator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationResult:
    output_bytes: bytes
    filename: str
    technique_id: str
    technique_label: str
    reliability: str  # "reliable" | "partial"
    reliability_note: str
    injected_chars: int
    injected_words: int
    naive_extract_injected_chars: int
    page_count_before: int
    page_count_after: int
    preview_png: bytes | None = None
