"""Parity basis: the linear encoding U = lower-triangular ones (diagonal
included). Dual to Jordan-Wigner in a specific sense: mode i's X-support
under this U is the suffix {i, i+1, ..., n-1} rather than JW's singleton
{i}, which pushes weight out of the number term and into hopping (an
X-string spanning the two modes) instead of JW's Z-string.
"""

import numpy as np

from harness.constructors import from_linear_encoding


def encode(spec: dict) -> dict:
    m = spec["M"]
    u = np.tril(np.ones((m, m), dtype=np.uint8))
    return from_linear_encoding(u)
