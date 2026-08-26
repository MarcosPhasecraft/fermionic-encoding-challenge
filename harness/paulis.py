"""Symplectic (bit-vector) representation of Pauli strings.

A Pauli on N qubits is represented as a pair of length-N bit vectors (x, z):
X sets the x-bit, Z sets the z-bit, Y sets both, I sets neither. Two Paulis
anticommute iff their symplectic inner product is 1 (mod 2):

    x1 . z2 + z1 . x2 = 1  (mod 2)

This module assumes inputs are already well-formed (chars in IXYZ, consistent
lengths). Validation of untrusted input happens one layer up, in verify.py.
"""

import numpy as np

# Phase is dropped -- commutation doesn't depend on it.
_CHAR_TO_XZ = {"I": (0, 0), "X": (1, 0), "Y": (1, 1), "Z": (0, 1)}


def string_to_xz(pauli: str) -> tuple[np.ndarray, np.ndarray]:
    """A single length-N Pauli string -> (x, z), each a length-N bit vector."""
    n = len(pauli)
    x = np.zeros(n, dtype=np.uint8)
    z = np.zeros(n, dtype=np.uint8)
    for i, c in enumerate(pauli):
        x[i], z[i] = _CHAR_TO_XZ[c]
    return x, z


def strings_to_xz_matrix(paulis: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """k length-N Pauli strings -> (X, Z), each a (k, N) bit matrix.

    Row i of X, Z is the (x, z) pair for paulis[i].
    """
    k = len(paulis)
    n = len(paulis[0])
    X = np.zeros((k, n), dtype=np.uint8)
    Z = np.zeros((k, n), dtype=np.uint8)
    for row, s in enumerate(paulis):
        X[row], Z[row] = string_to_xz(s)
    return X, Z


def commutation_matrix(X: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """Pairwise anticommutation table for the Paulis stacked in (X, Z).

    Applies the module-level formula (x1.z2 + z1.x2 mod 2) to every pair at
    once: each matmul computes one of its two terms for all pairs in one shot.

        C = (X @ Z.T + Z @ X.T) mod 2

    So C[i, j] == 1 iff Pauli i and Pauli j anticommute, 0 if they commute.
    Vectorized like this instead of a Python double loop, since that loop is
    what would starve later once this runs inside search.
    """
    return (X @ Z.T + Z @ X.T) % 2
