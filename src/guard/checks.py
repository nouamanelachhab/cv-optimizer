"""Blocking pre-write validation checks (guard).

Guard runs *after* render has produced candidate ``RenderedBlock`` instances
and *before* anything is written to a document. Every check here is
deterministic, offline, and does not rewrite text -- it only accepts or
rejects it.

G1-G3 are always active. G4-G7 need optional external assets/context
(a hunspell fr-FR dictionary, a language_tool_python server, the list of
ontology skill labels in play, and known proper nouns) -- when not supplied,
they gracefully report no findings rather than failing, per spec (G5 is
explicitly optional; G4/G6/G7 degrade the same way when their inputs are
unavailable, e.g. no local French dictionary bundled in this offline repo).
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

from src.guard.models import GuardFinding, Operation, RenderedBlock, Severity
from src.normalize import canonicalize


# --- G2: orphaned placeholder detection -------------------------------------

_PLACEHOLDER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\{[^{}]*\}"),  # {xxx}, {{xxx}}
    re.compile(r"<[^<>]{1,40}>"),  # <xxx>
    re.compile(r"\(e\)", re.IGNORECASE),  # unresolved gender suffix "(e)"
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bNone\b"),
    re.compile(r"\bnan\b", re.IGNORECASE),
    re.compile(r"%%[^%]*%%"),
]


def _diacritic_ratio(text: str) -> float:
    """Ratio of diacritical (combining) marks to letters in ``text``.

    Uses NFD decomposition + unicodedata categories only (no ``unidecode``,
    which per spec is confined to the ``normalize`` module).
    """
    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return 0.0
    decomposed = unicodedata.normalize("NFD", text)
    marks = sum(1 for ch in decomposed if unicodedata.category(ch) == "Mn")
    return marks / letters


def check_g1_integrity(blocks: list[RenderedBlock]) -> list[GuardFinding]:
    """G1: KEEP blocks must be byte-identical to their source (zero tolerance)."""
    findings: list[GuardFinding] = []
    for block in blocks:
        if block.operation is Operation.KEEP:
            if block.source_text is None:
                findings.append(
                    GuardFinding(
                        rule_id="G1",
                        severity=Severity.ERROR,
                        message="KEEP block has no source_text to verify against.",
                        block_id=block.block_id,
                    )
                )
                continue
            if block.output_text != block.source_text:
                diff = "\n".join(
                    difflib.unified_diff(
                        [block.source_text],
                        [block.output_text],
                        lineterm="",
                    )
                )
                findings.append(
                    GuardFinding(
                        rule_id="G1",
                        severity=Severity.ERROR,
                        message=f"KEEP block was altered from its source text: {diff}",
                        block_id=block.block_id,
                    )
                )
        elif block.operation is Operation.INSERT and block.source_text is not None:
            findings.append(
                GuardFinding(
                    rule_id="G1",
                    severity=Severity.ERROR,
                    message="INSERT block must not carry a source_text.",
                    block_id=block.block_id,
                )
            )
    return findings


def check_g2_orphaned_placeholders(blocks: list[RenderedBlock]) -> list[GuardFinding]:
    """G2: no unfilled template placeholder may reach the output."""
    findings: list[GuardFinding] = []
    for block in blocks:
        for pattern in _PLACEHOLDER_PATTERNS:
            match = pattern.search(block.output_text)
            if match:
                findings.append(
                    GuardFinding(
                        rule_id="G2",
                        severity=Severity.ERROR,
                        message=f"Orphaned placeholder found: {match.group(0)!r}",
                        block_id=block.block_id,
                    )
                )
    return findings


def check_g3_diacritic_ratio(
    blocks: list[RenderedBlock], tolerance: float = 0.02
) -> list[GuardFinding]:
    """G3: overall diacritic ratio of the output must not decrease vs. source."""
    source_text = "\n".join(
        b.source_text for b in blocks if b.source_text is not None
    )
    output_text = "\n".join(b.output_text for b in blocks)

    source_ratio = _diacritic_ratio(source_text)
    output_ratio = _diacritic_ratio(output_text)

    if output_ratio < source_ratio - tolerance:
        return [
            GuardFinding(
                rule_id="G3",
                severity=Severity.ERROR,
                message=(
                    "Diacritic ratio decreased: "
                    f"source={source_ratio:.4f} output={output_ratio:.4f}"
                ),
            )
        ]
    return []


# --- G4-G7: full implementations, all with graceful degradation ------------

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def check_g4_dictionary(
    blocks: list[RenderedBlock], dictionary_path: str | Path | None = None
) -> list[GuardFinding]:
    """G4: flag words absent from a hunspell fr-FR dictionary (INSERT blocks only).

    Capitalized words are skipped (likely proper nouns, handled by G7
    instead). If no dictionary is available, this check is skipped entirely
    rather than raising or guessing -- there is no bundled fr-FR hunspell
    dictionary in this offline repository by default.
    """
    if dictionary_path is None:
        return []

    try:
        from spylls.hunspell import Dictionary
    except ImportError:
        return []

    try:
        dictionary = Dictionary.from_files(str(dictionary_path))
    except Exception:
        return []

    findings: list[GuardFinding] = []
    for block in blocks:
        if block.operation is not Operation.INSERT:
            continue
        for word in _WORD_RE.findall(block.output_text):
            if word[0].isupper():
                continue
            if not dictionary.lookup(word):
                findings.append(
                    GuardFinding(
                        rule_id="G4",
                        severity=Severity.ERROR,
                        message=f"Word not found in dictionary: {word!r}",
                        block_id=block.block_id,
                    )
                )
    return findings


def _grammalecte_checker():
    """Build a grammar-check callable backed by Grammalecte if available.

    Grammalecte is the mandated primary checker (pure Python, offline, no
    JRE, French-specific rules for accords/élisions/typographie). It is not
    published as an installable ``pip`` package in this environment, so this
    import is expected to fail here and the caller falls back to
    ``language_tool_python``. Isolating the import in one place means
    swapping in a real Grammalecte install later requires no other code
    changes.
    """
    import grammalecte  # type: ignore[import-not-found]

    checker = grammalecte.GrammarChecker("fr")

    def _check(text: str) -> list[str]:
        return [str(err) for err in checker.getParagraphErrors(text)]

    return _check


def check_g5_grammar(blocks: list[RenderedBlock], language_tool_client=None) -> list[GuardFinding]:
    """G5: blocking offline grammar check, INSERT blocks only.

    Order of preference: (1) Grammalecte if installed -- pure Python, no
    network, best French-specific coverage (accords, élisions); (2) an
    injected ``language_tool_client`` exposing ``.check(text) -> list``
    (e.g. ``language_tool_python.LanguageTool``); (3) if neither is
    available, degrades to no findings -- G5 is explicitly optional per
    spec, never blocking the pipeline on missing optional tooling.

    Applied only to INSERT blocks: running a grammar checker over the
    user's own original (KEEP) text would risk "correcting" it, which is
    exactly the failure mode that produced defect D3 in the previous
    engine.
    """
    findings: list[GuardFinding] = []
    insert_blocks = [b for b in blocks if b.operation is Operation.INSERT]
    if not insert_blocks:
        return []

    try:
        grammalecte_check = _grammalecte_checker()
    except Exception:
        grammalecte_check = None

    if grammalecte_check is not None:
        for block in insert_blocks:
            try:
                errors = grammalecte_check(block.output_text)
            except Exception:
                continue
            for message in errors:
                findings.append(
                    GuardFinding(
                        rule_id="G5",
                        severity=Severity.WARNING,
                        message=f"Erreur grammaticale (Grammalecte) : {message}",
                        block_id=block.block_id,
                    )
                )
        return findings

    client = language_tool_client
    if client is None:
        try:
            import language_tool_python

            client = language_tool_python.LanguageTool("fr")
        except Exception:
            return []

    for block in insert_blocks:
        try:
            matches = client.check(block.output_text)
        except Exception:
            continue
        for match in matches:
            findings.append(
                GuardFinding(
                    rule_id="G5",
                    severity=Severity.WARNING,
                    message=f"Possible grammar issue: {getattr(match, 'message', str(match))}",
                    block_id=block.block_id,
                )
            )
    return findings


def check_g6_keyword_density(
    blocks: list[RenderedBlock],
    skill_terms: list[str] | None = None,
    max_occurrences: int = 3,
) -> list[GuardFinding]:
    """G6: cap how many times any single skill term may appear in the output.

    Guards against keyword stuffing (D2). If ``skill_terms`` is not supplied,
    there is nothing to check against, so this returns no findings.
    """
    if not skill_terms:
        return []

    full_text = canonicalize("\n".join(b.output_text for b in blocks))
    findings: list[GuardFinding] = []
    for term in skill_terms:
        canonical_term = canonicalize(term)
        if not canonical_term:
            continue
        count = len(re.findall(rf"(?<!\w){re.escape(canonical_term)}(?!\w)", full_text))
        if count > max_occurrences:
            findings.append(
                GuardFinding(
                    rule_id="G6",
                    severity=Severity.ERROR,
                    message=(
                        f"Keyword {term!r} appears {count} times "
                        f"(max allowed: {max_occurrences}) -- looks like keyword stuffing."
                    ),
                )
            )
    return findings


def check_g7_entity_casing(
    blocks: list[RenderedBlock], proper_nouns: list[str] | None = None
) -> list[GuardFinding]:
    """G7: proper nouns must keep their exact original casing wherever inserted.

    Only INSERT blocks are checked (KEEP blocks are already covered
    byte-for-byte by G1). If ``proper_nouns`` is not supplied, returns no
    findings.
    """
    if not proper_nouns:
        return []

    findings: list[GuardFinding] = []
    for block in blocks:
        if block.operation is not Operation.INSERT:
            continue
        for noun in proper_nouns:
            pattern = re.compile(re.escape(noun), re.IGNORECASE)
            for match in pattern.finditer(block.output_text):
                if match.group(0) != noun:
                    findings.append(
                        GuardFinding(
                            rule_id="G7",
                            severity=Severity.ERROR,
                            message=(
                                f"Proper noun casing altered: expected {noun!r}, "
                                f"found {match.group(0)!r}."
                            ),
                            block_id=block.block_id,
                        )
                    )
    return findings


def check_g8_typography(blocks: list[RenderedBlock]) -> list[GuardFinding]:
    """G8: French typography (narrow/no-break spaces) on INSERT blocks only.

    Ensures ``;:!?»`` are preceded by a narrow no-break space and ``%`` by a
    no-break space, per defect D10.
    """
    from src.render.french_typography import has_expected_spacing

    findings: list[GuardFinding] = []
    for block in blocks:
        if block.operation is not Operation.INSERT:
            continue
        if not has_expected_spacing(block.output_text):
            findings.append(
                GuardFinding(
                    rule_id="G8",
                    severity=Severity.WARNING,
                    message="Espacement typographique français manquant avant ;:!?»%.",
                    block_id=block.block_id,
                )
            )
    return findings


def check_g9_fact_attribution(
    blocks: list[RenderedBlock],
    facts=None,
    skill_labels: list[str] | None = None,
) -> list[GuardFinding]:
    """G9: un bloc INSERT ne peut mentionner un terme de l'ontologie que s'il
    existe un ``CvFact`` attestant ce terme dans CE bloc precis (meme
    ``block_id``). Un terme atteste uniquement ailleurs dans le CV (ex. la
    rubrique Competences) ne l'autorise pas dans une experience differente --
    c'est le garde-fou contre l'attribution abusive (D12).

    Degrade sans erreur si ``facts``/``skill_labels`` ne sont pas fournis
    (contexte non disponible), comme G4-G8.
    """
    if not facts or not skill_labels:
        return []

    findings: list[GuardFinding] = []
    facts_by_block: dict[str, set[str]] = {}
    for fact in facts:
        facts_by_block.setdefault(fact.block_id, set()).add(fact.label.lower())

    sorted_labels = sorted(skill_labels, key=len, reverse=True)
    for block in blocks:
        if block.operation is not Operation.INSERT:
            continue
        allowed = facts_by_block.get(block.block_id, set())
        for label in sorted_labels:
            pattern = re.compile(r"\b" + re.escape(label) + r"\b", re.IGNORECASE)
            if pattern.search(block.output_text) and label.lower() not in allowed:
                findings.append(
                    GuardFinding(
                        rule_id="G9",
                        severity=Severity.ERROR,
                        message=(
                            f"Terme '{label}' mentionné dans le bloc {block.block_id} "
                            "sans fait attesté dans ce bloc (attribution abusive)."
                        ),
                        block_id=block.block_id,
                    )
                )
    return findings

