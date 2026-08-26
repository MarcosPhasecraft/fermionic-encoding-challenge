"""Direct tests for harness.paulis -- the foundational symplectic
representation, previously only exercised indirectly via verify.py/score.py.
"""

import numpy as np

from harness.paulis import commutation_matrix, string_to_xz, strings_to_xz_matrix


def test_string_to_xz_encodes_each_pauli_char():
    x, z = string_to_xz("IXYZ")
    assert list(x) == [0, 1, 1, 0]
    assert list(z) == [0, 0, 1, 1]


def test_single_qubit_commutation_facts():
    # X,Z anticommute; X,X commute; I commutes with everything.
    x, z = strings_to_xz_matrix(["X", "Z", "X", "I"])
    c = commutation_matrix(x, z)
    assert c[0, 1] == 1  # X,Z anticommute
    assert c[0, 2] == 0  # X,X commute
    assert c[3, 0] == 0  # I,X commute
    assert c[3, 1] == 0  # I,Z commute


def test_commutation_matrix_is_symmetric_with_zero_diagonal():
    x, z = strings_to_xz_matrix(["XII", "ZXI", "IZY"])
    c = commutation_matrix(x, z)
    assert np.array_equal(c, c.T)
    assert np.all(np.diag(c) == 0)


def test_xor_cancellation_not_or():
    # Two Paulis sharing a Z factor on the same qubit: the product's weight
    # must reflect XOR (cancellation), not OR (which would overcount).
    x, z = strings_to_xz_matrix(["ZX", "ZY"])  # share the Z on qubit 0
    combined_x = np.bitwise_xor.reduce(x, axis=0)
    combined_z = np.bitwise_xor.reduce(z, axis=0)
    weight = int(np.count_nonzero(combined_x | combined_z))
    assert weight == 1  # qubit 0's Z cancels; only qubit 1 (X xor Y = Z) survives
