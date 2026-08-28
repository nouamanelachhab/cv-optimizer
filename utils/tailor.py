# -*- coding: utf-8 -*-
"""Reecriture hors-ligne du Profil et des Experiences pour coller a l'offre.

Aucune IA payante : on s'appuie sur des modeles (templates) alimentes par les
mots-cles reellement extraits de l'offre et par les informations deja presentes
dans le CV (annees d'experience, metier). L'utilisateur relit et ajuste toujours
le texte genere : c'est un assistant, pas un generateur automatique aveugle.
"""

import re

from .ats import normalize
from .skills_data import all_skills, category_of

# Mots indiquant un intitule de poste dans une offre.
TITLE_HINTS = [
    "consultant", "consultante", "developpeur", "developpeuse", "ingenieur",
    "ingenieure", "technicien", "technicienne", "analyste", "chef de projet",
    "cheffe de projet", "administrateur", "administratrice", "architecte",
    "responsable", "charge", "chargee", "lead", "expert", "experte",
    "manager", "gestionnaire", "concepteur", "integrateur",
]


def extract_job_title(offer_text):
    """Deduit l'intitule du poste depuis l'offre.

    Priorite au motif "... (H/F)". A defaut, premiere phrase courte contenant
    un mot d'intitule.
    """
    if not offer_text:
        return ""

    # 1) Motif "Intitule (H/F)" ou "Intitule (F/H)" ou "H/F/X".
    m = re.search(
        r"([A-Za-zÀ-ÿ][\wÀ-ÿ'\-&/()\s]{3,70}?)\s*\(?\s*[HF]\s*/\s*[HFX](?:\s*/\s*X)?\s*\)?",
        offer_text,
    )
    if m:
        title = _clean_title(m.group(1))
        if title:
            return title

    # 2) Ligne contenant un mot d'intitule.
    for line in offer_text.splitlines():
        low = normalize(line)
        if any(h in low for h in TITLE_HINTS) and 3 <= len(line.split()) <= 12:
            title = _clean_title(line)
            if title:
                return title

    return ""


def _clean_title(text):
    text = re.sub(r"\(?\s*[HF]\s*/\s*[HFX](?:\s*/\s*X)?\s*\)?", "", text)
    # Retire les marques d'ecriture inclusive ('(e)', '.e)', '.e.s'...), qui ne
    # sont pas un champ a completer dans l'intitule du poste.
    text = re.sub(r"\(e\)|\.e\)|\.e\.s\)?", "", text)
    text = re.sub(r"\b(le|la|un|une|notre|poste|de|du|des|est|:)\b", " ",
                  text, flags=re.IGNORECASE)
    text = re.sub(r"[\"'«».,;:]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Coupe apres un separateur de sens.
    text = re.split(r"\s+(?:qui|dont|au sein|apres|garant|est)\b", text,
                    flags=re.IGNORECASE)[0].strip()
    words = text.split()
    if len(words) > 10:
        text = " ".join(words[:10])
    return text.strip(" -")


def extract_years(profile_text):
    """Recupere le nombre d'annees d'experience mentionne dans le profil."""
    m = re.search(r"(\d+)\s*ans?", profile_text or "", flags=re.IGNORECASE)
    return m.group(1) if m else None


def _identity_clause(profile_text):
    """Recupere la premiere proposition du profil (diplome / identite pro)."""
    if not profile_text:
        return "Professionnel de l'informatique"
    first = re.split(r"[.,;]", profile_text.strip())[0].strip()
    # Retire une eventuelle amorce type "je suis".
    first = re.sub(r"^(je suis|actuellement)\s+", "", first, flags=re.IGNORECASE)
    if len(first) < 8:
        return "Professionnel de l'informatique"
    return first[0].upper() + first[1:]


def _humanize_list(items):
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " et " + items[-1]


def build_profile(existing_profile, offer_text, present_kw, missing_kw,
                  company="", title=""):
    """Construit une accroche adaptee a l'offre (a relire par l'utilisateur).

    - present_kw / missing_kw : listes de termes (str) issues de l'analyse ATS.
    - On met en avant les competences deja possedees (present) et on exprime une
      appetence pour les competences cibles manquantes (missing) sans les
      affirmer comme acquises (honnetete vis-a-vis du recruteur et de l'entretien).

    Le style suit les bonnes pratiques de redaction de CV : accroche courte,
    orientee poste, mots-cles ATS integres naturellement.
    """
    title = title or extract_job_title(offer_text)
    years = extract_years(existing_profile)
    identity = _identity_clause(existing_profile)

    # Les langues (deja affichees dans l'en-tete du CV) n'ont pas leur place
    # dans la liste des competences maitrisees de l'accroche.
    strengths = _humanize_list(
        [k for k in present_kw if category_of(k) != "Langues"][:6]
    )
    aspirations = _humanize_list(missing_kw[:4])

    parts = [identity.rstrip(".") + "."]

    if years:
        exp_sentence = f"Fort de {years} ans d'expérience"
    else:
        exp_sentence = "Fort de mon expérience"
    if strengths:
        exp_sentence += f", je maîtrise {strengths}."
    else:
        exp_sentence += " en développement logiciel."
    parts.append(exp_sentence)

    if title:
        goal = f"Je souhaite mettre cette expertise au service du poste de {title}"
        if company.strip():
            company_name = company.strip()
            company_name = company_name[0].upper() + company_name[1:]
            goal += f" chez {company_name}"
        goal += "."
        parts.append(goal)

    if aspirations:
        parts.append(
            f"En montée en compétence sur {aspirations}, "
            "j'apporte rigueur, autonomie et sens du service client."
        )
    else:
        parts.append("Rigoureux, autonome et orienté qualité et service client.")

    return " ".join(parts)


def suggest_bullet_keywords(bullet_text, offer_terms, max_terms=3):
    """Retourne les mots-cles de l'offre pertinents et absents d'un bullet."""
    low = normalize(bullet_text)
    out = []
    for term in offer_terms:
        if normalize(term) not in low:
            out.append(term)
        if len(out) >= max_terms:
            break
    return out


# Mots trop generiques pour servir de lien de pertinence.
_LINK_STOP = {
    "pour", "les", "des", "une", "aux", "dans", "avec", "sur", "par", "plus",
    "moins", "entre", "chez", "cette", "leur", "leurs", "sont", "etre", "avoir",
    "gestion", "projet", "projets", "application", "applications", "outil",
    "outils", "donnees", "systeme", "systemes", "equipe", "equipes",
}


def _content_tokens(text):
    """Tokens signifiants (>= 4 lettres, hors mots generiques)."""
    low = normalize(text)
    words = re.findall(r"[a-z0-9]{4,}", low)
    return {w for w in words if w not in _LINK_STOP}


# --------------------------------------------------------------------------- #
# Reconnaissance des technos deja mentionnees dans une puce (par categorie)
# --------------------------------------------------------------------------- #
_ALL_SKILLS_NORM = [(normalize(s), s) for s in all_skills() if len(s) >= 2]
_ALL_SKILLS_NORM.sort(key=lambda x: len(x[0]), reverse=True)


def _known_terms_in_text(text):
    """Retourne les competences du lexique metier detectees dans `text`."""
    norm_text = normalize(text)
    found = []
    for norm_s, orig in _ALL_SKILLS_NORM:
        if re.search(r"(?<![a-z0-9])" + re.escape(norm_s) + r"(?![a-z0-9])", norm_text):
            found.append(orig)
    return found


def _bullet_categories(text):
    """Categories de competences deja presentes dans une puce (pour rapprocher
    thematiquement un mot-cle manquant d'une categorie similaire)."""
    return {category_of(t) for t in _known_terms_in_text(text)}


def assign_keywords_to_bullets(bullets, keywords, max_per_bullet=2):
    """Repartit intelligemment les mots-cles manquants sur les puces.

    Contrairement a un simple ajout en vrac, chaque mot-cle est **infiltre
    dans la puce la plus pertinente** :
      1. En priorite, la puce qui partage le plus de vocabulaire avec le
         mot-cle (recoupement lexical).
      2. A defaut, une puce qui mentionne deja une competence de la **meme
         categorie** (ex : un autre framework, un autre outil DevOps) pour
         garder une coherence thematique dans le detail du projet decrit.
      3. En dernier recours, les mots-cles restants sont repartis en
         round-robin sur les puces les plus riches en contenu technique
         (plutot que d'etre abandonnes et ajoutes en vrac ailleurs).
    - Un mot-cle deja present dans une puce est ignore.
    - Au plus `max_per_bullet` mots-cles ajoutes par puce (anti-bourrage).
    Retourne un dict {index_puce: [mots-cles]}.
    """
    assignments = {b["index"]: [] for b in bullets}
    if not bullets:
        return assignments

    bullet_tokens = {b["index"]: _content_tokens(b["text"]) for b in bullets}
    bullet_cats = {b["index"]: _bullet_categories(b["text"]) for b in bullets}
    all_text_norm = " || ".join(normalize(b["text"]) for b in bullets)

    unresolved = []
    for kw in keywords:
        kw_norm = normalize(kw)
        if not kw_norm or kw_norm in all_text_norm:
            continue  # deja present quelque part
        kw_tokens = _content_tokens(kw)
        kw_cat = category_of(kw)

        best_idx, best_score = None, 0
        for b in bullets:
            idx = b["index"]
            if len(assignments[idx]) >= max_per_bullet:
                continue
            score = len(kw_tokens & bullet_tokens[idx]) * 2
            if kw_cat != "Autre" and kw_cat in bullet_cats[idx]:
                score += 1  # coherence thematique (meme categorie de competence)
            if score > best_score:
                best_score, best_idx = score, idx
        if best_idx is not None and best_score > 0:
            assignments[best_idx].append(kw)
        else:
            unresolved.append(kw)

    # Repartition de secours : plutot que de laisser des mots-cles non
    # integres, on les place sur les puces au contenu le plus technique
    # (round-robin), dans la limite du quota anti-bourrage par puce.
    if unresolved:
        ranked = sorted(
            bullets, key=lambda b: len(bullet_tokens[b["index"]]), reverse=True
        )
        i = 0
        for kw in unresolved:
            for _ in range(len(ranked)):
                b = ranked[i % len(ranked)]
                i += 1
                idx = b["index"]
                if len(assignments[idx]) < max_per_bullet:
                    assignments[idx].append(kw)
                    break
    return assignments


# --------------------------------------------------------------------------- #
# Integration naturelle des mots-cles dans une puce (clause tissee, pas de
# liste entre parentheses) : le mot-cle est infiltre comme un detail concret
# de la mission/du projet decrit, avec une formulation qui varie selon la
# categorie de competence et selon la puce (evite la repetition mecanique).
# --------------------------------------------------------------------------- #
CATEGORY_CONNECTORS = {
    "Langages": ["en {t}", "à l'aide de {t}", "avec {t}"],
    "Frameworks & Bibliotheques": ["avec {t}", "en s'appuyant sur {t}", "via {t}"],
    "Bases de donnees": ["avec {t}", "en s'appuyant sur {t}", "sur {t}"],
    "DevOps & Cloud": ["sur {t}", "via {t}", "en s'appuyant sur {t}"],
    "Securite": ["en intégrant {t}", "en veillant à {t}", "conformément à {t}"],
    "Outils & Methodes": ["avec {t}", "selon une approche {t}", "via {t}"],
    "SIRH / Paie / RH": ["sur {t}", "avec {t}"],
    "Support & Maintenance": ["avec {t}", "via {t}"],
    "Soft skills": ["en faisant preuve de {t}"],
    "Langues": ["en {t}"],
    "Autre": ["avec {t}", "incluant {t}"],
}


def _group_keywords_by_category(keywords):
    groups = {}
    for kw in keywords:
        groups.setdefault(category_of(kw), []).append(kw)
    return groups


def enrich_bullet(bullet_text, keywords, seed=0):
    """Tisse naturellement des mots-cles dans une puce, comme un detail concret
    du projet/de la mission decrite (et non une liste entre parentheses).

    Ex : "Developpement d'une API de gestion des commandes." ->
         "Developpement d'une API de gestion des commandes, avec Node.js et
         PostgreSQL, en s'appuyant sur Docker."

    `seed` fait varier la formulation (connecteur) d'une puce a l'autre pour
    eviter un rendu mecanique/repetitif.
    """
    keywords = [k for k in keywords if normalize(k) not in normalize(bullet_text)]
    if not keywords:
        return bullet_text

    base = bullet_text.rstrip()
    trailing = ""
    while base and base[-1] in ".;":
        trailing = base[-1] + trailing
        base = base[:-1].rstrip()

    groups = _group_keywords_by_category(keywords)
    clauses = []
    used_templates = set()
    for i, (cat, terms) in enumerate(groups.items()):
        connectors = CATEGORY_CONNECTORS.get(cat, CATEGORY_CONNECTORS["Autre"])
        template = next(
            (connectors[(seed + i + off) % len(connectors)]
             for off in range(len(connectors))
             if connectors[(seed + i + off) % len(connectors)] not in used_templates),
            connectors[(seed + i) % len(connectors)],
        )
        used_templates.add(template)
        clauses.append(template.format(t=_humanize_list(terms)))
    return f"{base}, {', '.join(clauses)}{trailing or '.'}"


# --------------------------------------------------------------------------- #
# Reecriture par verbe d'action
# --------------------------------------------------------------------------- #
# Correspondance nom -> verbe (participe passe, infinitif). L'accent porte sur
# des verbes d'action forts, valorises par les recruteurs et les ATS.
NOUN_TO_VERB = {
    "developpement": ("Developpe", "Developper"),
    "conception": ("Concu", "Concevoir"),
    "creation": ("Cree", "Creer"),
    "integration": ("Integre", "Integrer"),
    "maintenance": ("Maintenu", "Maintenir"),
    "gestion": ("Gere", "Gerer"),
    "mise en place": ("Mis en place", "Mettre en place"),
    "mise en oeuvre": ("Mis en oeuvre", "Mettre en oeuvre"),
    "mise en production": ("Mis en production", "Mettre en production"),
    "optimisation": ("Optimise", "Optimiser"),
    "automatisation": ("Automatise", "Automatiser"),
    "harmonisation": ("Harmonise", "Harmoniser"),
    "fiabilisation": ("Fiabilise", "Fiabiliser"),
    "amelioration": ("Ameliore", "Ameliorer"),
    "reduction": ("Reduit", "Reduire"),
    "analyse": ("Analyse", "Analyser"),
    "livraison": ("Livre", "Livrer"),
    "deploiement": ("Deploye", "Deployer"),
    "supervision": ("Supervise", "Superviser"),
    "support": ("Assure le support", "Assurer le support"),
    "suivi": ("Assure le suivi", "Assurer le suivi"),
    "pilotage": ("Pilote", "Piloter"),
    "gouvernance": ("Assure la gouvernance", "Assurer la gouvernance"),
    "parametrage": ("Parametre", "Parametrer"),
    "administration": ("Administre", "Administrer"),
    "migration": ("Migre", "Migrer"),
    "refonte": ("Refondu", "Refondre"),
    "coordination": ("Coordonne", "Coordonner"),
    "mise a jour": ("Mis a jour", "Mettre a jour"),
    "test": ("Teste", "Tester"),
    "tests": ("Teste", "Tester"),
    "recette": ("Recette", "Recetter"),
    "correction": ("Corrige", "Corriger"),
    "resolution": ("Resolu", "Resoudre"),
    "traitement": ("Traite", "Traiter"),
    "exports": ("Genere", "Generer"),
    "export": ("Genere", "Generer"),
    "cadrage": ("Cadre", "Cadrer"),
    "redaction": ("Redige", "Rediger"),
    "formation": ("Forme", "Former"),
    "accompagnement": ("Accompagne", "Accompagner"),
    "assistance": ("Assure l'assistance", "Assurer l'assistance"),
}

# Connecteurs a nettoyer apres le nom converti ("Developpement d'une" -> "une").
_CONNECTORS = [
    (r"^d'", ""),
    (r"^de\s+la\s+", "la "),
    (r"^de\s+l'", "l'"),
    (r"^des\s+", "des "),
    (r"^du\s+", "le "),
    (r"^de\s+", ""),
]

# Verbes d'action forts proposes comme banque d'idees.
ACTION_VERBS = [
    "Concevoir", "Developper", "Deployer", "Optimiser", "Automatiser",
    "Piloter", "Coordonner", "Analyser", "Integrer", "Maintenir",
    "Fiabiliser", "Ameliorer", "Reduire", "Livrer", "Superviser",
    "Parametrer", "Migrer", "Refondre", "Resoudre", "Accompagner",
]


def _strip_leading_connector(rest):
    low = rest.lstrip()
    for pattern, repl in _CONNECTORS:
        new = re.sub(pattern, repl, low, flags=re.IGNORECASE)
        if new != low:
            return new.strip()
    return low.strip()


def _restore_accents_hint(verb):
    """Ajoute les accents usuels sur les verbes convertis (affichage FR)."""
    fixes = {
        "Developpe": "Développé", "Developper": "Développer",
        "Concu": "Conçu", "Concevoir": "Concevoir",
        "Cree": "Créé", "Creer": "Créer",
        "Integre": "Intégré", "Integrer": "Intégrer",
        "Gere": "Géré", "Gerer": "Gérer",
        "Optimise": "Optimisé", "Optimiser": "Optimiser",
        "Automatise": "Automatisé", "Automatiser": "Automatiser",
        "Harmonise": "Harmonisé", "Harmoniser": "Harmoniser",
        "Fiabilise": "Fiabilisé", "Fiabiliser": "Fiabiliser",
        "Ameliore": "Amélioré", "Ameliorer": "Améliorer",
        "Reduit": "Réduit", "Reduire": "Réduire",
        "Analyse": "Analysé", "Analyser": "Analyser",
        "Livre": "Livré", "Livrer": "Livrer",
        "Deploye": "Déployé", "Deployer": "Déployer",
        "Supervise": "Supervisé", "Superviser": "Superviser",
        "Pilote": "Piloté", "Piloter": "Piloter",
        "Parametre": "Paramétré", "Parametrer": "Paramétrer",
        "Administre": "Administré", "Administrer": "Administrer",
        "Migre": "Migré", "Migrer": "Migrer",
        "Refondu": "Refondu", "Refondre": "Refondre",
        "Coordonne": "Coordonné", "Coordonner": "Coordonner",
        "Teste": "Testé", "Tester": "Tester",
        "Corrige": "Corrigé", "Corriger": "Corriger",
        "Resolu": "Résolu", "Resoudre": "Résoudre",
        "Traite": "Traité", "Traiter": "Traiter",
        "Genere": "Généré", "Generer": "Générer",
        "Cadre": "Cadré", "Cadrer": "Cadrer",
        "Redige": "Rédigé", "Rediger": "Rédiger",
        "Forme": "Formé", "Former": "Former",
        "Accompagne": "Accompagné", "Accompagner": "Accompagner",
        "Assure le support": "Assuré le support",
        "Assurer le support": "Assurer le support",
        "Assure le suivi": "Assuré le suivi",
        "Assurer le suivi": "Assurer le suivi",
        "Assure la gouvernance": "Assuré la gouvernance",
        "Assurer la gouvernance": "Assurer la gouvernance",
        "Assure l'assistance": "Assuré l'assistance",
        "Assurer l'assistance": "Assurer l'assistance",
        # Synonymes de variete des verbes.
        "Realise": "Réalisé", "Realiser": "Réaliser",
        "Implemente": "Implémenté", "Implementer": "Implémenter",
        "Bati": "Bâti", "Batir": "Bâtir",
        "Modelise": "Modélisé", "Modeliser": "Modéliser",
        "Architecture": "Architecturé", "Architecturer": "Architecturer",
        "Elabore": "Élaboré", "Elaborer": "Élaborer",
        "Accelere": "Accéléré", "Accelerer": "Accélérer",
        "Rationalise": "Rationalisé", "Rationaliser": "Rationaliser",
        "Renforce": "Renforcé", "Renforcer": "Renforcer",
        "Interface": "Interfacé", "Interfacer": "Interfacer",
        "Connecte": "Connecté", "Connecter": "Connecter",
        "Incorpore": "Incorporé", "Incorporer": "Incorporer",
        "Etudie": "Étudié", "Etudier": "Étudier",
        "Diagnostique": "Diagnostiqué", "Diagnostiquer": "Diagnostiquer",
        "Qualifie": "Qualifié", "Qualifier": "Qualifier",
        "Dirige": "Dirigé", "Diriger": "Diriger",
        "Orchestre": "Orchestré", "Orchestrer": "Orchestrer",
        "Anime": "Animé", "Animer": "Animer",
        "Encadre": "Encadré", "Encadrer": "Encadrer",
        "Suit": "Suivi", "Suivre": "Suivre",
        "Controle": "Contrôlé", "Controler": "Contrôler",
        "Installe": "Installé", "Installer": "Installer",
        "Generalise": "Généralisé", "Generaliser": "Généraliser",
        "Consolide": "Consolidé", "Consolider": "Consolider",
        "Fait evoluer": "Fait évoluer", "Faire evoluer": "Faire évoluer",
        "Fait progresser": "Fait progresser",
        "Faire progresser": "Faire progresser",
    }
    return fixes.get(verb, verb)


def to_action_verb(bullet_text, tense="participe"):
    """Reecrit une puce pour qu'elle commence par un verbe d'action.

    tense = "participe" (Developpe...) ou "infinitif" (Developper...).
    Convertit une tournure nominale ("Developpement d'une API...") en tournure
    verbale ("Developpe une API..."). Traite la premiere proposition ; le reste
    (apres ';') est conserve tel quel. Si aucun nom connu n'est detecte, le
    texte est renvoye inchange.
    """
    if not bullet_text or not bullet_text.strip():
        return bullet_text

    text = bullet_text.strip()
    # Separe la premiere proposition du reste (apres ';').
    if ";" in text:
        head, sep, tail = text.partition(";")
    else:
        head, sep, tail = text, "", ""

    head_stripped = head.strip()
    low = normalize(head_stripped)

    # Cherche le nom d'action en tete (le plus long d'abord).
    chosen = None
    for noun in sorted(NOUN_TO_VERB, key=len, reverse=True):
        if low.startswith(noun + " ") or low == noun:
            chosen = noun
            break
    if chosen is None:
        return bullet_text  # rien de reconnu : on ne force pas.

    idx = 0 if tense == "participe" else 1
    verb = _restore_accents_hint(NOUN_TO_VERB[chosen][idx])

    # Recupere ce qui suit le nom, dans le texte d'origine (avec accents).
    remainder = head_stripped[len(chosen):].strip()

    # Cas compose : "X et Y d'une application" -> "Verbe(X) et verbe(Y) ...".
    m = re.match(r"^et\s+([A-Za-zÀ-ÿ']+)\b(.*)$", remainder, flags=re.IGNORECASE)
    if m:
        second_noun = normalize(m.group(1))
        if second_noun in NOUN_TO_VERB:
            second_verb = _restore_accents_hint(NOUN_TO_VERB[second_noun][idx])
            verb = f"{verb} et {second_verb[0].lower() + second_verb[1:]}"
            remainder = m.group(2).strip()

    remainder = _strip_leading_connector(remainder)

    new_head = (verb + (" " + remainder if remainder else "")).strip()
    if sep:
        result = new_head + " ; " + tail.strip()
    else:
        result = new_head
    # Capitalise proprement.
    return result[0].upper() + result[1:] if result else bullet_text


def rewrite_bullet(bullet_text, keywords=None, tense="participe", seed=0):
    """Applique le verbe d'action a une puce.

    Les mots-cles ne sont plus tisses en fin de puce (cela produisait des
    ajouts hors sujet et repetitifs) : ils restent geres via la rubrique
    Competences.
    """
    return to_action_verb(bullet_text, tense=tense)


# --------------------------------------------------------------------------- #
# Variete des verbes d'action (eviter la repetition du meme verbe)
# --------------------------------------------------------------------------- #
# Les recruteurs et les guides de redaction (Harvard, Google/Laszlo Bock)
# recommandent de varier les verbes d'action : un CV qui commence dix puces par
# "Developpe" parait pauvre. On propose des synonymes forts, de sens proche.
VERB_SYNONYMS = {
    "developpe": ["Concu", "Realise", "Implemente", "Bati"],
    "developper": ["Concevoir", "Realiser", "Implementer", "Batir"],
    "concu": ["Developpe", "Modelise", "Architecture", "Elabore"],
    "concevoir": ["Developper", "Modeliser", "Architecturer", "Elaborer"],
    "cree": ["Concu", "Bati", "Elabore", "Mis en place"],
    "creer": ["Concevoir", "Batir", "Elaborer", "Mettre en place"],
    "gere": ["Pilote", "Administre", "Coordonne", "Supervise"],
    "gerer": ["Piloter", "Administrer", "Coordonner", "Superviser"],
    "maintenu": ["Fiabilise", "Supervise", "Fait evoluer", "Consolide"],
    "maintenir": ["Fiabiliser", "Superviser", "Faire evoluer", "Consolider"],
    "optimise": ["Ameliore", "Fiabilise", "Accelere", "Rationalise"],
    "optimiser": ["Ameliorer", "Fiabiliser", "Accelerer", "Rationaliser"],
    "ameliore": ["Optimise", "Renforce", "Fiabilise", "Fait progresser"],
    "ameliorer": ["Optimiser", "Renforcer", "Fiabiliser", "Faire progresser"],
    "integre": ["Interface", "Connecte", "Deploie", "Incorpore"],
    "integrer": ["Interfacer", "Connecter", "Deployer", "Incorporer"],
    "analyse": ["Etudie", "Diagnostique", "Cadre", "Qualifie"],
    "analyser": ["Etudier", "Diagnostiquer", "Cadrer", "Qualifier"],
    "pilote": ["Coordonne", "Dirige", "Orchestre", "Anime"],
    "piloter": ["Coordonner", "Diriger", "Orchestrer", "Animer"],
    "supervise": ["Encadre", "Pilote", "Suit", "Controle"],
    "superviser": ["Encadrer", "Piloter", "Suivre", "Controler"],
    "deploye": ["Livre", "Mis en production", "Installe", "Generalise"],
    "deployer": ["Livrer", "Mettre en production", "Installer", "Generaliser"],
}


def _first_word(text):
    m = re.match(r"^\s*([A-Za-zÀ-ÿ']+)", text or "")
    return m.group(1) if m else ""


def vary_leading_verbs(bullets, tense="participe"):
    """Diversifie les verbes d'attaque d'une liste de puces deja verbalisees.

    Parcourt les puces dans l'ordre : quand un verbe d'attaque a deja ete
    utilise, on tente de le remplacer par un synonyme fort non encore employe.
    Preserve la casse, la ponctuation et la suite de la puce.

    `bullets` : liste de chaines (texte des puces). Retourne une nouvelle liste.
    """
    used = set()
    out = []
    for text in bullets:
        if not text or not text.strip():
            out.append(text)
            continue
        first = _first_word(text)
        key = normalize(first)
        if not key:
            out.append(text)
            used.add(key)
            continue
        if key not in used:
            used.add(key)
            out.append(text)
            continue
        # Verbe deja utilise : cherche un synonyme libre.
        replaced = None
        for syn in VERB_SYNONYMS.get(key, []):
            if normalize(syn) not in used:
                replaced = _restore_accents_hint(syn)
                break
        if replaced is None:
            out.append(text)  # pas d'alternative : on garde tel quel.
            continue
        used.add(normalize(replaced))
        rest = text[len(first):]
        new_text = replaced + rest
        out.append(new_text)
    return out

