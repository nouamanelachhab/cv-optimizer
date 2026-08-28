"""Hypothesis property test for the render module.

Property (as mandated by the spec): for any input CV, the set of KeepBlock
output blocks in the render result is an exact subset of the input blocks.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.render import render
from src.render.operations import DropBlock, KeepBlock

_BLOCK_IDS = [f"b{i}" for i in range(10)]
_SOURCE_BLOCKS = {block_id: f"texte original {block_id}" for block_id in _BLOCK_IDS}


@given(
    kept_ids=st.lists(st.sampled_from(_BLOCK_IDS), unique=True),
    dropped_ids=st.lists(st.sampled_from(_BLOCK_IDS), unique=True),
)
def test_keep_block_outputs_are_always_a_subset_of_input_blocks(kept_ids, dropped_ids):
    operations = [KeepBlock(block_id=bid) for bid in kept_ids] + [
        DropBlock(block_id=bid) for bid in dropped_ids if bid not in kept_ids
    ]

    result = render(operations, _SOURCE_BLOCKS, ontology=None)

    output_block_ids = {b.block_id for b in result.blocks}
    assert output_block_ids <= set(_SOURCE_BLOCKS.keys())
    assert output_block_ids == set(kept_ids)

    for block in result.blocks:
        assert block.output_text == _SOURCE_BLOCKS[block.block_id]
        assert block.source_text == _SOURCE_BLOCKS[block.block_id]
