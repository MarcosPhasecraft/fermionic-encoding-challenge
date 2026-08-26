"""Tests for harness.constructors.from_linear_encoding -- the general
ancilla-free linear encoding (arXiv 2504.21636 eq. 18).
"""

import numpy as np
import pytest

from baselines.jw import encode as jw_encode
from harness.constructors import from_linear_encoding
from harness.verify import verify


@pytest.mark.parametrize("n", [2, 3, 5, 9])
def test_identity_reproduces_jw_exactly(n):
    # The strongest available check on the general machinery: feeding it
    # U=I must reproduce the hand-written JW baseline character-for-character,
    # not just "pass verify()" -- this catches sign/index errors that a
    # valid-but-different mapping wouldn't.
    reconstructed = from_linear_encoding(np.eye(n, dtype=np.uint8))
    reference = jw_encode({"M": n})
    assert reconstructed["majoranas"] == reference["majoranas"]


def test_singular_matrix_raises():
    singular = np.array([[1, 1], [1, 1]], dtype=np.uint8)  # not invertible over GF(2)
    with pytest.raises(ValueError):
        from_linear_encoding(singular)


@pytest.mark.parametrize("n", [2, 5, 9])
def test_lower_triangular_u_gives_valid_encoding(n):
    # This is the parity-basis U; check it's valid in general, independent
    # of baselines/parity.py, to isolate the constructor from the baseline.
    u = np.tril(np.ones((n, n), dtype=np.uint8))
    mapping = from_linear_encoding(u)
    spec = {"name": "test", "M": n}
    assert verify(spec, mapping)["passed"]
