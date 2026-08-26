"""Frozen Stage-2 helpers, built ahead of schedule (see NOTES.md for why
evaluate() was too). Importable by any encode_fn, baseline or submission.

from_linear_encoding(U) is the general ancilla-free linear encoding (arXiv
2504.21636 eq. 18): given invertible U over GF(2), F = U^-1, gamma_i ->
X_{U(i)} Z_{P(i)}, gammabar_i -> X_{U(i)} Z_{R(i)}, with R = L @ F (L =
lower-triangular ones INCLUDING the diagonal) and P = R + F.

That L-includes-diagonal detail matters and is easy to get backwards: an
earlier draft of this derivation (see PLAN.md's original eq. 18 note) used
L strictly below the diagonal, which is wrong -- verified here by requiring
from_linear_encoding(I) to reproduce baselines/jw.py's hand-written mapping
exactly (tests/test_constructors.py), which only holds with L including the
diagonal.
"""

import numpy as np

from harness.paulis import xz_to_string


def _invert_gf2(u: np.ndarray) -> np.ndarray:
    """U^-1 over GF(2) via Gauss-Jordan elimination (XOR row ops)."""
    n = u.shape[0]
    augmented = np.concatenate([u.astype(np.uint8) % 2, np.eye(n, dtype=np.uint8)], axis=1)
    for col in range(n):
        pivot = next((row for row in range(col, n) if augmented[row, col]), None)
        if pivot is None:
            raise ValueError("U is not invertible over GF(2)")
        augmented[[col, pivot]] = augmented[[pivot, col]]
        for row in range(n):
            if row != col and augmented[row, col]:
                augmented[row] ^= augmented[col]
    return augmented[:, n:]


def from_linear_encoding(u: np.ndarray) -> dict:
    n = u.shape[0]
    f = _invert_gf2(u)
    l = np.tril(np.ones((n, n), dtype=np.uint8))  # lower-triangular ones, diagonal included
    r = (l @ f) % 2
    p = (r + f) % 2

    majoranas = []
    for i in range(n):
        x_support = u[:, i] % 2
        majoranas.append(xz_to_string(x_support, p[i, :]))
        majoranas.append(xz_to_string(x_support, r[i, :]))

    return {"n_qubits": n, "majoranas": majoranas, "stabilizers": []}
