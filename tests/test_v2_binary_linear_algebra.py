"""Tests for harness.v2.binary_linear_algebra -- GF(2) rank and row-span
membership, the machinery behind stabilizer independence/dimension checks
(harness/v2/verify.py) and stabilizer-dressed representative certification
(harness/v2/score.py).
"""

import numpy as np

from harness.v2.binary_linear_algebra import Gf2RowSpace, gf2_in_row_span, gf2_rank


def test_gf2_rank_independent_rows():
    assert gf2_rank([[0, 0, 1, 1], [1, 1, 0, 0]]) == 2  # ZI, IZ in (x|z) form


def test_gf2_rank_dependent_row_is_xor_of_others():
    a = [1, 1, 0, 1, 1, 0]
    b = [0, 1, 1, 0, 1, 1]
    c = [x ^ y for x, y in zip(a, b)]
    assert gf2_rank([a, b, c]) == 2


def test_gf2_rank_all_zero_row():
    assert gf2_rank([[0, 0, 0]]) == 0


def test_gf2_rank_empty_matrix():
    assert gf2_rank(np.zeros((0, 4), dtype=np.uint8)) == 0


def test_gf2_rank_against_reference_elimination():
    rng = np.random.default_rng(0)
    for _ in range(20):
        shape = (rng.integers(1, 6), rng.integers(1, 6))
        A = rng.integers(0, 2, size=shape)
        assert gf2_rank(A) == _reference_gf2_rank(A)


def _reference_gf2_rank(A: np.ndarray) -> int:
    """Independent, unvectorized elimination -- a different implementation
    path than harness.v2.binary_linear_algebra._row_reduce, for the random
    cross-check above to be a genuine test rather than comparing a function
    against itself.
    """
    A = [row[:] for row in (A.astype(int) % 2).tolist()]
    n_rows = len(A)
    n_cols = len(A[0]) if n_rows else 0
    rank = 0
    for col in range(n_cols):
        pivot = next((r for r in range(rank, n_rows) if A[r][col] == 1), None)
        if pivot is None:
            continue
        A[rank], A[pivot] = A[pivot], A[rank]
        for r in range(n_rows):
            if r != rank and A[r][col] == 1:
                A[r] = [a ^ b for a, b in zip(A[r], A[rank])]
        rank += 1
    return rank


def test_row_span_membership_accepts_span_members():
    basis = [[1, 0, 1, 0], [0, 1, 0, 1]]
    assert gf2_in_row_span([1, 0, 1, 0], basis)
    assert gf2_in_row_span([0, 1, 0, 1], basis)
    assert gf2_in_row_span([1, 1, 1, 1], basis)  # sum of both rows
    assert gf2_in_row_span([0, 0, 0, 0], basis)  # the zero vector is always in any span


def test_row_span_membership_rejects_outside_span():
    basis = [[1, 0, 1, 0], [0, 1, 0, 1]]
    assert not gf2_in_row_span([1, 0, 0, 0], basis)


def test_row_span_membership_trivial_span_only_contains_zero():
    empty_basis = np.zeros((0, 4), dtype=np.uint8)
    assert gf2_in_row_span([0, 0, 0, 0], empty_basis)
    assert not gf2_in_row_span([1, 0, 0, 0], empty_basis)


def test_gf2_row_space_reused_across_many_queries_matches_one_shot():
    basis = [[1, 1, 0, 0], [0, 0, 1, 1]]
    space = Gf2RowSpace(basis)
    queries = [[1, 1, 0, 0], [1, 1, 1, 1], [1, 0, 0, 0], [0, 0, 0, 0]]
    for v in queries:
        assert space.contains(v) == gf2_in_row_span(v, basis)
    assert space.rank() == 2
