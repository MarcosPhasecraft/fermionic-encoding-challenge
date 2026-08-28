"""Tests for baselines.geo_ternary_opt -- an externally-submitted variant
of baselines.geo_ternary that adds a bounded local search (_optimize_order)
hill-climbing the mode-to-tree-slot assignment against (max_weight,
total_weight). Every candidate it considers is already a valid encoding --
relabelling which mode owns which operator can't break the Majorana
algebra -- so the search can only improve score, never validity; see
baselines/geo_ternary_opt.py's own docstring for the full argument.
"""

import pytest

from baselines.geo_ternary_opt import encode
from baselines.jw import encode as jw_encode
from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle
from harness.verify import verify


# Kept deliberately small (l <= 3): _optimize_order's local search is
# genuinely expensive even at moderate M (0.5s+ at 5x5, tens of seconds by
# 15x15 -- see scripts/submit_baseline.py's acceptance run, which already
# exercised the full 3x3-15x15 range once as the real gate). These tests
# are a fast sanity/regression check, not a re-verification at every size.


@pytest.mark.parametrize("l", [1, 2, 3])
def test_valid_encoding(l):
    spec = rectangle(l, l)
    assert verify(spec, encode(spec))["passed"]


def test_m1_matches_jw():
    spec = rectangle(1, 1)
    assert encode(spec)["majoranas"] == jw_encode({"M": 1})["majoranas"]


def test_deterministic():
    # _optimize_order uses an RNG seeded by M alone -- running encode()
    # twice on the same spec must give byte-identical results, or the
    # leaderboard number for this submission wouldn't be reproducible.
    spec = rectangle(3, 3)
    assert encode(spec)["majoranas"] == encode(spec)["majoranas"]


def test_pinned_regression_values():
    # Pins the exact score this submission was accepted with at 3x3 (from
    # scripts/submit_baseline.py's output) -- a future refactor of
    # geo_ternary_opt.py that silently changes its search or scores
    # should fail this.
    spec = rectangle(3, 3)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode, terms)
    assert result["passed"]
    assert result["total_weight"] == 243
    assert result["max_weight"] == 5
