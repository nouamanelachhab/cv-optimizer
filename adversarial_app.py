# -*- coding: utf-8 -*-
"""ATS Red-Team CV Generator - application Streamlit.

Outil de test interne : injecte l'intégralité d'une offre d'emploi dans une
copie d'un CV (DOCX ou PDF), en utilisant l'une de plusieurs techniques
d'occultation de contenu, afin de vérifier si *votre propre* moteur ATS
extrait ce contenu caché.

Usage prévu : audit de votre pipeline d'extraction de texte. Ne jamais
envoyer les documents générés à un véritable employeur -- il s'agirait
alors d'une fraude au recrutement.

Lancement :  streamlit run adversarial_app.py
"""

from __future__ import annotations

import streamlit as st

from src.redteam import generator
from src.redteam.docx_to_pdf import ConversionUnavailableError
from src.redteam.techniques import TECHNIQUES, get_technique

st.set_page_config(page_title="ATS Red-Team CV Generator", layout="wide")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg-0: #0a0d12;
            --bg-1: #10141c;
            --panel: #12161f;
            --panel-alt: #161b26;
            --stroke: #232a38;
            --stroke-soft: #1b212c;
            --text: #e6e9ef;
            --muted: #8891a1;
            --accent: #39ff9e;
            --accent-dim: #1c8a58;
            --accent-soft: rgba(57, 255, 158, 0.1);
            --danger: #ff5470;
            --warning: #ffb454;
            --info: #4fd1ff;
            --mono: 'JetBrains Mono', 'Fira Code', monospace;
            --sans: 'Inter', -apple-system, sans-serif;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 15% 0%, rgba(57, 255, 158, 0.06) 0%, transparent 45%),
                radial-gradient(circle at 85% 100%, rgba(79, 209, 255, 0.05) 0%, transparent 45%),
                var(--bg-0);
            color: var(--text);
            font-family: var(--sans);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        div.block-container {
            max-width: 1160px;
            padding-top: 2rem;
            padding-left: 1.5rem;
            padding-right: 1.5rem;
            padding-bottom: 4rem;
        }

        /* ---- Hero ---- */
        .rt-hero {
            border: 1px solid var(--stroke);
            border-radius: 4px;
            background: linear-gradient(135deg, var(--bg-1) 0%, var(--panel) 100%);
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.4rem;
            position: relative;
            overflow: hidden;
        }
        .rt-hero::before {
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), var(--info), var(--accent));
        }
        .rt-kicker {
            font-family: var(--mono);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.6rem;
        }
        .rt-kicker::before {
            content: "●";
            font-size: 0.55rem;
            animation: rt-pulse 1.8s ease-in-out infinite;
        }
        @keyframes rt-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.25; }
        }
        .rt-title {
            font-family: var(--mono);
            font-size: clamp(1.6rem, 3vw, 2.4rem);
            font-weight: 800;
            letter-spacing: -0.02em;
            color: var(--text);
            margin: 0 0 0.5rem 0;
            line-height: 1.15;
        }
        .rt-title span { color: var(--accent); }
        .rt-desc {
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.55;
            max-width: 70ch;
            margin: 0;
        }
        .rt-alert {
            margin-top: 1.1rem;
            border: 1px solid rgba(255, 84, 112, 0.35);
            background: rgba(255, 84, 112, 0.08);
            border-left: 3px solid var(--danger);
            border-radius: 3px;
            padding: 0.7rem 0.9rem;
            font-size: 0.85rem;
            color: #ffcdd8;
            font-family: var(--sans);
        }
        .rt-alert b { color: var(--danger); }

        /* ---- Step section headers ---- */
        .rt-step {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 1.6rem 0 0.9rem 0;
        }
        .rt-step-num {
            font-family: var(--mono);
            font-weight: 800;
            font-size: 0.8rem;
            color: var(--bg-0);
            background: var(--accent);
            width: 26px;
            height: 26px;
            border-radius: 3px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .rt-step-label {
            font-family: var(--mono);
            font-weight: 700;
            font-size: 0.95rem;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            color: var(--text);
        }

        hr {
            border-color: var(--stroke) !important;
            margin: 1.4rem 0 !important;
        }

        .stCaption, [data-testid="stCaptionContainer"] {
            color: var(--muted) !important;
            font-size: 0.85rem !important;
        }

        /* ---- Inputs ---- */
        div[data-testid="stFileUploader"] section {
            background: var(--panel) !important;
            border: 1px dashed var(--stroke) !important;
            border-radius: 4px !important;
        }
        div[data-testid="stFileUploader"] section:hover {
            border-color: var(--accent-dim) !important;
        }

        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            background: var(--panel) !important;
            border: 1px solid var(--stroke) !important;
            border-radius: 3px !important;
            color: var(--text) !important;
            font-family: var(--sans) !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 1px var(--accent) !important;
        }
        label, .stSelectbox label, .stTextInput label, .stTextArea label {
            color: var(--muted) !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        section[data-testid="stSidebar"] {
            background: var(--bg-1);
            border-right: 1px solid var(--stroke);
        }

        /* ---- Buttons ---- */
        .stButton > button {
            border: 1px solid var(--accent);
            border-radius: 3px;
            background: transparent;
            color: var(--accent);
            font-family: var(--mono);
            font-weight: 700;
            font-size: 0.82rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 0.65rem 1rem;
            transition: all 0.15s ease;
        }
        .stButton > button:hover {
            background: var(--accent);
            color: var(--bg-0);
            box-shadow: 0 0 22px rgba(57, 255, 158, 0.35);
        }
        .stButton > button[kind="primary"] {
            background: var(--accent);
            color: var(--bg-0);
            box-shadow: 0 0 18px rgba(57, 255, 158, 0.25);
        }
        .stButton > button[kind="primary"]:hover {
            filter: brightness(1.1);
        }

        .stDownloadButton > button {
            border-radius: 3px;
            background: var(--info);
            border: 1px solid var(--info);
            color: var(--bg-0);
            font-family: var(--mono);
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            font-size: 0.82rem;
        }
        .stDownloadButton > button:hover {
            filter: brightness(1.1);
            box-shadow: 0 0 22px rgba(79, 209, 255, 0.3);
        }

        /* ---- Alerts ---- */
        div[data-testid="stAlert"] {
            border-radius: 3px;
            font-family: var(--sans);
            font-size: 0.88rem;
        }
        div[data-testid="stAlertContentError"], div[data-testid="stAlert"]:has(div[data-testid="stAlertContentError"]) {
            border: 1px solid rgba(255, 84, 112, 0.4) !important;
            background: rgba(255, 84, 112, 0.08) !important;
            border-left: 3px solid var(--danger) !important;
        }
        div[data-testid="stAlert"]:has(div[data-testid="stAlertContentSuccess"]) {
            border: 1px solid rgba(57, 255, 158, 0.4) !important;
            background: rgba(57, 255, 158, 0.07) !important;
            border-left: 3px solid var(--accent) !important;
        }
        div[data-testid="stAlert"]:has(div[data-testid="stAlertContentWarning"]) {
            border: 1px solid rgba(255, 180, 84, 0.4) !important;
            background: rgba(255, 180, 84, 0.07) !important;
            border-left: 3px solid var(--warning) !important;
        }
        div[data-testid="stAlert"]:has(div[data-testid="stAlertContentInfo"]) {
            border: 1px solid rgba(79, 209, 255, 0.4) !important;
            background: rgba(79, 209, 255, 0.07) !important;
            border-left: 3px solid var(--info) !important;
        }

        /* ---- Metrics ---- */
        [data-testid="stMetric"] {
            background: var(--panel);
            border: 1px solid var(--stroke);
            border-top: 2px solid var(--accent);
            border-radius: 3px;
            padding: 0.9rem 1rem;
        }
        [data-testid="stMetricLabel"] {
            font-family: var(--mono) !important;
            font-size: 0.7rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted) !important;
        }
        [data-testid="stMetricValue"] {
            font-family: var(--mono) !important;
            color: var(--accent) !important;
        }

        /* ---- Expander ---- */
        div[data-testid="stExpander"] {
            border: 1px solid var(--stroke) !important;
            border-radius: 3px !important;
            background: var(--panel) !important;
        }
        div[data-testid="stExpander"] summary {
            font-family: var(--mono) !important;
            font-size: 0.85rem !important;
        }

        img { border-radius: 3px !important; border: 1px solid var(--stroke); }

        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: var(--bg-0); }
        ::-webkit-scrollbar-thumb { background: var(--stroke); border-radius: 6px; }

        /* ---- Mobile ---- */
        @media (max-width: 768px) {
            div.block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
                padding-top: 1rem;
            }
            .rt-hero { padding: 1.2rem 1.1rem; }
            .rt-title { font-size: 1.5rem; }

            [data-testid="stHorizontalBlock"] {
                display: block !important;
            }
            [data-testid="stHorizontalBlock"] > div {
                width: 100% !important;
                margin-bottom: 0.75rem;
            }
            .stButton > button, .stDownloadButton > button {
                width: 100% !important;
            }
            .stTextInput input, .stTextArea textarea, div[data-testid="stFileUploader"] section {
                min-height: 46px;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def _step_header(number: str, label: str) -> None:
    st.markdown(
        f'<div class="rt-step"><div class="rt-step-num">{number}</div>'
        f'<div class="rt-step-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


_RELIABILITY_RENDER = {
    "reliable": ("success", "✅ Fiable"),
    "partial": ("warning", "⚠️ Partiellement fiable"),
}

_PDF_MIME = "application/pdf"


def _render_reliability(level: str, note: str) -> None:
    kind, label = _RELIABILITY_RENDER.get(level, ("info", level))
    renderer = getattr(st, kind)
    renderer(f"**{label}** — {note}")


def _run_generation(
    cv_bytes: bytes,
    cv_name: str,
    description: str,
    technique_id: str,
    company_name: str,
    offer_title: str,
) -> None:
    result = generator.generate(
        cv_bytes, cv_name, description, technique_id, company_name, offer_title
    )
    st.session_state["last_result"] = result
    st.session_state["generation_count"] = st.session_state.get("generation_count", 0) + 1


# --------------------------------------------------------------------------- #
# En-tête
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="rt-hero">
        <div class="rt-kicker">Internal Red-Team Tooling</div>
        <div class="rt-title">ATS <span>Red-Team</span> CV Generator</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Entrées : CV + offre
# --------------------------------------------------------------------------- #
col_cv, col_offer = st.columns(2)

with col_cv:
    _step_header("01", "CV source")
    cv_file = st.file_uploader(
        "Déposez votre CV (remplace le précédent)",
        type=["docx", "pdf"],
        key="cv_uploader",
    )
    if cv_file is not None:
        st.success(f"Fichier chargé : **{cv_file.name}** ({len(cv_file.getvalue()) / 1024:.1f} Ko)")
    else:
        st.info("Aucun CV chargé pour le moment.")

with col_offer:
    _step_header("02", "Offre cible")
    company_col, offer_col = st.columns(2)
    company_name = company_col.text_input(
        "Nom de l'entreprise",
        key="company_name",
        placeholder="Ex: Acme Corp",
    )
    offer_title = offer_col.text_input(
        "Intitulé de l'offre",
        key="offer_title",
        placeholder="Ex: Développeur Python Senior",
    )
    st.text_area(
        "Collez ici le texte complet de l'offre d'emploi",
        height=220,
        key="job_description",
        placeholder="Collez l'offre d'emploi complète ici...",
    )

    def _clear_description() -> None:
        st.session_state["job_description"] = ""

    st.button(
        "Vider la description",
        use_container_width=True,
        on_click=_clear_description,
    )

st.divider()

# --------------------------------------------------------------------------- #
# Technique d'injection
# --------------------------------------------------------------------------- #
_step_header("03", "Méthode d'injection")

technique_id = st.selectbox(
    "Choisissez la technique d'occultation à tester",
    options=[t.id for t in TECHNIQUES],
    format_func=lambda tid: get_technique(tid).label,
    key="technique_id",
)
technique = get_technique(technique_id)
st.caption(technique.description)

detected_format = None
if cv_file is not None:
    try:
        detected_format = generator.detect_format(cv_file.name)
    except ValueError:
        detected_format = None

_render_reliability(technique.reliability, technique.note)
if detected_format == "docx":
    st.caption(
        "Ce CV DOCX sera d'abord converti en PDF (mise en page préservée) "
        "avant l'injection, car le résultat est toujours un PDF."
    )

with st.expander("Fiabilité de toutes les techniques"):
    for t in TECHNIQUES:
        kind, label = _RELIABILITY_RENDER.get(t.reliability, ("info", t.reliability))
        st.markdown(f"**{t.label}** — {t.description}")
        st.markdown(f"- {label} — {t.note}")

st.divider()

# --------------------------------------------------------------------------- #
# Génération
# --------------------------------------------------------------------------- #
def _validate_inputs(cv_file, description: str, company_name: str, offer_title: str) -> str | None:
    if cv_file is None:
        return "Veuillez charger un CV avant de générer."
    if not description.strip():
        return "Veuillez coller une description de poste avant de générer."
    if not company_name.strip():
        return "Veuillez indiquer le nom de l'entreprise."
    if not offer_title.strip():
        return "Veuillez indiquer l'intitulé de l'offre."
    return None


def _generate_and_report(cv_file, description: str, technique_id: str, company_name: str, offer_title: str) -> bool:
    error = _validate_inputs(cv_file, description, company_name, offer_title)
    if error:
        st.error(error)
        return False
    try:
        _run_generation(
            cv_file.getvalue(), cv_file.name, description, technique_id, company_name, offer_title
        )
        return True
    except ConversionUnavailableError as exc:
        st.error(str(exc))
        return False
    except Exception as exc:  # fichier corrompu, format inattendu...
        st.error(f"Échec de la génération : {exc}")
        return False


if st.button("🎯 Generate adversarial CV", type="primary", use_container_width=True):
    _generate_and_report(
        cv_file, st.session_state.get("job_description", ""), technique_id, company_name, offer_title
    )

# --------------------------------------------------------------------------- #
# Résultat
# --------------------------------------------------------------------------- #
if "last_result" in st.session_state:
    result = st.session_state["last_result"]

    st.divider()
    _step_header("//", "Résultat généré")
    _render_reliability(result.reliability, result.reliability_note)

    if result.page_count_after == result.page_count_before:
        st.success(
            f"Nombre de pages inchangé : {result.page_count_before} "
            f"→ {result.page_count_after}. Aucune page ajoutée."
        )
    else:
        st.error(
            f"Le nombre de pages a changé ({result.page_count_before} → "
            f"{result.page_count_after}) — ce n'est pas censé arriver."
        )

    m1, m2, m3 = st.columns(3)
    m1.metric("Caractères injectés", result.injected_chars)
    m2.metric("Mots injectés", result.injected_words)
    m3.metric(
        "Récupérés par un extracteur naïf",
        result.naive_extract_injected_chars,
        help=(
            "Nombre de caractères supplémentaires qu'un extracteur de texte "
            "basique (lecture brute du corps du document) retrouve après "
            "injection. Sert de référence : comparez ce chiffre à ce que "
            "votre propre ATS extrait réellement."
        ),
    )

    st.caption(f"Fichier généré : **{result.filename}**")

    if result.preview_png:
        st.image(
            result.preview_png,
            caption="Aperçu réel (page 1) — doit être visuellement identique à l'original",
        )

    dl_col, again_col = st.columns(2)
    with dl_col:
        st.download_button(
            "⬇️ Download",
            data=result.output_bytes,
            file_name=result.filename,
            mime=_PDF_MIME,
            use_container_width=True,
        )
    with again_col:
        if st.button("🔁 Generate again", use_container_width=True):
            succeeded = _generate_and_report(
                cv_file, st.session_state.get("job_description", ""), technique_id, company_name, offer_title
            )
            if succeeded:
                st.rerun()

