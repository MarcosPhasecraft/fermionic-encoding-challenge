"""Tests for baselines.ternary (ternary tree)."""

import math

import pytest

from baselines.jw import encode as jw_encode
from baselines.ternary import encode, tt_matrix
from harness.constructors import _invert_gf2
from harness.verify import verify


@pytest.mark.parametrize("m", [1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16, 17, 25])
def test_valid_encoding(m):
    # Also exercises _invert_gf2(tt_matrix(m)) implicitly -- a singular
    # matrix would raise inside encode() rather than fail verify().
    spec = {"name": "test", "M": m}
    assert verify(spec, encode(spec))["passed"]


def test_m1_matches_jw():
    # A single mode has no tree structure to speak of -- TT must degenerate
    # to exactly JW's mapping.
    assert encode({"M": 1})["majoranas"] == jw_encode({"M": 1})["majoranas"]


def test_m4_pinned_structure():
    # Regression pin against a hand-verified Sierpinski-tree mapping for
    # M=4 (padded range 0..8): distinguishes this from both JW and BK.
    mapping = encode({"M": 4})
    assert mapping["majoranas"] == [
        "XXII", "YXII", "ZXII", "IYZI",
        "IYYI", "IYXI", "IZIX", "IZIY",
    ]


@pytest.mark.parametrize("m", [3, 5, 9, 15, 17, 25, 100, 225])
def test_num_weight_grows_log_like(m):
    # Ternary tree's recursion isn't a perfectly balanced tree (the middle
    # third's own children aren't wired directly to the outer thirds), so
    # there's no clean ceil(log3(m))+1 closed form the way BK has one for
    # log2 -- but weight must still grow far slower than linearly. This
    # generous 2*ceil(log2(m))+2 envelope is loose enough to hold at every
    # size checked while still ruling out anything but log-like growth.
    f = _invert_gf2(tt_matrix(m))
    max_num_weight = max(int(row.sum()) for row in f)
    assert max_num_weight <= 2 * math.ceil(math.log2(m)) + 2


def test_num_weight_nondecreasing():
    sizes = [3, 9, 27, 81, 225]
    weights = []
    for m in sizes:
        f = _invert_gf2(tt_matrix(m))
        weights.append(max(int(row.sum()) for row in f))
    assert weights == sorted(weights)
