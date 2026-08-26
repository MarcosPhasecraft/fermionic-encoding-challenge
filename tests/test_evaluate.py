"""Tests for harness.evaluate -- confirms the encode_fn -> verify -> score
chain, previously only ever hand-rolled in ad hoc scripts, actually
reproduces those results now that it's a real function.
"""

from baselines.jw import encode
from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle


def test_jw_3x3_row_major_matches_known_result():
    # Reproduces the numbers from the Table I investigation (PLAN.md Sec 1.7
    # Test 4 notes): row-major is the true global optimum for JW on 3x3,
    # total=201, max=4 -- matching arXiv 2504.21636's published max exactly.
    spec = rectangle(3, 3)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode, terms)

    assert result["passed"]
    assert result["total_weight"] == 201
    assert result["max_weight"] == 4


def test_evaluate_gates_scoring_on_verify_failure():
    def broken_encode(spec):
        mapping = encode(spec)
        mapping["majoranas"][0] = "XXI"  # drop the Z prefix, breaks the algebra
        return mapping

    spec = rectangle(3, 1)
    terms = hamiltonian(spec, model="hopping")
    result = evaluate(spec, broken_encode, terms)

    assert not result["passed"]
    assert "total_weight" not in result  # scoring never ran


def test_ordering_lives_in_spec_not_in_encode_fn():
    # Same encode_fn (JW), different orderings via different specs -- this
    # is the whole mechanism for comparing orderings: no change to encode_fn
    # or evaluate() itself, just which spec gets passed in.
    row_major_spec = rectangle(4, 4, ordering="row_major")
    snake_spec = rectangle(4, 4, ordering="snake")

    row_major_result = evaluate(row_major_spec, encode, hamiltonian(row_major_spec, model="full"))
    snake_result = evaluate(snake_spec, encode, hamiltonian(snake_spec, model="full"))

    assert row_major_result["passed"] and snake_result["passed"]
    # Matches the ordering-sensitivity finding from PLAN.md Sec 1.7 Test 3:
    # standard boustrophedon snake is not better than row-major for JW.
    assert row_major_result["max_weight"] <= snake_result["max_weight"]
    assert row_major_result["total_weight"] <= snake_result["total_weight"]
