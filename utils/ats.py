# -*- coding: utf-8 -*-
"""Analyse ATS 100% hors-ligne.

Principe : les ATS (Applicant Tracking Systems) reposent essentiellement sur
la correspondance de mots-cles entre l'offre et le CV. Ce module :
  1. extrait les mots-cles pertinents d'une offre d'emploi ;
  2. verifie leur presence dans le CV ;
  3. calcule un score de correspondance et liste les mots-cles manquants.

Aucune connexion ni IA payante : tout est base sur un lexique metier + une
extraction lexicale (acronymes, termes techniques capitalises).
"""

import re
import unicodedata
from collections import Counter

from .skills_data import all_skills, category_of

# Mots vides francais/anglais a ignorer lors de l'extraction generique.
STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "a", "au",
    "aux", "en", "dans", "pour", "par", "sur", "avec", "sans", "sous", "ce",
    "cet", "cette", "ces", "son", "sa", "ses", "leur", "leurs", "nos", "vos",
    "notre", "votre", "est", "sont", "etre", "avoir", "vous", "nous", "ils",
    "elles", "il", "elle", "on", "qui", "que", "quoi", "dont", "ainsi", "plus",
    "moins", "tres", "aussi", "comme", "afin", "lors", "chez", "vers", "entre",
    "the", "and", "or", "of", "to", "in", "for", "with", "on", "at", "by",
    "an", "as", "is", "are", "be", "will", "your", "our", "you", "we", "this",
    "that", "from", "job", "poste", "mission", "missions", "profil", "cet",
    "notamment", "notre", "cette", "annee", "groupe", "equipe", "equipes",
    "solution", "solutions", "client", "clients", "entreprise", "entreprises",
}


def normalize(text):
    """Minuscule + suppression des accents pour une comparaison robuste."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Uniformise les espaces (retours a la ligne, tabulations) pour que les
    # termes en plusieurs mots soient reconnus meme a cheval sur deux lignes.
    text = re.sub(r"\s+", " ", text)
    # Recolle les espaces (normaux ou insecables) intercales entre deux
    # groupes de chiffres : Word insere souvent un separateur de milliers
    # (espace fine insecable) dans les nombres, ce qui casse la reconnaissance
    # de codes/normes ecrits sans espace dans l'offre (ex. "ISO 27 001" vs
    # "ISO 27001").
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    return text


def _boundary_present(needle_norm, haystack_norm):
    """Vrai si `needle_norm` apparait comme terme dans `haystack_norm`."""
    if not needle_norm:
        return False
    # Frontieres souples : caracteres non alphanumeriques autour du terme.
    pattern = r"(?<![a-z0-9])" + re.escape(needle_norm) + r"(?![a-z0-9])"
    return re.search(pattern, haystack_norm) is not None


# --------------------------------------------------------------------------- #
# Filtrage des sections institutionnelles d'une offre (non prescriptives)
# --------------------------------------------------------------------------- #
# Titres de rubrique a conserver (mots-cles prescriptifs attendus).
# Configurable : modifiable en place ou fourni via le parametre
# `included_titles` de `filter_institutional_sections`/`extract_offer_keywords`.
DEFAULT_INCLUDED_SECTION_TITLES = [
    "mission",
    "contexte",
    "responsabilites",
    "profil",
    "competences",
]

# Titres de rubrique institutionnels/non prescriptifs a ignorer (bruit pour
# l'extraction de mots-cles : ils ne decrivent pas le poste). Configurable de
# la meme facon que ci-dessus.
DEFAULT_EXCLUDED_SECTION_TITLES = [
    "pourquoi nous rejoindre",
    "notre engagement",
    "processus de selection",
    "a propos",
    "inclusion",
    "qui sommes nous",
    "presentation de l'entreprise",
    "notre entreprise",
]


def _normalize_title(line):
    """Normalise une ligne candidate a etre un titre de section : meme
    normalisation que `normalize()`, plus suppression de la ponctuation de
    titre (':', '?', tirets) pour comparer robustement aux listes
    configurees."""
    t = normalize(line)
    t = t.replace("-", " ")
    t = t.strip(" :?.#")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _matches_any_title(norm_line, titles):
    return any(title and title in norm_line for title in titles)


def filter_institutional_sections(offer_text, included_titles=None, excluded_titles=None):
    """Retire d'une offre les sections institutionnelles non prescriptives
    (presentation entreprise, avantages, processus de recrutement...) avant
    extraction des mots-cles, pour que les termes des sections utiles
    (mission, contexte, responsabilites, profil, competences) ressortent
    mieux.

    Le texte est decoupe par lignes ; une ligne courte (<=80 caracteres) dont
    la forme normalisee correspond a un titre de `excluded_titles` ouvre une
    section ignoree jusqu'au prochain titre reconnu (inclus ou exclu). Un
    titre non reconnu (ni inclus ni exclu) ne declenche aucune suppression :
    son contenu reste conserve par defaut, comme le contenu place avant le
    premier titre reconnu (souvent l'intitule de poste / l'accroche de
    mission).
    """
    included = [_normalize_title(t) for t in (included_titles or DEFAULT_INCLUDED_SECTION_TITLES)]
    excluded = [_normalize_title(t) for t in (excluded_titles or DEFAULT_EXCLUDED_SECTION_TITLES)]

    kept_lines = []
    dropping = False
    for line in offer_text.splitlines():
        norm_line = _normalize_title(line)
        if norm_line and len(line.strip()) <= 80:
            if _matches_any_title(norm_line, excluded):
                dropping = True
                continue
            if _matches_any_title(norm_line, included):
                dropping = False
                kept_lines.append(line)
                continue
        if not dropping:
            kept_lines.append(line)
    return "\n".join(kept_lines)


# --------------------------------------------------------------------------- #
# Correspondance floue (rapidfuzz) pour rattraper les variantes / fautes
# --------------------------------------------------------------------------- #
try:
    from rapidfuzz import fuzz as _rf_fuzz
    _HAS_RAPIDFUZZ = True
except Exception:  # pragma: no cover - repli si lib absente
    _HAS_RAPIDFUZZ = False


def _fuzzy_present(needle_norm, haystack_norm, threshold=88):
    """Vrai si le terme apparait de facon approximative dans le texte.

    Utilise rapidfuzz (algorithme de distance d'edition performant, issu de la
    recherche sur l'appariement de chaines) pour tolerer les variantes
    ("developpe"/"developpement") et les fautes de frappe. Ne s'applique qu'aux
    termes d'un seul mot suffisamment longs pour eviter les faux positifs.
    """
    if not _HAS_RAPIDFUZZ or not needle_norm or " " in needle_norm:
        return False
    if len(needle_norm) < 5:
        return False
    # Compare au meilleur token du texte (partial_ratio sur mots proches).
    best = 0
    nlen = len(needle_norm)
    for token in set(re.findall(r"[a-z0-9]{4,}", haystack_norm)):
        # Filtre rapide sur la longueur pour limiter les comparaisons.
        if abs(len(token) - nlen) > max(3, nlen // 2):
            continue
        r = _rf_fuzz.ratio(needle_norm, token)
        if r > best:
            best = r
            if best >= threshold:
                return True
    return False



def extract_offer_keywords(offer_text, max_generic=25, included_titles=None, excluded_titles=None):
    """Extrait les mots-cles d'une offre.

    Les sections institutionnelles non prescriptives (presentation
    entreprise, avantages, processus de recrutement...) sont retirees au
    prealable via `filter_institutional_sections` (listes de titres
    configurables via `included_titles`/`excluded_titles`).

    Retourne une liste de tuples (terme, categorie, source) ou source vaut
    'lexique' (haute confiance) ou 'detecte' (extraction generique).
    """
    offer_text = filter_institutional_sections(
        offer_text, included_titles=included_titles, excluded_titles=excluded_titles
    )
    offer_norm = normalize(offer_text)
    found = []
    seen = set()

    # 1) Termes du lexique metier presents dans l'offre.
    for skill in all_skills():
        skill_norm = normalize(skill)
        if _boundary_present(skill_norm, offer_norm):
            key = skill_norm
            if key not in seen:
                seen.add(key)
                found.append((skill, category_of(skill), "lexique"))

    # 2) Termes techniques capitalises avec symbole (C++, .NET, Node.js...).
    #    Les acronymes en majuscules ne sont plus detectes par la casse :
    #    un acronyme n'est retenu que s'il figure dans le lexique metier
    #    (utils/skills_data.py), traite au point 1 ci-dessus.
    generic_counter = Counter()
    raw_tokens = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\+\#\./-]{1,}", offer_text)
    for tok in raw_tokens:
        clean = tok.strip(".,;:()[]").strip()
        if len(clean) < 2:
            continue
        low = normalize(clean)
        if low in STOPWORDS or low in seen:
            continue
        is_capitalized_tech = (
            clean[0].isupper()
            and any(ch in clean for ch in "+#.")
        )
        if is_capitalized_tech:
            generic_counter[clean] += 1

    for term, _count in generic_counter.most_common(max_generic):
        low = normalize(term)
        if low not in seen:
            seen.add(low)
            found.append((term, "Détecté", "detecte"))

    return found


def analyze(cv_text, offer_text):
    """Compare le CV a l'offre et renvoie le detail de correspondance ATS."""
    cv_norm = normalize(cv_text)
    keywords = extract_offer_keywords(offer_text)

    present, missing = [], []
    for term, cat, source in keywords:
        term_norm = normalize(term)
        # Presence exacte OU approximative (variantes, fautes) via rapidfuzz.
        if _boundary_present(term_norm, cv_norm) or _fuzzy_present(term_norm, cv_norm):
            present.append((term, cat, source))
        else:
            missing.append((term, cat, source))

    total = len(keywords)
    score = round(100 * len(present) / total) if total else 0
    semantic = semantic_similarity(cv_text, offer_text)

    return {
        "score": score,
        "semantic": semantic,
        "total": total,
        "present": present,
        "missing": missing,
        "keywords": keywords,
    }


# --------------------------------------------------------------------------- #
# Similarite semantique (TF-IDF + cosinus, scikit-learn)
# --------------------------------------------------------------------------- #
_FR_EN_STOP = sorted(STOPWORDS)


def semantic_similarity(cv_text, offer_text):
    """Score 0-100 de proximite semantique globale CV <-> offre.

    Complemente la correspondance de mots-cles : deux textes peuvent partager
    peu de mots exacts mais couvrir le meme champ lexical. On vectorise en
    TF-IDF (avec bi-grammes) et on calcule la similarite cosinus, methode de
    reference en recherche d'information. Repli gracieux si scikit-learn absent.
    """
    if not cv_text or not offer_text:
        return 0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception:  # pragma: no cover
        return 0

    a, b = normalize(cv_text), normalize(offer_text)
    try:
        vect = TfidfVectorizer(
            stop_words=_FR_EN_STOP,
            ngram_range=(1, 2),
            min_df=1,
            token_pattern=r"[a-z0-9][a-z0-9\+\#\.]{1,}",
        )
        m = vect.fit_transform([a, b])
        sim = cosine_similarity(m[0], m[1])[0][0]
    except ValueError:
        return 0
    return int(round(max(0.0, min(1.0, sim)) * 100))



def group_by_category(items):
    """Regroupe une liste (terme, categorie, source) par categorie."""
    grouped = {}
    for term, cat, source in items:
        grouped.setdefault(cat, []).append(term)
    return grouped
