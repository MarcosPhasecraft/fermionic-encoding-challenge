"""Analytic 1D chain -- PLAN.md Sec 1.7 Test 1.

Run this first: it validates the symplectic machinery against a result we
can derive by hand, no external source needed. If it fails, nothing
downstream (Tests 2-4) is meaningful.
"""

import pytest

from baselines.jw import encode
from harness.lattice import hamiltonian, rectangle
from harness.score import score_majorana
from harness.verify import verify


@pytest.mark.parametrize("L", [4, 16, 64])
def test_jw_chain_hopping_weight_is_exactly_two(L):
    spec = rectangle(L, 1)
    mapping = encode(spec)
    assert verify(spec, mapping)["passed"]

    terms = hamiltonian(spec, model="hopping")
    s = score_majorana(spec, mapping, terms)

    # avg_weight == max_weight == 2 forces every term to be exactly weight 2
    # (weights are non-negative integers, so equal average and max means no
    # term can be below the max either).
    assert s["max_weight"] == 2
    assert s["avg_weight"] == 2
