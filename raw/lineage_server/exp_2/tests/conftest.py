"""Shared test helpers.

`plain` rewrites fallback block ids (`b_<n>_<hash8>`) back to their bare
ordinal (`b_<n>`) inside any string, so tests that are about lineage
structure — which occurrence flows into which — stay readable and do not
hard-code content hashes. The hash format itself is asserted directly in
tests/unit/test_block_edges.py.
"""
import re

import pytest

_FALLBACK_ID = re.compile(r"\bb_(\d+)_[0-9a-f]{8}\b")


def strip_block_hash(text: str) -> str:
    return _FALLBACK_ID.sub(r"b_\1", text)


@pytest.fixture
def plain():
    return strip_block_hash
