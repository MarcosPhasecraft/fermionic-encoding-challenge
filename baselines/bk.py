"""Bravyi-Kitaev: a linear encoding built from a Fenwick-tree matrix.

U's structure: pad the mode range to the next power of 2, recursively
connect each range's midpoint down into its two half-ranges (the standard
Fenwick / binary-indexed-tree construction), take the transitive closure
(U[i,j]=1 iff j is an ancestor of i in the resulting tree), then add the
identity (every mode is trivially its own ancestor). Cross-checked against
arXiv 2504.21636's released code (hexaly_quadratic_assignment.py's
fenwick()/bk()) -- reimplemented in plain numpy rather than their
GF(2)-Galois-array style, but preserving the exact recursion and padding.
"""

import math

import numpy as np

from harness.constructors import from_linear_encoding, transitive_closure


def _fenwick(u: np.ndarray, c: int, r: int) -> None:
    if c == r:
        return
    k = (c + r) // 2
    if r < u.shape[0] and k < u.shape[1]:
        u[r, k] = 1
    _fenwick(u, c, k)
    _fenwick(u, k + 1, r)


def bk_matrix(n: int) -> np.ndarray:
    padded = 2 ** math.ceil(math.log(n, 2)) if n > 1 else 1
    u = np.zeros((n, n), dtype=np.uint8)
    _fenwick(u, 0, padded - 1)
    u = transitive_closure(u)
    return (u + np.eye(n, dtype=np.uint8)) % 2


def encode(spec: dict) -> dict:
    return from_linear_encoding(bk_matrix(spec["M"]))
