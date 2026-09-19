# -*- coding: utf-8 -*-
"""CV ATS Optimizer - application Streamlit.

Déposez votre CV (.docx ou .pdf), collez l'offre d'emploi et saisissez le
nom de l'entreprise : l'application analyse la compatibilité ATS (hors
ligne), récupère le logo de l'entreprise pour appliquer sa charte graphique,
et vous rend un CV prêt à envoyer.

Lancement :  streamlit run app.py
"""

import io
import hashlib

import streamlit as st

from utils import ats
from utils.colors import fetch_logo, brand_colors, build_palette, contrast_ratio
from utils.docx_tools import (
    read_text,
    detect_accent_colors,
    build_color_mapping,
    recolor,
    extract_structure,
    apply_rewrites,
    assess_format,
)
from utils import tailor
from utils import cv_review
from utils import corrector
from utils import reformat

st.set_page_config(page_title="CV ATS Optimizer", layout="wide")


def hex_swatch(hx):
    return (
        f'<span style="display:inline-block;width:18px;height:18px;'
        f'border-radius:4px;background:#{hx};border:1px solid #ccc;'
        f'vertical-align:middle;margin-right:6px"></span>#{hx}'
    )


def score_color(score):
    if score >= 75:
        return "#1a9850"
    if score >= 50:
        return "#f0a202"
    return "#d73027"


# --------------------------------------------------------------------------- #
# En-tête
# --------------------------------------------------------------------------- #
st.title("CV ATS Optimizer")
st.caption(
    "Vérifiez que votre CV passe les filtres automatiques, et repérez ce qui "
    "manque par rapport à l'offre. Tout est analysé sur votre machine."
)

with st.expander("Comment ça marche ?", expanded=False):
    st.markdown(
        "1. **Déposez votre CV** (.docx ou .pdf).\n"
        "2. **Collez l'offre d'emploi** : l'application extrait les mots-clés "
        "attendus par l'ATS et vérifie s'ils figurent dans votre CV.\n"
        "3. **Saisissez le nom de l'entreprise** (ou l'URL de son site) : "
        "l'application cherche automatiquement le logo et en déduit les "
        "couleurs de marque.\n"
        "4. **Téléchargez** votre CV recoloré et enrichi des mots-clés "
        "manquants."
    )

# --------------------------------------------------------------------------- #
# Entrees
# --------------------------------------------------------------------------- #
col1, col2 = st.columns(2)
with col1:
    cv_file = st.file_uploader("Votre CV (.docx ou .pdf)", type=["docx", "pdf"])
    company = st.text_input(
        "Entreprise ou adresse du site",
        placeholder="ex : Cegedim  ou  https://www.cegedim.fr",
    )
with col2:
    offer_text = st.text_area(
        "Offre d'emploi (copier/coller)",
        height=220,
        placeholder="Collez ici le texte complet de l'annonce...",
    )

run = st.button("Analyser le CV", type="primary", use_container_width=True)

# --------------------------------------------------------------------------- #
# Traitement
# --------------------------------------------------------------------------- #
if run:
    if not cv_file:
        st.error("Veuillez déposer votre CV (.docx ou .pdf).")
        st.stop()
    if not offer_text.strip():
        st.error("Veuillez coller le texte de l'offre d'emploi.")
        st.stop()

    cv_bytes = cv_file.read()

    try:
        cv_text = read_text(cv_bytes)
    except Exception as exc:  # fichier docx invalide / corrompu
        st.error(f"Impossible de lire le CV : {exc}")
        st.stop()

    fmt = assess_format(cv_bytes)
    if fmt["malformed"]:
        # CV trop mal structure pour une analyse fiable : on propose un
        # reformattage intelligent plutot que de lancer l'analyse/amelioration.
        st.session_state["malformed_cv"] = {
            "cv_bytes": cv_bytes,
            "offer_text": offer_text,
            "company": company,
            "reasons": fmt["reasons"],
        }
        st.session_state.pop("reformatted", None)
        st.session_state.pop("result", None)
    else:
        result = ats.analyze(cv_text, offer_text)
        st.session_state["result"] = result
        st.session_state["cv_bytes"] = cv_bytes
        st.session_state["cv_text"] = cv_text
        st.session_state["offer_text"] = offer_text
        st.session_state["company"] = company
        st.session_state.pop("malformed_cv", None)
        st.session_state.pop("reformatted", None)

# --------------------------------------------------------------------------- #
# CV malformaté : proposition de styles + reformattage intelligent
# --------------------------------------------------------------------------- #
if "malformed_cv" in st.session_state:
    mc = st.session_state["malformed_cv"]

    st.divider()
    st.warning(
        "**Votre CV semble difficile à analyser automatiquement en l'état** "
        "(" + " ".join(mc["reasons"]) + ") Plutôt que de lancer une analyse ou "
        "une amélioration peu fiable, choisissez un style ci-dessous : "
        "l'application **reformate intelligemment** votre CV (rubriques "
        "détectées automatiquement, même sans intitulé standard) et **corrige "
        "l'orthographe, la grammaire et le vocabulaire**."
    )

    style_options = {s["key"]: s for s in reformat.STYLES}
    style_key = st.radio(
        "Choisissez un style de mise en forme",
        options=list(style_options.keys()),
        format_func=lambda k: style_options[k]["label"],
        horizontal=True,
        key="reformat_style",
    )
    st.caption(style_options[style_key]["description"])

    if st.button("Reformater le CV", type="primary", use_container_width=True):
        data = reformat.parse_cv(mc["cv_bytes"])
        out_bytes, n_corrections = reformat.build_docx(
            data, style_key=style_key, correct=True
        )
        st.session_state["reformatted"] = {
            "bytes": out_bytes,
            "corrections": n_corrections,
            "company": mc["company"],
            "offer_text": mc["offer_text"],
        }

    if "reformatted" in st.session_state:
        rf = st.session_state["reformatted"]
        st.success("CV reformaté avec succès.")
        st.info(
            f"{rf['corrections']} amélioration(s) d'orthographe, de "
            "grammaire ou de vocabulaire ont été appliquées automatiquement."
        )
        st.download_button(
            "Télécharger le CV reformaté (.docx)",
            data=rf["bytes"],
            file_name="CV_reformate.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        if st.button(
            "Continuer vers l'analyse ATS avec ce CV reformaté",
            use_container_width=True,
        ):
            new_text = read_text(rf["bytes"])
            result = ats.analyze(new_text, rf["offer_text"])
            st.session_state["result"] = result
            st.session_state["cv_bytes"] = rf["bytes"]
            st.session_state["cv_text"] = new_text
            st.session_state["offer_text"] = rf["offer_text"]
            st.session_state["company"] = rf["company"]
            st.session_state.pop("malformed_cv", None)
            st.session_state.pop("reformatted", None)
            st.rerun()
    st.stop()

# --------------------------------------------------------------------------- #
# Résultats (regroupés en onglets pour limiter le défilement)
# --------------------------------------------------------------------------- #
if "result" in st.session_state:
    result = st.session_state["result"]
    cv_bytes = st.session_state["cv_bytes"]
    cv_text = st.session_state.get("cv_text", "")
    offer_text = st.session_state.get("offer_text", offer_text)
    company = st.session_state.get("company", "")

    structure = extract_structure(cv_bytes)
    present_terms = [t for t, _c, _s in result["present"]]
    missing_terms_all = [t for t, _c, _s in result["missing"]]
    missing_terms = missing_terms_all
    offer_terms = [t for t, _c, _s in result["keywords"]]
    suggested_title = tailor.extract_job_title(offer_text)
    bullets = structure["experience_bullets"]
    current_profile = structure["profile"]["text"] if structure["profile"] else ""
    accents = detect_accent_colors(cv_bytes)

    st.divider()

    # ---- Bandeau de score, toujours visible (pas besoin d'ouvrir un onglet) ----
    sc = result["score"]
    sem = result.get("semantic")
    hcol1, hcol2 = st.columns([1, 2])
    with hcol1:
        st.markdown(
            f'<div style="font-size:42px;font-weight:800;line-height:1;'
            f'color:{score_color(sc)}">{sc}%</div>'
            f'<div style="color:#666;font-size:13px">{len(result["present"])} '
            f'mots-clés sur {result["total"]}</div>',
            unsafe_allow_html=True,
        )
    with hcol2:
        st.progress(sc / 100)
        if sem is not None:
            with st.expander("Détails techniques"):
                st.caption(
                    f"Recouvrement de vocabulaire : **{sem}%** — indicatif, ne "
                    "remplace pas la couverture des mots-clés."
                )

    tab_kw, tab_rewrite, tab_quality, tab_export = st.tabs(
        ["Mots-clés", "Profil et expériences", "Qualité", "Couleurs et export"]
    )

    # ----------------------------------------------------------------------- #
    # Onglet 1 : mots-clés présents / manquants + sélection à intégrer
    # ----------------------------------------------------------------------- #
    with tab_kw:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Présents dans le CV")
            grp = ats.group_by_category(result["present"])
            if grp:
                for cat, terms in grp.items():
                    st.markdown(f"**{cat}** : " + ", ".join(sorted(set(terms))))
            else:
                st.info("Aucun mot-clé de l'offre détecté dans le CV.")
        with c2:
            st.markdown("#### Manquants (à ajouter)")
            grp_missing = ats.group_by_category(result["missing"])
            if grp_missing:
                for cat, terms in grp_missing.items():
                    st.markdown(f"**{cat}** : " + ", ".join(sorted(set(terms))))
            else:
                st.success("Tous les mots-clés détectés sont couverts.")

        st.divider()
        st.caption(
            "Les mots-clés cochés ne sont **pas** ajoutés en vrac en bas du CV "
            "(bourrage pénalisé par les recruteurs) : ils sont **tissés dans le "
            "profil et les puces réécrites** (onglet suivant), sur les "
            "expériences où ils sont pertinents."
        )
        to_add = st.multiselect(
            "Mots-clés manquants à ajouter au CV (choisissez ceux qui vous "
            "correspondent) :",
            options=missing_terms,
            default=[t for t, c, _s in result["missing"] if c != "Détecté"][:15],
            help="Ne cochez que les compétences que vous maîtrisez réellement.",
        )

    # Sélection des mots-clés à intégrer dans le profil (les cochés ci-dessus).
    profile_kw = to_add or missing_terms_all

    # ----------------------------------------------------------------------- #
    # Onglet 2 : réécriture automatique du Profil et des Expériences
    # ----------------------------------------------------------------------- #
    with tab_rewrite:
        st.caption(
            "Des textes adaptés à l'offre sont **générés automatiquement** "
            "(accroche orientée poste + puces en verbes d'action avec mots-clés "
            "tissés naturellement). Vous pouvez tout modifier ; **relisez** pour "
            "ne garder que ce que vous savez défendre."
        )

        tense_label = st.radio(
            "Style de verbe d'action pour les puces",
            options=["Participe passé (Développé...)", "Infinitif (Développer...)"],
            horizontal=True,
            key="tense_choice",
        )
        tense = "participe" if tense_label.startswith("Participe") else "infinitif"

        def _auto_generate():
            """Génère automatiquement le profil et toutes les puces adaptées."""
            st.session_state["profile_area"] = tailor.build_profile(
                current_profile, offer_text, present_terms, profile_kw,
                company=company, title=suggested_title,
            )
            # Répartit les mots-clés cochés sur les puces pertinentes : intégration
            # intelligente (recoupement lexical + cohérence de catégorie de
            # compétence), pas un ajout en vrac. Seuls les mots-clés sélectionnés
            # par l'utilisateur (qu'il maîtrise réellement) sont infiltrés.
            kw_map = tailor.assign_keywords_to_bullets(bullets, profile_kw)
            drafts = [
                tailor.rewrite_bullet(
                    b["text"], keywords=kw_map.get(b["index"], []), tense=tense,
                    seed=i,
                )
                for i, b in enumerate(bullets)
            ]
            # Diversifie les verbes d'attaque répétés (bonne pratique de rédaction).
            drafts = tailor.vary_leading_verbs(drafts, tense=tense)
            for b, draft in zip(bullets, drafts):
                st.session_state[f"bullet_{b['index']}"] = draft

        def _restore_original():
            st.session_state["profile_area"] = current_profile
            for b in bullets:
                st.session_state[f"bullet_{b['index']}"] = b["text"]

        # Régénère automatiquement quand le CV, l'offre, l'entreprise, le style ou
        # les mots-clés changent (aucun clic requis).
        token = hashlib.md5(
            (cv_text + "||" + offer_text + "||" + company + "||" + tense
             + "||" + ",".join(profile_kw)).encode("utf-8")
        ).hexdigest()
        if st.session_state.get("rw_token") != token:
            st.session_state["rw_token"] = token
            _auto_generate()

        cprof1, cprof2 = st.columns([1, 1])
        with cprof1:
            if st.button("Régénérer les textes", use_container_width=True):
                _auto_generate()
        with cprof2:
            if st.button("Restaurer l'original", use_container_width=True):
                _restore_original()

        # ---- Profil ----
        st.markdown("#### Profil / Accroche")
        if suggested_title:
            st.caption(f"Intitulé de poste détecté dans l'offre : **{suggested_title}**")
        st.text_area(
            "Profil (généré, modifiable)",
            height=150,
            key="profile_area",
        )
        new_profile = st.session_state.get("profile_area", "")
        if not structure["profile"]:
            st.info(
                "Section PROFIL non détectée automatiquement : le texte ci-dessus "
                "ne sera pas injecté. Vérifiez que votre CV comporte un titre "
                "'PROFIL'."
            )

        # ---- Expériences ----
        st.markdown("#### Puces d'expérience (verbes d'action + mots-clés)")
        bullet_edits = {}
        if not bullets:
            st.info("Aucune puce d'expérience détectée automatiquement.")
        else:
            st.caption(
                "Chaque puce a été réécrite automatiquement. Dépliez pour ajuster."
            )
            for b in bullets:
                idx = b["index"]
                draft_key = f"bullet_{idx}"
                if draft_key not in st.session_state:
                    st.session_state[draft_key] = b["text"]
                current_val = st.session_state.get(draft_key, b["text"])
                label = current_val[:80] + ("..." if len(current_val) > 80 else "")
                with st.expander(label):
                    st.caption(f"Original : {b['text']}")
                    st.text_area(
                        "Texte de la puce (modifiable)",
                        height=90,
                        key=draft_key,
                    )
                bullet_edits[idx] = st.session_state.get(draft_key, b["text"])

    # ----------------------------------------------------------------------- #
    # Onglet 3 : qualité rédactionnelle (bonnes pratiques recruteur)
    # ----------------------------------------------------------------------- #
    with tab_quality:
        st.caption(
            "Analyse fondée sur des critères éprouvés qui augmentent le taux de "
            "conversion en entretien : quantification (formule XYZ de Google), "
            "verbes d'action, variété, concision, formulations fortes, accroche "
            "sans cliché."
        )
        review = cv_review.review(new_profile, list(bullet_edits.values()))
        gs = review["global"]
        st.markdown(
            f'<div style="font-size:40px;font-weight:800;color:{score_color(gs)}">'
            f"{gs}/100</div>"
            f'<div style="color:#666">Score global de qualité rédactionnelle</div>',
            unsafe_allow_html=True,
        )
        st.progress(gs / 100)

        qc1, qc2 = st.columns(2)
        comp_items = list(review["components"].items())
        for i, (label, val) in enumerate(comp_items):
            col = qc1 if i % 2 == 0 else qc2
            with col:
                st.markdown(
                    f'<div style="margin-bottom:2px"><b>{label}</b> '
                    f'<span style="color:{score_color(val)};font-weight:700">{val}%</span></div>',
                    unsafe_allow_html=True,
                )
                st.progress(val / 100)

        if review["profile_readability"] is not None:
            st.caption(
                f"Lisibilité de l'accroche : {review['profile_readability']}/100 "
                "(plus haut = plus facile à lire)."
            )

        if review["tips"]:
            st.markdown("#### Conseils prioritaires")
            for tip in review["tips"]:
                badge = "[important]" if tip["level"] == "important" else "[suggestion]"
                with st.expander(f"{badge} {tip['type']}"):
                    st.markdown(tip["msg"])
                    for ex in tip.get("examples", []):
                        st.markdown(f"- {ex}")
        else:
            st.success("Excellent : aucun point bloquant détecté sur la rédaction.")

    # ----------------------------------------------------------------------- #
    # Onglet 4 : couleurs de l'entreprise + génération finale
    # ----------------------------------------------------------------------- #
    with tab_export:
        primary = st.session_state.get("primary", "25305F")
        secondary = st.session_state.get("secondary", "5487C6")

        if company.strip():
            with st.spinner(f"Recherche du logo de « {company} »..."):
                logo_bytes, source = fetch_logo(company)
            if logo_bytes:
                try:
                    primary, secondary, _palette = brand_colors(logo_bytes)
                    st.session_state["primary"] = primary
                    st.session_state["secondary"] = secondary
                    lc1, lc2 = st.columns([1, 3])
                    with lc1:
                        st.image(logo_bytes, caption=source, width=110)
                    with lc2:
                        st.markdown(
                            hex_swatch(primary) + " (primaire) &nbsp; "
                            + hex_swatch(secondary) + " (secondaire)",
                            unsafe_allow_html=True,
                        )
                except Exception:
                    st.warning("Logo trouvé mais couleurs illisibles. Ajustez-les ci-dessous.")
            else:
                st.warning(
                    "Logo introuvable automatiquement. Ajustez les couleurs "
                    "manuellement ci-dessous si besoin."
                )

        # Palette cohérente dérivée des couleurs de marque (calculée dès maintenant
        # pour que l'aperçu et la personnalisation restent en phase).
        palette = build_palette(primary, secondary)
        heading_c = palette["heading"]
        accent_c = palette["accent"]

        st.markdown(
            f"**Palette générée** — harmonie *{palette['name']}* : "
            + hex_swatch(heading_c) + " Titres &nbsp; "
            + hex_swatch(accent_c) + " Accent",
            unsafe_allow_html=True,
        )

        use_palette = st.checkbox(
            "Utiliser la palette cohérente générée (recommandé)", value=True,
            help="Décochez pour appliquer directement les couleurs brutes du logo.",
        )

        with st.expander("Personnaliser les couleurs manuellement"):
            a1, a2 = st.columns(2)
            with a1:
                primary = st.color_picker(
                    "Couleur primaire", f"#{primary}"
                ).lstrip("#").upper()
            with a2:
                secondary = st.color_picker(
                    "Couleur secondaire", f"#{secondary}"
                ).lstrip("#").upper()
            swatches = "".join(
                f'<div style="display:inline-block;text-align:center;margin-right:10px">'
                f'<div style="width:48px;height:48px;border-radius:8px;background:#{col};'
                f'border:1px solid #ccc"></div>'
                f'<div style="font-size:11px;margin-top:3px">{label}<br>#{col}</div></div>'
                for label, col in [
                    ("Titres", heading_c), ("Accent", accent_c),
                    ("Texte", palette["text"]), ("Gris", palette["muted"]),
                    ("Fond", palette["tint"]),
                ]
            )
            st.markdown(swatches, unsafe_allow_html=True)
            ratio_head = palette["contrast"]["heading_on_white"]
            ratio_acc = palette["contrast"]["accent_on_white"]
            st.caption(
                f"Contraste titres/blanc : **{ratio_head}** "
                f"({'conforme AA' if ratio_head >= 4.5 else 'faible'}) · "
                f"accent/blanc : **{ratio_acc}** "
                f"({'conforme' if ratio_acc >= 3 else 'faible'})"
            )

        if use_palette:
            target_primary, target_secondary = heading_c, accent_c
        else:
            target_primary, target_secondary = primary, secondary

    # ----------------------------------------------------------------------- #
    # Génération finale : toujours visible sous les onglets (action principale).
    # ----------------------------------------------------------------------- #
    st.divider()
    if st.button("Générer le CV optimisé", type="primary", use_container_width=True):
        out_bytes = cv_bytes

        # 0) Correction orthographe / grammaire / vocabulaire (par défaut,
        #    appliquée à tout CV avant toute autre transformation).
        corrections_count = 0
        corrected_profile = new_profile
        if new_profile.strip():
            corrected_profile, n_prof = corrector.correct_text(new_profile)
            corrections_count += n_prof
        corrected_bullet_edits = {}
        for idx, txt in bullet_edits.items():
            fixed_txt, n_b = corrector.correct_text(txt) if txt.strip() else (txt, 0)
            corrected_bullet_edits[idx] = fixed_txt
            corrections_count += n_b

        # 1) Réécriture Profil + Expériences (adaptation à l'offre).
        profile_changed = (
            structure["profile"] is not None
            and corrected_profile.strip()
            and corrected_profile.strip() != current_profile.strip()
        )
        original_bullets = {b["index"]: b["text"] for b in bullets}
        changed_bullets = {
            idx: txt
            for idx, txt in corrected_bullet_edits.items()
            if txt.strip() and txt.strip() != original_bullets.get(idx, "").strip()
        }

        if profile_changed or changed_bullets:
            out_bytes = apply_rewrites(
                out_bytes,
                new_profile=corrected_profile if profile_changed else None,
                bullet_edits=changed_bullets or None,
            )

        # 2) Recolorisation à la charte de l'entreprise.
        mapping = build_color_mapping(accents, target_primary, target_secondary)
        if mapping:
            out_bytes = recolor(out_bytes, mapping)

        st.success("CV optimisé généré avec succès.")
        if corrections_count:
            st.info(
                f"{corrections_count} amélioration(s) d'orthographe, de "
                "grammaire ou de vocabulaire ont été appliquées automatiquement."
            )
        else:
            st.caption("Aucune faute d'orthographe ou de grammaire détectée dans les textes générés.")

        # Vérifie quels mots-clés cochés sont réellement intégrés dans le
        # profil / les puces finales (pas de bourrage, intégration naturelle).
        final_text_norm = ats.normalize(
            (corrected_profile if profile_changed else current_profile) + " "
            + " ".join(corrected_bullet_edits.values())
        )
        not_integrated = [
            kw for kw in to_add if ats.normalize(kw) not in final_text_norm
        ]

        summary = []
        if profile_changed:
            summary.append("profil réécrit")
        if changed_bullets:
            summary.append(f"{len(changed_bullets)} puce(s) adaptée(s)")
        if to_add and not not_integrated:
            summary.append(f"{len(to_add)} mot(s)-clé(s) intégré(s) naturellement")
        if mapping:
            summary.append("couleurs mises à la charte")
        if summary:
            st.caption("Modifications : " + ", ".join(summary) + ".")
        if not_integrated:
            st.warning(
                "Ces mots-clés cochés n'ont pas trouvé de puce pertinente "
                "pour être intégrés automatiquement : "
                + ", ".join(not_integrated)
                + ". Ajoutez-les vous-même dans une expérience ou la section "
                "Compétences si vous les maîtrisez réellement (évitez le bourrage)."
            )
        if mapping:
            st.caption(
                "Recolorisation : "
                + ", ".join(f"#{o} → #{n}" for o, n in mapping.items())
            )
        st.download_button(
            "Télécharger le CV optimisé (.docx)",
            data=out_bytes,
            file_name="CV_optimise_ATS.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
