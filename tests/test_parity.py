"""Tests for baselines.parity."""

import pytest

from baselines.parity import encode, order
from baselines.parity_snake import encode as snake_encode
from baselines.parity_snake import order as snake_order
from harness.lattice import row_major_perm, snake_perm
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


def test_declared_ordering_is_row_major():
    assert order(3, 3) == row_major_perm(3, 3)


def test_snake_variant_declares_snake_and_reuses_the_same_encode():
    # parity_snake.py is a thin wrapper: same encoding, different declared
    # ordering -- prove it's actually the same function, not a duplicate.
    assert snake_encode is encode
    assert snake_order(3, 3) == snake_perm(3, 3)
