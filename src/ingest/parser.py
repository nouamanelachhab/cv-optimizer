# -*- coding: utf-8 -*-
"""Parsing d'un .docx en arbre Document (voir ingest/models.py).

python-docx fournit le modele objet pour le flux normal (paragraphes,
tableaux). lxml est utilise en complement pour detecter le contenu HORS FLUX
(en-tetes, pieds de page, zones de texte / formes `w:txbxContent`, controles
de contenu `w:sdt`) que python-docx n'expose pas ou mal : ce contenu est
souvent invisible aux ATS et remonte par `parseability`, jamais modifie par
`render`.

Le texte porte par les noeuds produits ici est TOUJOURS le texte original
exact. Aucune normalisation, aucune correction n'est appliquee.
"""

from __future__ import annotations

import io
import re
import zipfile

from docx import Document as _DocxDocument
from lxml import etree

from .models import Bullet, BlockKind, Document, Entry, Section, make_block_id

_NSMAP = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}

# Vocabulaire minimal de titres de section reconnus (correspondance exacte
# apres normalisation legere ; la reconnaissance floue/etendue est du ressort
# de modules ulterieurs si besoin, ce module reste un simple ingest fidele).
_SECTION_VOCAB = {
    "profil": {"profil", "profile", "a propos", "resume", "summary", "presentation", "accroche", "objectif"},
    "experience": {"experience", "experiences", "experience professionnelle",
                   "experiences professionnelles", "work experience", "parcours",
                   "parcours professionnel"},
    "competences": {"competences", "competences techniques", "skills", "savoir-faire"},
    "formation": {"formation", "formations", "education", "diplomes", "etudes"},
    "langues": {"langues", "languages"},
    "projets": {"projets", "projects", "realisations"},
    "contact": {"contact", "coordonnees"},
    "loisirs": {"loisirs", "centres d'interet", "centre d'interet", "interets", "hobbies"},
    "certifications": {"certifications", "certificats"},
    "references": {"references"},
}


def _norm_heading(text: str) -> str:
    import unicodedata
    t = text.strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip(" :\u2014-")


def _heading_category(text: str) -> str | None:
    if not text or len(text) > 60:
        return None
    if text.rstrip().endswith((".", ",", ";")):
        return None
    if len(text.split()) > 6:
        return None
    norm = _norm_heading(text)
    for cat, vocab in _SECTION_VOCAB.items():
        if norm in vocab:
            return cat
    letters = [c for c in text if c.isalpha()]
    if letters and text == text.upper() and len(text.split()) <= 6:
        return "autre"
    return None


def _is_bullet_style(paragraph) -> bool:
    style = paragraph.style
    style_name = (style.name or "").lower() if style is not None else ""
    if "list" in style_name or "liste" in style_name or "puce" in style_name:
        return True
    ppr = paragraph._p.pPr
    if ppr is not None and ppr.numPr is not None:
        return True
    return False


def parse_docx(docx_bytes: bytes, source_name: str = "") -> Document:
    """Construit l'arbre Document a partir des octets d'un fichier .docx."""
    docx = _DocxDocument(io.BytesIO(docx_bytes))
    paragraphs = docx.paragraphs

    name_block: Bullet | None = None
    contact_blocks: list[Bullet] = []
    sections: list[Section] = []
    current: Section | None = None
    current_entry: Entry | None = None

    seen_non_empty = 0
    for offset, p in enumerate(paragraphs):
        text = p.text.strip()
        if not text:
            continue

        cat = _heading_category(text)
        if cat is not None:
            bid = make_block_id(source_name, str(offset), text, "heading")
            current = Section(
                block_id=bid, heading_text=text, category=cat, xml_offset=offset,
            )
            sections.append(current)
            current_entry = None
            continue

        seen_non_empty += 1
        bid = make_block_id(source_name, str(offset), text)

        # Avant la premiere section : nom (1re ligne) puis lignes de contact.
        if current is None:
            if name_block is None:
                name_block = Bullet(
                    block_id=bid, text=text, xml_offset=offset,
                    style_name=(p.style.name if p.style is not None else None),
                    kind=BlockKind.CONTACT,
                )
            else:
                contact_blocks.append(Bullet(
                    block_id=bid, text=text, xml_offset=offset,
                    style_name=(p.style.name if p.style is not None else None),
                    kind=BlockKind.CONTACT,
                ))
            continue

        style_name = p.style.name if p.style is not None else None
        if _is_bullet_style(p):
            bullet = Bullet(
                block_id=bid, text=text, xml_offset=offset, style_name=style_name,
                kind=BlockKind.BULLET,
            )
            if current_entry is not None:
                current_entry = current_entry.model_copy(
                    update={"bullets": [*current_entry.bullets, bullet]}
                )
                # Remplace la derniere entree de la section courante (frozen
                # models -> on reconstruit la liste `entries`).
                new_entries = list(current.entries[:-1]) + [current_entry]
                current = current.model_copy(update={"entries": new_entries})
                sections[-1] = current
            else:
                current = current.model_copy(
                    update={"free_text_blocks": [*current.free_text_blocks, bullet]}
                )
                sections[-1] = current
        else:
            # Un paragraphe non-puce dans une section devient une nouvelle
            # Entry (ex: intitule de poste + dates) si la section est de type
            # experience/formation/projets, sinon un free_text_block.
            if current.category in {"experience", "formation", "projets"}:
                current_entry = Entry(
                    block_id=bid, title=text, text=text, xml_offset=offset,
                    style_name=style_name,
                )
                current = current.model_copy(
                    update={"entries": [*current.entries, current_entry]}
                )
                sections[-1] = current
            else:
                current = current.model_copy(
                    update={"free_text_blocks": [*current.free_text_blocks, Bullet(
                        block_id=bid, text=text, xml_offset=offset,
                        style_name=style_name, kind=BlockKind.PARAGRAPH,
                    )]}
                )
                sections[-1] = current

    out_of_flow = _extract_out_of_flow_blocks(docx_bytes, source_name)

    return Document(
        source_name=source_name,
        name_block=name_block,
        contact_blocks=contact_blocks,
        sections=sections,
        out_of_flow_blocks=out_of_flow,
    )


# --------------------------------------------------------------------------- #
# Contenu hors flux (lxml) : en-tetes, pieds de page, zones de texte, w:sdt.
# --------------------------------------------------------------------------- #
_HEADER_FOOTER_RE = re.compile(r"^word/(header|footer)\d*\.xml$")


def _extract_out_of_flow_blocks(docx_bytes: bytes, source_name: str) -> list[Bullet]:
    blocks: list[Bullet] = []
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        names = z.namelist()

        # En-tetes / pieds de page.
        for name in names:
            if _HEADER_FOOTER_RE.match(name):
                xml = z.read(name)
                for i, text in enumerate(_iter_paragraph_texts(xml)):
                    if text.strip():
                        blocks.append(Bullet(
                            block_id=make_block_id(source_name, name, str(i), text),
                            text=text.strip(), xml_offset=-1,
                            kind=BlockKind.UNKNOWN,
                        ))

        # Zones de texte / formes (w:txbxContent) et controles de contenu
        # (w:sdt) dans le document principal : souvent ignores par les ATS.
        if "word/document.xml" in names:
            xml = z.read("word/document.xml")
            root = etree.fromstring(xml)
            for i, txbx in enumerate(root.iter("{%s}txbxContent" % _NSMAP["w"])):
                for j, text in enumerate(_iter_paragraph_texts_from_element(txbx)):
                    if text.strip():
                        blocks.append(Bullet(
                            block_id=make_block_id(source_name, "txbx", str(i), str(j), text),
                            text=text.strip(), xml_offset=-1,
                            kind=BlockKind.UNKNOWN,
                        ))
            for i, sdt in enumerate(root.iter("{%s}sdt" % _NSMAP["w"])):
                for j, text in enumerate(_iter_paragraph_texts_from_element(sdt)):
                    if text.strip():
                        blocks.append(Bullet(
                            block_id=make_block_id(source_name, "sdt", str(i), str(j), text),
                            text=text.strip(), xml_offset=-1,
                            kind=BlockKind.UNKNOWN,
                        ))
    return blocks


def _iter_paragraph_texts(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    return _iter_paragraph_texts_from_element(root)


def _iter_paragraph_texts_from_element(elem) -> list[str]:
    out = []
    for p in elem.iter("{%s}p" % _NSMAP["w"]):
        texts = p.findall(".//{%s}t" % _NSMAP["w"])
        out.append("".join(t.text or "" for t in texts))
    return out
