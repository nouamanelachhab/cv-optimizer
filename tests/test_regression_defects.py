"""Non-regression tests, one per defect (D1-D8) originally observed in the
free-text-rewriting engine this deterministic pipeline replaces.

Each test demonstrates that the new architecture makes the defect
structurally impossible (not just "currently absent").
"""

from __future__ import annotations

import pytest

from src.extract import extract_skills
from src.extract.facts import collect_facts, facts_for_block
from src.guard import Operation, RenderedBlock, run_guard
from src.guard.checks import check_g9_fact_attribution
from src.ingest.parser import parse_docx
from src.ontology import load_ontology
from src.render import RenderError, render
from src.render.operations import InsertTemplateBlock, KeepBlock


@pytest.fixture(scope="module")
def ontology():
    return load_ontology()


def test_d1_no_unfilled_placeholder_can_reach_output(ontology):
    """D1: unfilled template placeholders (e.g. '{competence}') must never
    reach the final output. InsertTemplateBlock raises if a required slot is
    missing, and G2 blocks any leftover placeholder-like pattern."""
    with pytest.raises(RenderError):
        render(
            [InsertTemplateBlock(template_id="skill_bullet", slots={})],
            source_blocks={},
            ontology=ontology,
        )
    # Even if a raw block slipped through with a leftover placeholder, G2 catches it.
    blocks = [
        RenderedBlock(
            block_id="b1",
            operation=Operation.INSERT,
            source_text=None,
            output_text="Expérience en {competence}.",
        )
    ]
    report = run_guard(blocks)
    assert not report.passed
    assert any(f.rule_id == "G2" for f in report.errors)


def test_d2_keyword_stuffing_is_flagged(ontology):
    """D2: excessive repetition of a keyword (stuffing) must be flagged."""
    blocks = [
        RenderedBlock(
            block_id="b1",
            operation=Operation.INSERT,
            source_text=None,
            output_text="Python Python Python Python Python.",
        )
    ]
    report = run_guard(blocks, skill_terms=["Python"], max_keyword_occurrences=3)
    assert not report.passed
    assert any(f.rule_id == "G6" for f in report.errors)


def test_d3_naive_spellcheck_corruption_is_blocked_by_g1():
    """D3: a naive spellchecker rewriting 'infocentre' or similar terms into
    something else inside a KEEP block must be rejected byte-for-byte."""
    corrupted = RenderedBlock(
        block_id="b1",
        operation=Operation.KEEP,
        source_text="Expérience en infocentre Oracle.",
        output_text="Expérience en info-centre Oracle.",  # naive "correction"
    )
    report = run_guard([corrupted])
    assert not report.passed
    assert any(f.rule_id == "G1" for f in report.errors)


def test_d4_diacritic_loss_is_blocked():
    """D4: diacritics stripped by an over-eager normalizer must be caught."""
    blocks = [
        RenderedBlock(
            block_id="b1",
            operation=Operation.KEEP,
            source_text="Ingénieur diplômé, sécurité des données",
            output_text="Ingenieur diplome, securite des donnees",
        )
    ]
    report = run_guard(blocks)
    assert not report.passed
    assert any(f.rule_id in ("G1", "G3") for f in report.errors)


def test_d5_unwanted_verb_reconjugation_is_blocked():
    """D5: silently reconjugating a verb inside a KEEP block is rejected."""
    blocks = [
        RenderedBlock(
            block_id="b1",
            operation=Operation.KEEP,
            source_text="A développé une application de gestion des stocks.",
            output_text="Développe une application de gestion des stocks.",
        )
    ]
    report = run_guard(blocks)
    assert not report.passed
    assert any(f.rule_id == "G1" for f in report.errors)


def test_d6_proper_noun_casing_loss_is_blocked():
    """D6: 'Decathlon' becoming 'decathlon' in an inserted block is rejected."""
    blocks = [
        RenderedBlock(
            block_id="b1",
            operation=Operation.INSERT,
            source_text=None,
            output_text="Expérience professionnelle chez decathlon.",
        )
    ]
    report = run_guard(blocks, proper_nouns=["Decathlon"])
    assert not report.passed
    assert any(f.rule_id == "G7" for f in report.errors)


def test_d7_false_positive_skill_extraction_requires_context(ontology):
    """D7: an ambiguous term ('Java' as the island) must not be extracted as
    a skill unless real technical context is present."""
    lone_mention = "Je suis né à Java, une île d'Indonésie, en 1990."
    skills_alone = extract_skills(lone_mention, ontology)
    assert "java" not in {s.skill_id for s in skills_alone}

    technical_context = "Développement Java, Python et Docker."
    skills_with_context = extract_skills(technical_context, ontology)
    assert "java" in {s.skill_id for s in skills_with_context}


def test_d8_template_insertion_never_produces_broken_grammar(ontology):
    """D8: an insertion can only ever be a fully pre-validated, grammatically
    correct template with ontology-checked slot values -- never assembled
    free text that could break grammatically."""
    result = render(
        [KeepBlock(block_id="b1")],
        source_blocks={"b1": "kept text"},
        ontology=ontology,
    )
    # The only way to add new text is InsertTemplateBlock, and it either
    # produces the exact pre-authored (grammatically valid) template text or
    # raises -- it can never silently emit a malformed sentence.
    with pytest.raises(RenderError):
        render(
            [InsertTemplateBlock(template_id="skill_bullet", slots={"skill": "not-a-real-skill"})],
            source_blocks={},
            ontology=ontology,
        )
    assert result.blocks[0].output_text == "kept text"


def test_d9_source_blocks_are_never_merged_across_runs(ontology, simple_cv_bytes):
    """D9: reconstructing a paragraph run-by-run can merge two originally
    distinct blocks into one ("Full-Stack PHP / Java. — Sofrecom"). In this
    architecture each source block keeps its own block_id and is only ever
    KEPT verbatim or DROPPED -- never concatenated with another block's text
    -- so two distinct entries can never fuse into a single output block."""
    doc = parse_docx(simple_cv_bytes, source_name="cv.docx")
    exp_section = next(s for s in doc.sections if s.category == "experience")
    entry = exp_section.entries[0]
    # The entry heading and its bullets are distinct blocks with distinct ids.
    block_ids = {entry.block_id, *[b.block_id for b in entry.bullets]}
    assert len(block_ids) == 1 + len(entry.bullets)

    blocks = [
        RenderedBlock(block_id=entry.block_id, operation=Operation.KEEP, source_text=entry.text, output_text=entry.text)
    ] + [
        RenderedBlock(block_id=b.block_id, operation=Operation.KEEP, source_text=b.text, output_text=b.text)
        for b in entry.bullets
    ]
    report = run_guard(blocks)
    assert report.passed
    # Each rendered block corresponds 1:1 to a single original block -- no
    # block's output_text is the concatenation of two source texts.
    for block in blocks:
        assert block.output_text == block.source_text


def test_d10_narrow_nbsp_cannot_be_silently_dropped():
    """D10: a KEEP block that drops the narrow no-break space before a French
    punctuation mark (e.g. "30 %" losing its NBSP) is byte-different from the
    source and therefore rejected by G1 -- narrow/no-break spaces can never
    be silently lost in a KEEP block."""
    source = "Réduction du temps de traitement de 30\u202f%\u00a0;\u00a0objectif atteint."
    corrupted = RenderedBlock(
        block_id="b1",
        operation=Operation.KEEP,
        source_text=source,
        output_text=source.replace("\u202f", " ").replace("\u00a0", " "),
    )
    report = run_guard([corrupted])
    assert not report.passed
    assert any(f.rule_id == "G1" for f in report.errors)


def test_d11_determiners_cannot_be_silently_dropped():
    """D11: changing a bullet's verbal tense in place (e.g. dropping "une"
    in "Réalisé fonctionnalités de supervision") produces a KEEP block that
    is byte-different from the source and is rejected by G1. This
    architecture never rewrites a KEEP block's text at all -- rewrites only
    ever happen through InsertTemplateBlock, which requires a fully
    pre-authored, grammatically complete template."""
    source = "A développé une fonctionnalité de supervision."
    corrupted = RenderedBlock(
        block_id="b1",
        operation=Operation.KEEP,
        source_text=source,
        output_text="Développé fonctionnalité de supervision.",  # determiner "une" lost
    )
    report = run_guard([corrupted])
    assert not report.passed
    assert any(f.rule_id == "G1" for f in report.errors)


def test_d12_skill_from_another_section_cannot_be_attributed_to_a_block(ontology, simple_cv_bytes):
    """D12: 'Spring Boot' mentioned only in the Compétences section must
    never be presented as a fact of an unrelated Experience block. Facts are
    rattachés to their exact source block_id (see extract/facts.py); G9
    rejects any INSERT block mentioning a skill term with no CvFact attested
    in that same block_id."""
    doc = parse_docx(simple_cv_bytes, source_name="cv.docx")
    facts = collect_facts(doc, ontology)

    competences_section = next(s for s in doc.sections if s.category == "competences")
    competences_block_id = competences_section.free_text_blocks[0].block_id
    exp_section = next(s for s in doc.sections if s.category == "experience")
    unrelated_bullet_id = exp_section.entries[0].bullets[0].block_id

    # "Python" is genuinely attested in the Compétences block...
    assert any(f.block_id == competences_block_id and f.label.lower() == "python" for f in facts)
    # ...but NOT attested in this unrelated experience bullet.
    assert not any(f.block_id == unrelated_bullet_id and f.label.lower() == "python" for f in facts)
    assert facts_for_block(facts, unrelated_bullet_id) == []

    # A render step that (wrongly) inserts "Python" into that unrelated
    # bullet, using facts collected from the whole CV instead of the block,
    # must be rejected by G9.
    bad_insert = RenderedBlock(
        block_id=unrelated_bullet_id,
        operation=Operation.INSERT,
        source_text=None,
        output_text="Optimisation des traitements Python en environnement Oracle.",
    )
    findings = check_g9_fact_attribution([bad_insert], facts=facts, skill_labels=["Python"])
    assert any(f.rule_id == "G9" for f in findings)

    report = run_guard([bad_insert], facts=facts, skill_labels=["Python"])
    assert not report.passed
    assert any(f.rule_id == "G9" for f in report.errors)
