"""Ternary tree: a linear encoding built from a Sierpinski-tree matrix.

Same idea as Bravyi-Kitaev's Fenwick construction, but a ternary (three-way)
recursive partition instead of binary: pad to the next power of 3,
recursively connect the middle third's midpoint to the midpoints of the
other two thirds, transitive-close, add the identity. Cross-checked against
arXiv 2504.21636's released code (hexaly_quadratic_assignment.py's
sierpinski()/tt()) -- reimplemented in plain numpy, preserving the exact
recursion, padding, and the reference's float-arithmetic midpoints (the
range doesn't always split evenly into thirds).
"""

import math

import numpy as np

from harness.constructors import from_linear_encoding, transitive_closure


def _mid(a: float, b: float) -> int:
    return int((a + b) // 2)


def _sierpinski(u: np.ndarray, c: float, r: float) -> None:
    if c == r:
        return
    third = (r - c + 1) / 3
    l = c + third
    rr = c + 2 * third
    if _mid(l, rr - 1) < u.shape[0] and _mid(c, l - 1) < u.shape[1]:
        u[_mid(l, rr - 1), _mid(c, l - 1)] = 1
    if _mid(l, rr - 1) < u.shape[0] and _mid(rr, r) < u.shape[1]:
        u[_mid(l, rr - 1), _mid(rr, r)] = 1
    _sierpinski(u, c, l - 1)
    _sierpinski(u, l, rr - 1)
    _sierpinski(u, rr, r)


def tt_matrix(n: int) -> np.ndarray:
    padded = 3 ** math.ceil(math.log(n, 3)) if n > 1 else 1
    u = np.zeros((n, n), dtype=np.uint8)
    _sierpinski(u, 0, padded - 1)
    u = transitive_closure(u)
    return (u + np.eye(n, dtype=np.uint8)) % 2


def encode(spec: dict) -> dict:
    return from_linear_encoding(tt_matrix(spec["M"]))
