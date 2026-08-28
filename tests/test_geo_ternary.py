"""Tests for baselines.geo_ternary -- an externally-submitted, from-scratch
ternary-tree encoding whose mode ordering is derived directly from
spec["coords"] inside encode() itself (no separate order() function). See
baselines/geo_ternary.py's own docstring for the construction and
correctness sketch.
"""

import pytest

from baselines.geo_ternary import _spatial_order, _tree_mode_pairs, encode
from baselines.jw import encode as jw_encode
from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle
from harness.verify import verify


@pytest.mark.parametrize("l", [1, 2, 3, 4, 5, 7, 9, 12])
def test_valid_encoding(l):
    # encode() reads spec["coords"] directly, so it needs a real lattice
    # spec -- unlike the other baselines, a bare {"M": m} dict won't do.
    spec = rectangle(l, l)
    assert verify(spec, encode(spec))["passed"]


def test_valid_on_a_non_square_lattice():
    # _spatial_order recursively splits along whichever axis is longer, so
    # this must generalize beyond the square grids it was submitted for --
    # confirms it's a genuine formula, not something tuned to l x l shapes.
    spec = rectangle(4, 6)
    assert verify(spec, encode(spec))["passed"]


def test_m1_matches_jw():
    spec = rectangle(1, 1)
    assert encode(spec)["majoranas"] == jw_encode({"M": 1})["majoranas"]


def test_tree_mode_pairs_produce_exactly_m_pairs():
    for m in (1, 4, 9, 16, 25):
        assert len(_tree_mode_pairs(m)) == m


def test_spatial_order_is_a_permutation():
    for l in (3, 5, 9):
        spec = rectangle(l, l)
        assert sorted(_spatial_order(spec)) == list(range(l * l))


@pytest.mark.parametrize("l,expected_total,expected_max", [(3, 261, 6), (9, 4053, 10), (15, 12434, 13)])
def test_pinned_regression_values(l, expected_total, expected_max):
    # Pins the exact scores this submission was accepted with (from
    # scripts/submit_baseline.py's output) -- a future refactor of
    # geo_ternary.py that silently changes its scores should fail this.
    spec = rectangle(l, l)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode, terms)
    assert result["passed"]
    assert result["total_weight"] == expected_total
    assert result["max_weight"] == expected_max
