# -*- coding: utf-8 -*-
"""Lecture, recolorisation et enrichissement ATS d'un CV Word (.docx).

Un .docx est une archive ZIP contenant du XML. On combine :
  - python-docx : pour lire le texte et injecter une section de mots-cles ;
  - manipulation directe du ZIP/XML : pour remplacer les couleurs d'accent
    par la charte de la societe (document.xml, styles.xml, theme1.xml).
"""

import io
import re
import zipfile
from collections import Counter

from docx import Document

HEX_RE = re.compile(r'w:(?:color|themeColor)?\s*[^>]*?w:val="([0-9A-Fa-f]{6})"')
COLOR_ATTR_RE = re.compile(r'w:val="([0-9A-Fa-f]{6})"')

XML_TARGETS = ["word/document.xml", "word/styles.xml", "word/theme/theme1.xml"]


# --------------------------------------------------------------------------- #
# Lecture du texte
# --------------------------------------------------------------------------- #
def read_text(docx_bytes):
    """Extrait tout le texte du document (paragraphes + tableaux)."""
    doc = Document(io.BytesIO(docx_bytes))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Detection des couleurs d'accent
# --------------------------------------------------------------------------- #
def _rgb(hx):
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def _is_accent(hx):
    """Ecarte noir, blanc et gris : on ne garde que les couleurs de marque."""
    r, g, b = _rgb(hx)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx > 235 and mn > 235:
        return False
    if mx < 45:
        return False
    if mx - mn < 22:
        return False
    return True


def _luminance(hx):
    r, g, b = _rgb(hx)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def detect_accent_colors(docx_bytes):
    """Retourne les couleurs d'accent du CV, triees par frequence."""
    counter = Counter()
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        for name in XML_TARGETS:
            if name not in z.namelist():
                continue
            xml = z.read(name).decode("utf-8", errors="ignore")
            for hx in COLOR_ATTR_RE.findall(xml):
                hx = hx.upper()
                if _is_accent(hx):
                    counter[hx] += 1
    return counter.most_common()


def build_color_mapping(accents, primary_hex, secondary_hex):
    """Associe les couleurs d'accent existantes a la charte cible.

    L'accent le plus fonce -> couleur primaire ; l'autre -> secondaire.
    """
    primary_hex = primary_hex.upper()
    secondary_hex = secondary_hex.upper()
    tops = [hx for hx, _ in accents[:2]]
    mapping = {}
    if len(tops) == 1:
        mapping[tops[0]] = primary_hex
    elif len(tops) >= 2:
        a, b = tops[0], tops[1]
        darker, lighter = (a, b) if _luminance(a) <= _luminance(b) else (b, a)
        mapping[darker] = primary_hex
        mapping[lighter] = secondary_hex
    return mapping


# --------------------------------------------------------------------------- #
# Recolorisation
# --------------------------------------------------------------------------- #
def recolor(docx_bytes, mapping):
    """Remplace les couleurs selon `mapping` ({ancienHex: nouveauHex})."""
    if not mapping:
        return docx_bytes

    src = io.BytesIO(docx_bytes)
    dst = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(
        dst, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in XML_TARGETS:
                text = data.decode("utf-8", errors="ignore")
                for old_hex, new_hex in mapping.items():
                    text = re.sub(
                        re.escape(old_hex), new_hex, text, flags=re.IGNORECASE
                    )
                data = text.encode("utf-8")
            zout.writestr(item, data)
    return dst.getvalue()


# --------------------------------------------------------------------------- #
# Extraction de la structure (Profil + bullets d'experience)
# --------------------------------------------------------------------------- #
# Vocabulaire de rubriques par categorie. On ne cherche pas une correspondance
# exacte au mot pres : la classification s'appuie sur ce vocabulaire ETENDU
# combine a une correspondance floue (rapidfuzz) et a des indices de mise en
# forme (gras, majuscules, taille de police), afin de reconnaitre des intitules
# non-standards ("Mon parcours", "Qui suis-je ?", "Mes compétences clés"...).
HEADING_VOCAB = {
    "profil": {
        "profil", "profile", "a propos", "a propos de moi", "about",
        "about me", "resume", "summary", "presentation",
        "presentation personnelle", "accroche", "objectif",
        "objectif professionnel", "qui suis-je", "mon profil", "synthese",
        "synthese professionnelle", "career summary", "personal profile",
        "professional summary", "profil professionnel",
    },
    "experience": {
        "experience", "experiences", "experience professionnelle",
        "experiences professionnelles", "work experience",
        "professional experience", "parcours", "parcours professionnel",
        "mon parcours", "vie professionnelle", "emplois",
        "postes occupes", "historique professionnel", "career history",
        "employment history", "experiences professionnelles et stages",
    },
    "competences": {
        "competences", "competences techniques", "competences cles",
        "competences professionnelles", "skills", "technical skills",
        "key skills", "savoir-faire", "expertises", "expertise",
        "hard skills", "soft skills", "outils", "outils et technologies",
        "technologies", "competences informatiques",
    },
    "formation": {
        "formation", "formations", "formation academique", "education",
        "parcours academique", "diplomes", "diplome", "etudes", "cursus",
        "academic background", "qualifications", "formation et diplomes",
    },
    "langues": {
        "langues", "languages", "langues parlees", "language skills",
    },
    "projets": {
        "projets", "projects", "realisations", "portfolio",
        "projets personnels", "side projects", "projets academiques",
    },
    "contact": {
        "contact", "coordonnees", "informations personnelles",
        "contact information", "me contacter",
    },
    "loisirs": {
        "loisirs", "centres d'interet", "centre d'interet", "interets",
        "hobbies", "activites extra-professionnelles", "passions",
    },
    "certifications": {
        "certifications", "certificats", "certification", "accreditations",
    },
    "references": {
        "references", "recommandations",
    },
}
# Alias conserves pour compatibilite (utilises comme section-tags internes).
PROFILE_HEADINGS = HEADING_VOCAB["profil"]
EXPERIENCE_HEADINGS = HEADING_VOCAB["experience"]

try:
    from rapidfuzz import fuzz as _rf_fuzz
    _HAS_RAPIDFUZZ = True
except Exception:  # pragma: no cover - repli si lib absente
    _HAS_RAPIDFUZZ = False


def _norm_heading(text):
    import unicodedata
    t = text.strip().lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip(" :\u2014-")


def _classify_heading_text(norm):
    """Devine la categorie d'un intitule normalise, sans exiger un mot exact.

    1) Correspondance exacte au vocabulaire (rapide, fiable).
    2) A defaut, correspondance floue (rapidfuzz) : tolere les mots ajoutes
       ("mon", "mes", "professionnel(le)s"), les abreviations et les fautes.
    """
    if not norm:
        return None
    for cat, phrases in HEADING_VOCAB.items():
        if norm in phrases:
            return cat
    if not _HAS_RAPIDFUZZ:
        return None
    best_cat, best_score = None, 0
    for cat, phrases in HEADING_VOCAB.items():
        for phrase in phrases:
            if " " in phrase or " " in norm:
                score = _rf_fuzz.partial_ratio(norm, phrase)
                thresh = 90
            else:
                score = _rf_fuzz.ratio(norm, phrase)
                thresh = 84
            if score >= thresh and score > best_score:
                best_score, best_cat = score, cat
    return best_cat


def _looks_like_heading_shape(text):
    """Filtre de forme : court, sans ponctuation de fin de phrase.

    Applique AVANT toute correspondance de vocabulaire (exacte ou floue) afin
    d'eviter les faux positifs sur une phrase longue qui contiendrait par
    hasard un mot proche d'une rubrique (ex : "...mes comptences en anglais").
    """
    if not text or len(text) > 60:
        return False
    if text.rstrip().endswith((".", ",", ";")):
        return False
    if len(text.split()) > 6:
        return False
    return True


def classify_heading_from_text(text):
    """Comme `classify_heading`, mais a partir d'une simple ligne de texte
    (pas d'objet paragraphe, donc pas d'info de mise en forme). Utilise pour
    le reformattage intelligent d'un CV mal structure (voir `utils.reformat`).
    """
    text = text.strip()
    if not _looks_like_heading_shape(text):
        return False, None
    norm = _norm_heading(text)
    cat = _classify_heading_text(norm)
    if cat:
        return True, cat
    letters = [c for c in text if c.isalpha()]
    is_allcaps = bool(letters) and text == text.upper()
    if is_allcaps:
        return True, "autre"
    return False, None


def _paragraph_is_bold(paragraph):
    runs = [r for r in paragraph.runs if r.text.strip()]
    if not runs:
        return False
    return all(r.bold for r in runs)


def _paragraph_font_size(paragraph):
    for r in paragraph.runs:
        if r.font.size is not None:
            return r.font.size.pt
    return None


def _doc_median_font_size(doc):
    sizes = [
        r.font.size.pt
        for p in doc.paragraphs
        for r in p.runs
        if r.font.size is not None
    ]
    if not sizes:
        return None
    sizes.sort()
    mid = len(sizes) // 2
    if len(sizes) % 2:
        return sizes[mid]
    return (sizes[mid - 1] + sizes[mid]) / 2


def classify_heading(paragraph, median_size=None):
    """Determine si un paragraphe est un titre de section, et sa categorie.

    Retourne (is_heading, category). `category` vaut l'une des cles de
    HEADING_VOCAB, ou "autre" pour un titre generique non reconnu (detecte
    via mise en forme : gras / majuscules / police plus grande que le corps).
    """
    text = paragraph.text.strip()
    if not _looks_like_heading_shape(text):
        return False, None

    norm = _norm_heading(text)
    cat = _classify_heading_text(norm)
    if cat:
        return True, cat

    # Indices de mise en forme quand le vocabulaire ne suffit pas.
    words = text.split()
    letters = [c for c in text if c.isalpha()]
    is_allcaps = bool(letters) and text == text.upper()
    is_bold = _paragraph_is_bold(paragraph)
    size = _paragraph_font_size(paragraph)
    is_large = median_size is not None and size is not None and size > median_size + 1.4

    if is_allcaps or (is_bold and (is_large or len(words) <= 4)):
        return True, "autre"
    return False, None


def _is_heading(paragraph, median_size=None):
    return classify_heading(paragraph, median_size)[0]


def _is_bullet(paragraph):
    """Vrai si le paragraphe est une puce (numbering) ou style de liste."""
    style = paragraph.style
    style_name = (style.name or "").lower() if style is not None else ""
    if "list" in style_name or "liste" in style_name or "puce" in style_name:
        return True
    ppr = paragraph._p.pPr
    if ppr is not None and ppr.numPr is not None:
        return True
    return False


def extract_structure(docx_bytes):
    """Retourne le texte du profil et la liste des bullets d'experience.

    Format de retour :
      {
        "profile": {"index": int, "text": str} | None,
        "experience_bullets": [ {"index": int, "text": str}, ... ],
      }
    Les index referencent doc.paragraphs (recharge cote application).
    """
    doc = Document(io.BytesIO(docx_bytes))
    median_size = _doc_median_font_size(doc)
    section = None
    profile = None
    bullets = []

    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        is_h, cat = classify_heading(p, median_size)
        if is_h:
            if cat == "profil":
                section = "profil"
            elif cat == "experience":
                section = "experience"
            else:
                # Autre rubrique (competences, formation, titre generique...) :
                # on sort des sections suivies pour ne pas melanger le contenu.
                section = "autre"
            continue

        if not text:
            continue

        if section == "profil" and profile is None:
            profile = {"index": i, "text": text}
        elif section == "experience" and _is_bullet(p):
            bullets.append({"index": i, "text": text})

    return {"profile": profile, "experience_bullets": bullets}


# --------------------------------------------------------------------------- #
# Evaluation de la qualite de mise en forme (CV malformatte ?)
# --------------------------------------------------------------------------- #
def _iter_block_items(doc):
    """Parcourt paragraphes et tableaux dans l'ordre du document."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def assess_format(docx_bytes):
    """Evalue si le CV est suffisamment structure pour une analyse automatique.

    Un CV est considere "malformatte" quand on ne parvient pas a identifier
    de rubriques claires (peu ou pas de titres de section reconnus, contenu
    tasse dans quelques paragraphes, mise en page uniquement via tableaux...).
    Dans ce cas, mieux vaut proposer un reformattage intelligent plutot que
    de lancer une analyse ATS qui se baserait sur une structure incertaine.
    """
    doc = Document(io.BytesIO(docx_bytes))
    median_size = _doc_median_font_size(doc)
    non_empty = [p for p in doc.paragraphs if p.text.strip()]

    categories = set()
    heading_count = 0
    for p in non_empty:
        is_h, cat = classify_heading(p, median_size)
        if is_h:
            heading_count += 1
            if cat and cat != "autre":
                categories.add(cat)

    n_paras = len(non_empty)
    total_chars = sum(len(p.text) for p in non_empty)
    table_chars = sum(
        len(cell.text)
        for table in doc.tables
        for row in table.rows
        for cell in row.cells
    )

    reasons = []
    if heading_count == 0 and total_chars > 200:
        reasons.append("Aucune rubrique (titre de section) n'a ete detectee.")
    if len(categories) < 2 and total_chars > 350:
        reasons.append(
            "Moins de deux rubriques identifiees clairement "
            "(Profil, Experience, Competences...)."
        )
    if n_paras < 6 and total_chars > 350:
        reasons.append(
            "Le contenu semble concentre dans tres peu de paragraphes "
            "(mise en page probablement via des sauts de ligne manuels ou "
            "des zones de texte)."
        )
    if table_chars > 2 * max(total_chars, 1):
        reasons.append(
            "Le CV est mis en page principalement via des tableaux/zones "
            "graphiques, difficiles a analyser automatiquement."
        )

    return {
        "malformed": bool(reasons),
        "reasons": reasons,
        "section_categories": categories,
        "paragraph_count": n_paras,
        "heading_count": heading_count,
    }


def extract_raw_lines(docx_bytes):
    """Extrait les lignes de texte du document, dans l'ordre de lecture.

    Combine paragraphes et cellules de tableaux (utile pour un CV mis en page
    via des tableaux) : sert de base au reformattage intelligent.
    """
    doc = Document(io.BytesIO(docx_bytes))
    lines = []
    for block in _iter_block_items(doc):
        if hasattr(block, "rows"):  # Table
            for row in block.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        t = p.text.strip()
                        if t:
                            lines.append(t)
        else:  # Paragraph
            t = block.text.strip()
            if t:
                lines.append(t)
    return lines


def _set_paragraph_text(paragraph, new_text):
    """Remplace le texte d'un paragraphe en conservant le format du 1er run."""
    if paragraph.runs:
        paragraph.runs[0].text = new_text
        for r in paragraph.runs[1:]:
            r.text = ""
    else:
        paragraph.add_run(new_text)


def apply_rewrites(docx_bytes, new_profile=None, bullet_edits=None):
    """Applique la reecriture du profil et des bullets.

    - new_profile : texte de remplacement du paragraphe profil (ou None).
    - bullet_edits : dict {index_paragraphe: nouveau_texte}.
    Conserve la mise en forme (couleurs, puces, tailles) des paragraphes.
    """
    doc = Document(io.BytesIO(docx_bytes))
    paras = doc.paragraphs

    structure = extract_structure(docx_bytes)
    if new_profile and structure["profile"] is not None:
        idx = structure["profile"]["index"]
        if 0 <= idx < len(paras):
            _set_paragraph_text(paras[idx], new_profile)

    if bullet_edits:
        for idx, new_text in bullet_edits.items():
            if 0 <= idx < len(paras) and new_text is not None:
                _set_paragraph_text(paras[idx], new_text)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
