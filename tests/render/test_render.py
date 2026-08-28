"""Tests for the render module."""

from __future__ import annotations

import pytest

from src.guard import Operation, run_guard
from src.ontology import load_ontology
from src.render import RenderError, render
from src.render.french import elide, join_list_fr
from src.render.operations import DropBlock, InsertTemplateBlock, KeepBlock, ReorderBlocks
from src.render.templates import TemplateError, load_templates, render_template


@pytest.fixture(scope="module")
def ontology():
    return load_ontology()


SOURCE_BLOCKS = {
    "b1": "Ingénieur diplômé en génie informatique",
    "b2": "Expérience Decathlon",
    "b3": "Puce à conserver telle quelle.",
}


def test_keep_block_preserves_text_exactly(ontology):
    result = render([KeepBlock(block_id="b1")], SOURCE_BLOCKS, ontology)
    assert len(result.blocks) == 1
    assert result.blocks[0].output_text == SOURCE_BLOCKS["b1"]
    assert result.blocks[0].operation is Operation.KEEP


def test_keep_block_unknown_id_raises(ontology):
    with pytest.raises(RenderError):
        render([KeepBlock(block_id="does-not-exist")], SOURCE_BLOCKS, ontology)


def test_drop_block_removes_from_output(ontology):
    result = render([KeepBlock(block_id="b1"), DropBlock(block_id="b2")], SOURCE_BLOCKS, ontology)
    ids = {b.block_id for b in result.blocks}
    assert "b1" in ids
    assert "b2" not in ids
    assert "b2" in result.dropped_block_ids


def test_reorder_blocks_controls_output_sequence(ontology):
    result = render([ReorderBlocks(block_ids=["b3", "b1", "b2"])], SOURCE_BLOCKS, ontology)
    assert [b.block_id for b in result.blocks] == ["b3", "b1", "b2"]


def test_insert_template_block_with_valid_slot(ontology):
    result = render(
        [InsertTemplateBlock(template_id="skill_bullet", slots={"skill": "Python"})],
        SOURCE_BLOCKS,
        ontology,
    )
    assert len(result.blocks) == 1
    inserted = result.blocks[0]
    assert inserted.operation is Operation.INSERT
    assert inserted.source_text is None
    assert inserted.output_text == "Maîtrise de Python."


def test_insert_template_block_with_skill_list(ontology):
    result = render(
        [
            InsertTemplateBlock(
                template_id="skills_list_bullet",
                slots={"skills": ["Python", "SQL", "Docker"]},
            )
        ],
        SOURCE_BLOCKS,
        ontology,
    )
    assert result.blocks[0].output_text == "Compétences techniques : Python, SQL et Docker."


def test_insert_template_block_rejects_invalid_skill_label(ontology):
    with pytest.raises(RenderError):
        render(
            [InsertTemplateBlock(template_id="skill_bullet", slots={"skill": "Invented Skill"})],
            SOURCE_BLOCKS,
            ontology,
        )


def test_insert_template_block_unknown_template_raises(ontology):
    with pytest.raises(RenderError):
        render(
            [InsertTemplateBlock(template_id="does_not_exist", slots={"skill": "Python"})],
            SOURCE_BLOCKS,
            ontology,
        )


def test_render_output_passes_guard(ontology):
    result = render(
        [
            KeepBlock(block_id="b1"),
            InsertTemplateBlock(template_id="skill_bullet", slots={"skill": "Docker"}),
        ],
        SOURCE_BLOCKS,
        ontology,
    )
    report = run_guard(result.blocks)
    assert report.passed


def test_render_template_never_leaves_unfilled_placeholder(ontology):
    templates = load_templates()
    with pytest.raises(TemplateError):
        render_template(templates["skill_bullet"], {}, ontology)


def test_elide_applies_before_vowel():
    assert elide("de", "Anglais") == "d'"
    assert elide("de", "Python") == "de"


def test_elide_preserves_capitalization():
    assert elide("De", "Anglais") == "D'"


def test_join_list_fr_various_lengths():
    assert join_list_fr([]) == ""
    assert join_list_fr(["Python"]) == "Python"
    assert join_list_fr(["Python", "SQL"]) == "Python et SQL"
    assert join_list_fr(["Python", "SQL", "Docker"]) == "Python, SQL et Docker"


def test_elide_h_aspire_does_not_elide():
    assert elide("de", "héros") == "de"
    assert elide("de", "hall") == "de"


def test_elide_h_muet_still_elides():
    assert elide("de", "habitude") == "d'"


def test_elide_acronym_vowel_sounding_letter():
    assert elide("de", "API") == "d'"


def test_elide_acronym_consonant_sounding_letter():
    assert elide("de", "PKI") == "de"
