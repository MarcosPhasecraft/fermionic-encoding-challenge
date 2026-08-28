"""Tests for baselines.geo_ternary_anneal -- another externally-submitted
variant of baselines.geo_ternary, this one replacing the max-weight local
search in geo_ternary_opt with simulated annealing that minimizes *total*
Pauli weight instead. Every candidate it considers is already a valid
encoding -- relabelling which mode owns which operator can't break the
Majorana algebra -- so the search can only improve score, never validity;
see baselines/geo_ternary_anneal.py's own docstring for the full argument.
"""

from baselines.geo_ternary_anneal import encode
from baselines.jw import encode as jw_encode
from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle
from harness.verify import verify

# Kept deliberately tiny: _optimize_order's iteration floor is 100,000
# regardless of M (even M=1 skips it, but M=4 already costs ~0.7s -- see
# scripts/submit_baseline.py's acceptance run, which already exercised the
# full 3x3-15x15 range once as the real gate). These are fast sanity/
# regression checks, not a re-verification at every size.


def test_valid_encoding_m1_and_m4():
    for l in (1, 2):
        spec = rectangle(l, l)
        assert verify(spec, encode(spec))["passed"]


def test_m1_matches_jw():
    spec = rectangle(1, 1)
    assert encode(spec)["majoranas"] == jw_encode({"M": 1})["majoranas"]


def test_deterministic():
    # _optimize_order uses an RNG seeded by M alone -- running encode()
    # twice on the same spec must give byte-identical results, or the
    # leaderboard number for this submission wouldn't be reproducible.
    spec = rectangle(2, 2)
    assert encode(spec)["majoranas"] == encode(spec)["majoranas"]


def test_pinned_regression_values():
    # Pins the exact score this submission was accepted with at 3x3 (from
    # scripts/submit_baseline.py's output) -- a future refactor of
    # geo_ternary_anneal.py that silently changes its search or scores
    # should fail this. Also exercises verify() at 3x3, so a separate
    # valid_encoding case for it would be redundant.
    spec = rectangle(3, 3)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode, terms)
    assert result["passed"]
    assert result["total_weight"] == 243
    assert result["max_weight"] == 6
