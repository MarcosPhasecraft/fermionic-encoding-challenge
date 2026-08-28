"""Tests for baselines.bk (Bravyi-Kitaev)."""

import math

import pytest

from baselines.bk import bk_matrix, encode
from baselines.jw import encode as jw_encode
from harness.constructors import _invert_gf2
from harness.verify import verify


@pytest.mark.parametrize("m", [1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16, 17, 25])
def test_valid_encoding(m):
    # Also exercises _invert_gf2(bk_matrix(m)) implicitly -- a singular
    # matrix would raise inside encode() rather than fail verify().
    spec = {"name": "test", "M": m}
    assert verify(spec, encode(spec))["passed"]


def test_m1_matches_jw():
    # A single mode has no tree structure to speak of -- BK must degenerate
    # to exactly JW's mapping.
    assert encode({"M": 1})["majoranas"] == jw_encode({"M": 1})["majoranas"]


def test_m4_pinned_structure():
    # Regression pin against a hand-verified Fenwick-tree mapping for M=4
    # (padded range 0..3): mode 2's operators pick up a Z from mode 1's
    # ancestor edge, distinguishing this from both JW and parity.
    mapping = encode({"M": 4})
    assert mapping["majoranas"] == [
        "XXIX", "YXIX", "ZXIX", "IYIX",
        "IZXX", "IZYX", "IZZX", "IIIY",
    ]


@pytest.mark.parametrize("m", [1, 2, 4, 8, 16, 32, 64, 128])
def test_num_weight_matches_log2_formula_at_powers_of_two(m):
    # At an exact power of two, the Fenwick tree built on [0, m) is a
    # perfectly balanced binary tree of height log2(m), so every mode's
    # number of ancestors (its Num-term weight) tops out at exactly
    # ceil(log2(m)) + 1 -- unlike JW, where it's always 1 regardless of m.
    f = _invert_gf2(bk_matrix(m))
    max_num_weight = max(int(row.sum()) for row in f)
    expected = math.ceil(math.log2(m)) + 1 if m > 1 else 1
    assert max_num_weight == expected


@pytest.mark.parametrize("m", [3, 5, 9, 15, 17, 25, 100, 225])
def test_num_weight_bounded_by_next_power_of_two(m):
    # For m not itself a power of two, padding can only ever shrink a
    # mode's ancestor count relative to the fully-padded perfect tree, so
    # the power-of-two formula is still a valid upper bound.
    padded = 2 ** math.ceil(math.log2(m))
    f = _invert_gf2(bk_matrix(m))
    max_num_weight = max(int(row.sum()) for row in f)
    assert max_num_weight <= math.ceil(math.log2(padded)) + 1
