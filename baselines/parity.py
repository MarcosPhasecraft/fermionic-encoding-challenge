"""Parity basis: the linear encoding U = lower-triangular ones (diagonal
included). Dual to Jordan-Wigner in a specific sense: mode i's X-support
under this U is the suffix {i, i+1, ..., n-1} rather than JW's singleton
{i}, which pushes weight out of the number term and into hopping (an
X-string spanning the two modes) instead of JW's Z-string.

order() declares row_major, which wins max weight at every size checked --
snake wins total weight instead (see baselines/parity_snake.py and NOTES.md
for the full breakdown); no single one of the built-in orderings is best on
both metrics for this encoding.
"""

import numpy as np

from harness.constructors import from_linear_encoding
from harness.lattice import row_major_perm


def order(Lx: int, Ly: int) -> list[int]:
    return row_major_perm(Lx, Ly)


def encode(spec: dict) -> dict:
    m = spec["M"]
    u = np.tril(np.ones((m, m), dtype=np.uint8))
    return from_linear_encoding(u)
