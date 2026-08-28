# -*- coding: utf-8 -*-
"""Anti-regression : aucune chaîne visible dans l'interface ne doit contenir
un mot du dictionnaire français privé de ses accents (ex. "genere" au lieu
de "généré"). Utilise le dictionnaire français de `pyspellchecker`, déjà une
dépendance du projet.

Le test se limite volontairement aux chaînes réellement affichées à
l'utilisateur (arguments des appels `st.*` dans `app.py`, et libellés des
styles/conseils dans `utils/`), pour éviter les faux positifs sur les
docstrings, commentaires et clés internes.
"""

import ast
import re
import unicodedata
from pathlib import Path

from spellchecker import SpellChecker

ROOT = Path(__file__).resolve().parents[1]

WORD_RE = re.compile(r"[a-zàâäéèêëïîôöùûüçñ]+", re.IGNORECASE)

# Mots ambigus/faux positifs connus (sigles, variables techniques...) à ignorer.
IGNORE = {"cv", "ats", "docx", "url", "xml", "html", "css", "sql", "aere"}


def _strip_accents(word: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", word) if unicodedata.category(c) != "Mn"
    )


def _build_unaccented_lookup() -> dict:
    """Retourne {forme_sans_accent: mot_accentue} pour les mots dont la forme
    sans accent n'est PAS elle-meme un mot valide (evite les faux positifs
    comme "a"/"à" ou "ou"/"où")."""
    sp = SpellChecker(language="fr")
    dictionary = set(sp.word_frequency.dictionary.keys())
    lookup = {}
    for w in dictionary:
        stripped = _strip_accents(w)
        if stripped != w and stripped not in dictionary:
            lookup.setdefault(stripped, w)
    return lookup


def _find_offenders(strings, lookup):
    offenders = []
    for literal in strings:
        for match in WORD_RE.finditer(literal):
            word = match.group(0).lower()
            if len(word) < 4 or word in IGNORE:
                continue
            if word in lookup:
                offenders.append((word, lookup[word], literal.strip()[:80]))
    return offenders


def _assert_no_offenders(strings, label, lookup):
    offenders = _find_offenders(strings, lookup)
    assert not offenders, (
        f"Mots sans accent detectes dans {label} : "
        + "; ".join(
            f"'{w}' (devrait etre '{correct}') dans « {ctx} »"
            for w, correct, ctx in offenders
        )
    )


def _literal_text_parts(node):
    """Retourne les segments de texte litteral d'une expression (chaîne
    simple ou f-string), en ignorant les sous-expressions ``{...}`` d'un
    f-string (variables, clés de dict, etc., qui ne sont pas du texte
    d'interface)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                yield value.value
    elif isinstance(node, ast.BinOp):
        yield from _literal_text_parts(node.left)
        yield from _literal_text_parts(node.right)


def _streamlit_ui_strings(path: Path):
    """Extrait les chaînes passées en argument aux appels `st.*` (texte
    réellement affiché à l'utilisateur)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_st_call = (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "st"
        )
        if not is_st_call:
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            yield from _literal_text_parts(arg)


def test_app_streamlit_strings_have_accents():
    lookup = _build_unaccented_lookup()
    strings = list(_streamlit_ui_strings(ROOT / "app.py"))
    assert strings, "Aucune chaine st.* trouvee : le test ne verifie rien."
    _assert_no_offenders(strings, "app.py", lookup)


def test_reformat_style_labels_have_accents():
    lookup = _build_unaccented_lookup()
    from utils.reformat import STYLES

    strings = []
    for style in STYLES:
        strings.append(style["label"])
        strings.append(style["description"])
    _assert_no_offenders(strings, "utils/reformat.py (STYLES)", lookup)


def test_cv_review_tips_have_accents():
    lookup = _build_unaccented_lookup()
    from utils.cv_review import review

    # Un CV pauvre declenche tous les conseils possibles.
    bullets = ["A fait des choses.", "A participe a un projet."]
    result = review(profile_text="Passionne dynamique", bullets=bullets)
    strings = []
    for tip in result["tips"]:
        strings.append(tip["type"])
        strings.append(tip["msg"])
    _assert_no_offenders(strings, "utils/cv_review.py (tips)", lookup)
