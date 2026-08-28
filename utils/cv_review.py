# -*- coding: utf-8 -*-
"""Analyse qualite d'un CV selon les bonnes pratiques de recrutement.

S'appuie sur des criteres eprouves qui augmentent le taux de conversion en
entretien (references : formule XYZ de Google/Laszlo Bock, etude eye-tracking
des recruteurs, recommandations Harvard/HBR, standards ATS) :

  1. Quantification  : les puces avec des chiffres/metriques marquent davantage.
  2. Verbes d'action : commencer par un verbe fort, en voix active.
  3. Mots faibles    : eviter "responsable de", "participe a", "en charge de".
  4. Clic hes vides   : eviter "dynamique", "motive", "rigoureux" sans preuve.
  5. Concision       : puces de 1 a 2 lignes (ni trop courtes, ni trop longues).
  6. Variete des verbes : ne pas repeter le meme verbe d'action.
  7. Lisibilite      : mesuree avec textstat (formules de lisibilite).

Bibliotheques de recherche : textstat (lisibilite). Le reste repose sur des
regles linguistiques ciblees, robustes et hors-ligne.
"""

import re

from .ats import normalize

# Verbes d'action forts reconnus en tete de puce (normalises, sans accent).
STRONG_VERBS = {
    "developpe", "developper", "concu", "concevoir", "cree", "creer",
    "integre", "integrer", "maintenu", "maintenir", "gere", "gerer",
    "optimise", "optimiser", "automatise", "automatiser", "harmonise",
    "harmoniser", "fiabilise", "fiabiliser", "ameliore", "ameliorer",
    "reduit", "reduire", "analyse", "analyser", "livre", "livrer",
    "deploye", "deployer", "supervise", "superviser", "pilote", "piloter",
    "parametre", "parametrer", "administre", "administrer", "migre", "migrer",
    "refondu", "refondre", "coordonne", "coordonner", "teste", "tester",
    "corrige", "corriger", "resolu", "resoudre", "traite", "traiter",
    "genere", "generer", "cadre", "cadrer", "redige", "rediger", "forme",
    "former", "accompagne", "accompagner", "assure", "assurer", "mis",
    "mettre", "realise", "realiser", "implemente", "implementer", "concoit",
    "dirige", "diriger", "encadre", "encadrer", "negocie", "negocier",
    "lance", "lancer", "structure", "structurer", "modelise", "modeliser",
    "industrialise", "conduit", "conduire", "orchestre", "orchestrer",
}

# Tournures faibles a bannir -> suggestion de remplacement.
WEAK_PHRASES = {
    "responsable de": "Pilote / Dirige",
    "en charge de": "Gere / Pilote",
    "charge de": "Gere / Pilote",
    "participe a": "Contribue a / Realise",
    "participation a": "Contribution a / Realisation de",
    "aide a": "Soutient / Appuie",
    "travaille sur": "Realise / Developpe",
    "s'occupe de": "Gere / Assure",
    "mission de": "Realise",
    "amene a": "Realise",
    "diverses taches": "des livrables precis",
    "differentes taches": "des livrables precis",
}

# Cliches / buzzwords sans preuve (a etayer par un fait).
CLICHES = {
    "dynamique", "motive", "motivee", "rigoureux", "rigoureuse", "serieux",
    "serieuse", "autonome", "polyvalent", "polyvalente", "passionne",
    "passionnee", "force de proposition", "esprit d'equipe", "bon relationnel",
    "team player", "proactif", "proactive", "creatif", "creative",
}


def _split_sentences(text):
    return [s.strip() for s in re.split(r"[.;\n]", text) if s.strip()]


def has_number(text):
    """Vrai si la puce contient une metrique chiffree exploitable."""
    return bool(re.search(r"\d", text))


def starts_with_strong_verb(text):
    """Vrai si la puce commence par un verbe d'action fort."""
    m = re.match(r"\s*([A-Za-zÀ-ÿ']+)", text)
    if not m:
        return False
    return normalize(m.group(1)) in STRONG_VERBS


def find_weak_phrases(text):
    low = normalize(text)
    return [(w, repl) for w, repl in WEAK_PHRASES.items() if w in low]


def find_cliches(text):
    low = normalize(text)
    hits = []
    for c in CLICHES:
        if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", low):
            hits.append(c)
    return hits


def bullet_length_flag(text):
    """Retourne 'court', 'ok' ou 'long' selon le nombre de mots."""
    n = len(text.split())
    if n < 4:
        return "court"
    if n > 34:
        return "long"
    return "ok"


def readability(text):
    """Score de lisibilite 0-100 (plus haut = plus lisible) via textstat."""
    if not text or len(text.split()) < 5:
        return None
    try:
        import textstat
        textstat.set_lang("fr")
        score = textstat.flesch_reading_ease(text)
    except Exception:
        return None
    return max(0, min(100, round(score)))


def verb_variety(bullets):
    """Mesure la diversite des premiers verbes (0-100) + verbes repetes."""
    firsts = []
    for b in bullets:
        m = re.match(r"\s*([A-Za-zÀ-ÿ']+)", b)
        if m:
            firsts.append(normalize(m.group(1)))
    if not firsts:
        return 100, []
    from collections import Counter
    c = Counter(firsts)
    variety = round(100 * len(c) / len(firsts))
    repeated = [v for v, n in c.items() if n > 1 and v in STRONG_VERBS]
    return variety, repeated


def review(profile_text, bullets):
    """Analyse complete : retourne un score global et des conseils cibles.

    bullets : liste de chaines (texte des puces d'experience).
    """
    bullets = [b for b in bullets if b and b.strip()]
    n = len(bullets)

    quant = sum(1 for b in bullets if has_number(b))
    strong = sum(1 for b in bullets if starts_with_strong_verb(b))
    weak_hits = [(b, find_weak_phrases(b)) for b in bullets]
    weak_hits = [(b, w) for b, w in weak_hits if w]
    long_bullets = [b for b in bullets if bullet_length_flag(b) == "long"]
    variety, repeated = verb_variety(bullets)

    profile_cliches = find_cliches(profile_text) if profile_text else []
    profile_read = readability(profile_text) if profile_text else None

    quant_rate = round(100 * quant / n) if n else 0
    strong_rate = round(100 * strong / n) if n else 0

    # Score pondere (bonnes pratiques). Chaque critere sur 100.
    weak_penalty = min(100, len(weak_hits) * 20)
    long_penalty = min(100, len(long_bullets) * 15)
    cliche_penalty = min(100, len(profile_cliches) * 12)

    components = {
        "Quantification": quant_rate,
        "Verbes d'action": strong_rate,
        "Variete des verbes": variety,
        "Concision": max(0, 100 - long_penalty),
        "Formulations fortes": max(0, 100 - weak_penalty),
        "Accroche sans cliche": max(0, 100 - cliche_penalty),
    }
    weights = {
        "Quantification": 0.28,
        "Verbes d'action": 0.24,
        "Variete des verbes": 0.12,
        "Concision": 0.12,
        "Formulations fortes": 0.14,
        "Accroche sans cliche": 0.10,
    }
    global_score = round(sum(components[k] * weights[k] for k in components))

    # Conseils actionnables, priorisés.
    tips = []
    if quant_rate < 60:
        no_num = [b for b in bullets if not has_number(b)]
        tips.append({
            "type": "Quantification",
            "level": "important",
            "msg": (
                f"Seules {quant}/{n} puces contiennent un chiffre. Ajoutez des "
                "métriques (%, volumes, délais, gains) : les recruteurs "
                "retiennent l'impact mesurable."
            ),
            "examples": no_num[:3],
        })
    if strong_rate < 80:
        weakstart = [b for b in bullets if not starts_with_strong_verb(b)]
        tips.append({
            "type": "Verbes d'action",
            "level": "important",
            "msg": (
                "Commencez chaque puce par un verbe d'action fort (Développé, "
                "Piloté, Optimisé...). Utilisez le bouton de réécriture."
            ),
            "examples": weakstart[:3],
        })
    if weak_hits:
        tips.append({
            "type": "Formulations faibles",
            "level": "important",
            "msg": "Remplacez les tournures passives ou faibles par des verbes forts.",
            "examples": [
                f"« {b[:70]} » → éviter « {', '.join(w for w, _ in ws)} »"
                for b, ws in weak_hits[:3]
            ],
        })
    if repeated:
        tips.append({
            "type": "Variété des verbes",
            "level": "conseil",
            "msg": (
                "Variez les verbes répétés (" + ", ".join(repeated) + ") : "
                "utilisez des synonymes pour un rendu plus riche."
            ),
            "examples": [],
        })
    if long_bullets:
        tips.append({
            "type": "Concision",
            "level": "conseil",
            "msg": "Raccourcissez les puces trop longues (visez 1 à 2 lignes).",
            "examples": [b[:90] + "..." for b in long_bullets[:3]],
        })
    if profile_cliches:
        tips.append({
            "type": "Accroche",
            "level": "conseil",
            "msg": (
                "Votre accroche contient des mots passe-partout ("
                + ", ".join(profile_cliches)
                + "). Appuyez-les par un fait concret ou supprimez-les."
            ),
            "examples": [],
        })

    return {
        "global": global_score,
        "components": components,
        "quant_rate": quant_rate,
        "strong_rate": strong_rate,
        "variety": variety,
        "profile_readability": profile_read,
        "n_bullets": n,
        "tips": tips,
    }
