"""Tests for baselines.parity."""

import pytest

from baselines.parity import encode
from harness.verify import verify


@pytest.mark.parametrize("m", [2, 3, 4, 9])
def test_valid_encoding(m):
    spec = {"name": "test", "M": m}
    assert verify(spec, encode(spec))["passed"]


def test_m4_matches_known_structure():
    # Pin the dual-JW structure: mode i's X-support is the shrinking suffix
    # {i, ..., M-1}, opposite of JW's growing prefix.
    mapping = encode({"M": 4})
    assert mapping["majoranas"] == ["XXXX", "YXXX", "ZXXX", "IYXX", "IZXX", "IIYX", "IIZX", "IIIY"]
