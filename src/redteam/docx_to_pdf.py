# -*- coding: utf-8 -*-
"""Converts a DOCX CV to PDF while preserving its visual design exactly, so
that the hidden-text injection can then happen on a single, unified PDF code
path (see ``pdf_injector.py``) regardless of the CV's original format.

There is no pure-Python library that renders DOCX to PDF pixel-for-pixel
like a real word processor, so this module shells out to whatever rendering
engine is available on the machine:

1. LibreOffice / OpenOffice (``soffice`` on PATH) -- cross-platform, free.
2. Microsoft Word via the ``docx2pdf`` package (Windows/macOS, requires
   Word to be installed) -- used as a fallback.

If neither is available, ``ConversionUnavailableError`` is raised with a
clear, actionable message instead of silently producing a degraded PDF.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

__all__ = ["convert_docx_to_pdf", "ConversionUnavailableError"]


class ConversionUnavailableError(RuntimeError):
    """Raised when no DOCX->PDF conversion backend is available."""


def _find_soffice() -> str | None:
    for name in ("soffice", "soffice.exe"):
        path = shutil.which(name)
        if path:
            return path
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def _convert_with_soffice(docx_path: Path, out_dir: Path) -> Path:
    soffice = _find_soffice()
    if not soffice:
        raise ConversionUnavailableError("soffice introuvable")
    subprocess.run(
        [
            soffice,
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(docx_path),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    pdf_path = out_dir / (docx_path.stem + ".pdf")
    if not pdf_path.is_file():
        raise ConversionUnavailableError(
            "La conversion LibreOffice a échoué (aucun PDF produit)."
        )
    return pdf_path


def _convert_with_docx2pdf(docx_path: Path, out_dir: Path) -> Path:
    try:
        from docx2pdf import convert as _word_convert
    except ImportError as exc:
        raise ConversionUnavailableError("docx2pdf non installé") from exc
    pdf_path = out_dir / (docx_path.stem + ".pdf")
    _word_convert(str(docx_path), str(pdf_path))
    if not pdf_path.is_file():
        raise ConversionUnavailableError(
            "La conversion via Microsoft Word a échoué (aucun PDF produit)."
        )
    return pdf_path


def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Converts DOCX bytes to PDF bytes, preserving the original layout.

    Tries LibreOffice first (no GUI app needed), then falls back to
    Microsoft Word via ``docx2pdf``. Raises ``ConversionUnavailableError``
    with an actionable message if neither is usable.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        docx_path = tmp_dir / "input.docx"
        docx_path.write_bytes(docx_bytes)

        errors: list[str] = []
        for backend in (_convert_with_soffice, _convert_with_docx2pdf):
            try:
                pdf_path = backend(docx_path, tmp_dir)
                return pdf_path.read_bytes()
            except ConversionUnavailableError as exc:
                errors.append(str(exc))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{backend.__name__}: {exc}")

        raise ConversionUnavailableError(
            "Impossible de convertir le CV DOCX en PDF : aucun moteur de "
            "conversion disponible. Installez LibreOffice (gratuit, "
            "recommandé) ou Microsoft Word sur cette machine, ou "
            "utilisez directement un CV au format PDF. Détails : "
            + " | ".join(errors)
        )
