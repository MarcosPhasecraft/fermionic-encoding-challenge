"""Tests for harness.lattice: rectangle() orderings and hamiltonian() term
construction. These were exercised extensively by hand in the Table I
investigation (PLAN.md Sec 1.7 Test 3/4) but never captured as real tests.
"""

import pytest

from harness.lattice import hamiltonian, rectangle


def test_row_major_indices():
    spec = rectangle(3, 2)  # Lx=3, Ly=2
    assert spec["coords"] == {
        0: (0, 0), 1: (1, 0), 2: (2, 0),
        3: (0, 1), 4: (1, 1), 5: (2, 1),
    }


def test_snake_indices():
    spec = rectangle(3, 3, ordering="snake")
    # row y=1 reverses direction relative to row_major: x=2,1,0 -> modes 3,4,5
    assert spec["coords"][3] == (2, 1)
    assert spec["coords"][4] == (1, 1)
    assert spec["coords"][5] == (0, 1)
    # even rows (y=0, y=2) are unchanged from row-major
    assert spec["coords"][0] == (0, 0)
    assert spec["coords"][8] == (2, 2)


def test_custom_ordering_with_explicit_permutation():
    perm = [3, 2, 1, 0]  # reverse a 2x2 grid's row-major indices
    spec = rectangle(2, 2, ordering="custom", perm=perm)
    assert spec["coords"][3] == (0, 0)
    assert spec["coords"][0] == (1, 1)


def test_unknown_ordering_raises():
    with pytest.raises(ValueError):
        rectangle(3, 3, ordering="not-a-real-ordering")


def test_custom_ordering_without_valid_permutation_raises():
    with pytest.raises(ValueError):
        rectangle(2, 2, ordering="custom", perm=[0, 1])  # wrong length

    with pytest.raises(ValueError):
        rectangle(2, 2, ordering="custom")  # missing perm entirely

    with pytest.raises(ValueError):
        rectangle(2, 2, ordering="custom", perm=[0, 0, 1, 2])  # not a permutation


def test_unknown_model_raises():
    spec = rectangle(2, 1)
    with pytest.raises(ValueError):
        hamiltonian(spec, model="not-a-real-model")


def test_term_counts_per_model():
    spec = rectangle(2, 1)  # M=2, 1 edge
    # hopping: 4 bilinears per edge (ReHop x2 + ImHop x2)
    assert len(hamiltonian(spec, model="hopping")) == 4
    # quadratic: hopping (4) + one Num term per vertex (2)
    assert len(hamiltonian(spec, model="quadratic")) == 6
    # full: quadratic (6) + 3 interaction pieces per edge (induced Num-like x2 + quartic)
    assert len(hamiltonian(spec, model="full")) == 9
