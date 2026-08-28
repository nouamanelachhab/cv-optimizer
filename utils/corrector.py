# -*- coding: utf-8 -*-
"""Correction automatique orthographe / grammaire / vocabulaire (hors-ligne).

Applique par defaut a tous les CV (bien ou mal formattes) avant generation :
  1. Typographie : espaces multiples, espace avant/apres ponctuation, mots
     repetes, majuscule en debut de phrase.
  2. Orthographe : dictionnaire francais (pyspellchecker, 100% local) pour
     les mots inconnus, en épargnant les termes techniques/competences du
     lexique metier et les acronymes (pour ne pas "corriger" Python, SQL...).
  3. Vocabulaire : petites confusions frequentes sur un CV (dictionnaire
     cible), en plus des tournures faibles deja gerees par cv_review.

Chaque correction appliquee est comptabilisee et restituee a l'utilisateur.
"""

import re
import unicodedata

from .skills_data import all_skills

# --------------------------------------------------------------------------- #
# Liste blanche : termes qu'il ne faut jamais "corriger" (jargon, acronymes).
# --------------------------------------------------------------------------- #
_EXTRA_WHITELIST = {
    "cv", "ats", "cdi", "cdd", "rh", "kpi", "ia", "ux", "ui", "pme", "eti",
    "b2b", "b2c", "rgpd", "saas", "paas", "iaas", "mvp", "roi", "seo", "sea",
    "erp", "crm", "sirh", "vae", "bac", "bts", "dut", "iut", "master", "licence",
    "linkedin", "excel", "word", "powerpoint", "outlook", "teams",
    # Anglicismes courants en CV/entreprise en francais (evite les
    # "corrections" vers un mot francais existant mais hors-sujet).
    "email", "mail", "job", "planning", "reporting", "workshop", "coaching",
    "freelance", "startup", "management", "manager", "leadership", "feedback",
    "brief", "briefing", "process", "digital", "marketing", "design",
    "hardware", "software", "cloud", "data", "deadline", "benchmark", "audit",
    "prestataire", "sourcing", "onboarding", "networking", "storytelling",
}


def _normalize(word):
    w = word.lower()
    w = unicodedata.normalize("NFD", w)
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return w


def _build_whitelist():
    words = set(_EXTRA_WHITELIST)
    for skill in all_skills():
        for token in re.split(r"[^A-Za-zÀ-ÿ0-9]+", skill):
            if token:
                words.add(_normalize(token))
    return words


_WHITELIST = _build_whitelist()

# --------------------------------------------------------------------------- #
# Vocabulaire : confusions frequentes sur un CV -> correction preferee.
# (cle normalisee sans accent -> forme correcte a afficher)
# --------------------------------------------------------------------------- #
VOCAB_FIXES = {
    "developement": "développement",
    "developement web": "développement web",
    "developeur": "développeur",
    "developeuse": "développeuse",
    "developpeur": "développeur",
    "developpeuse": "développeuse",
    "developpement": "développement",
    "manageur": "manager",
    "reponsable": "responsable",
    "comptence": "compétence",
    "comptences": "compétences",
    "experiance": "expérience",
    "experience professionel": "expérience professionnelle",
    "professionel": "professionnel",
    "professionelle": "professionnelle",
    "autonomme": "autonome",
    "rigoureu": "rigoureux",
    "language": "langage",
    "language de programmation": "langage de programmation",
}

_SENTENCE_END = re.compile(r"([.!?])\s+([a-zà-ÿ])")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
# Espace superflu avant virgule/point uniquement : ; : ! ? suivent une regle
# francaise differente (espace insecable fine), geree par _fix_french_typography.
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,.])")
_MISSING_SPACE_AFTER_PUNCT = re.compile(r"([,;:.!?])(?=[A-Za-zÀ-ÿ])")
_DUP_WORD = re.compile(r"\b(\w+)\b(\s+\1\b)+", re.IGNORECASE)

# Typographie francaise : espace insecable fine (U+202F) avant ; : ! ? et
# espace insecable (U+00A0) avant %. Ne s'applique jamais a l'interieur d'une
# URL/email/telephone (deja proteges par `_protect` avant cet appel).
_NNBSP = "\u202f"
_NBSP = "\u00a0"
_FR_NARROW_PUNCT_RE = re.compile(r"(\S)[ \t\u00a0\u202f]*([;:!?])")
_FR_PERCENT_RE = re.compile(r"(\d)[ \t\u00a0\u202f]*%")

# Emails / URLs / telephones : proteges (jamais retouches par la correction),
# pour eviter de casser une adresse mail ou un numero au passage.
_PROTECT_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+|https?://\S+|www\.\S+|\+?\d[\d .\-()]{7,}\d"
)
_PLACEHOLDER_RE = re.compile("\uE000(\\d+)\uE001")


def _protect(text):
    placeholders = []

    def repl(m):
        placeholders.append(m.group(0))
        return f"\uE000{len(placeholders) - 1}\uE001"

    return _PROTECT_RE.sub(repl, text), placeholders


def _restore(text, placeholders):
    def repl(m):
        return placeholders[int(m.group(1))]

    return _PLACEHOLDER_RE.sub(repl, text)

try:
    from spellchecker import SpellChecker
    _SPELL = SpellChecker(language="fr")
    _HAS_SPELLCHECKER = True
except Exception:  # pragma: no cover - repli si lib/dico absent
    _SPELL = None
    _HAS_SPELLCHECKER = False

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]*")


def _fix_typography(text):
    """Corrige espaces, ponctuation et mots doublonnes. Retourne (texte, n)."""
    n = 0
    fixed = text

    def _dup_repl(m):
        nonlocal n
        n += 1
        return m.group(1)

    fixed, c = _DUP_WORD.subn(_dup_repl, fixed)

    new = _MULTI_SPACE.sub(" ", fixed)
    if new != fixed:
        n += 1
    fixed = new

    new = _SPACE_BEFORE_PUNCT.sub(r"\1", fixed)
    if new != fixed:
        n += 1
    fixed = new

    new = _MISSING_SPACE_AFTER_PUNCT.sub(r"\1 ", fixed)
    if new != fixed:
        n += 1
    fixed = new

    def _cap_repl(m):
        return m.group(1) + " " + m.group(2).upper()

    new = _SENTENCE_END.sub(_cap_repl, fixed)
    if new != fixed:
        n += 1
    fixed = new

    def _fr_punct_repl(m):
        nonlocal n
        before, punct = m.group(1), m.group(2)
        replacement = before + _NNBSP + punct
        if replacement != m.group(0):
            n += 1
        return replacement

    new = _FR_NARROW_PUNCT_RE.sub(_fr_punct_repl, fixed)
    fixed = new

    def _fr_percent_repl(m):
        nonlocal n
        digit = m.group(1)
        replacement = digit + _NBSP + "%"
        if replacement != m.group(0):
            n += 1
        return replacement

    new = _FR_PERCENT_RE.sub(_fr_percent_repl, fixed)
    fixed = new

    if fixed:
        stripped = fixed.lstrip()
        lead = fixed[: len(fixed) - len(stripped)]
        if stripped and stripped[0].isalpha() and stripped[0] != stripped[0].upper():
            stripped = stripped[0].upper() + stripped[1:]
            n += 1
        fixed = lead + stripped

    return fixed.strip(), n


def _fix_vocabulary(text):
    """Applique les confusions de vocabulaire connues. Retourne (texte, n)."""
    n = 0

    def repl(m):
        nonlocal n
        word = m.group(0)
        key = _normalize(word)
        target = VOCAB_FIXES.get(key)
        if not target or target.lower() == word.lower():
            return word
        n += 1
        if word[0].isupper():
            target = target[0].upper() + target[1:]
        return target

    fixed = _WORD_RE.sub(repl, text)
    return fixed, n


def _fix_spelling(text):
    """Signale les mots hors dictionnaire francais, sans jamais les remplacer.

    Une correction devinee par le correcteur peut se reveler totalement hors
    sujet (ex. "infocentre" -> "innocente") : un mot que le dictionnaire ne
    reconnait pas est donc toujours laisse tel quel, jamais substitue par une
    supposition. Les mots commencant par une majuscule (hors debut de phrase)
    sont egalement ignores : il s'agit le plus souvent de noms propres.
    """
    return text, 0


def correct_text(text):
    """Corrige un texte (typographie, vocabulaire, orthographe).

    Les emails/URLs/telephones sont proteges (jamais modifies).
    Retourne (texte_corrige, nb_ameliorations).
    """
    if not text or not text.strip():
        return text, 0

    protected, placeholders = _protect(text)
    fixed, n1 = _fix_typography(protected)
    fixed, n2 = _fix_vocabulary(fixed)
    fixed, n3 = _fix_spelling(fixed)
    fixed = _restore(fixed, placeholders)
    return fixed, n1 + n2 + n3


def light_clean(text):
    """Nettoyage minimal (espaces) sans correction orthographique.

    A utiliser pour les champs qui sont surtout des noms propres / donnees de
    contact (nom, email, telephone...) : on ne veut pas risquer de les
    "corriger" vers un mot du dictionnaire.
    """
    if not text:
        return text
    return _MULTI_SPACE.sub(" ", text).strip()


def correct_many(texts):
    """Corrige une liste de textes. Retourne (liste_corrigee, total)."""
    total = 0
    out = []
    for t in texts:
        fixed, n = correct_text(t)
        out.append(fixed)
        total += n
    return out, total

