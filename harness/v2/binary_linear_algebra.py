"""GF(2) linear algebra for stabilizer codes.

Assumes inputs are already well-formed binary arrays -- same division of
labor as harness/paulis.py, whose docstring makes the same assumption for
Pauli strings. Validation of untrusted submission data happens one layer
up, in harness/v2/verify.py.

Never use floating-point matrix rank for any of this: it doesn't see GF(2)
structure and silently gives the wrong answer for exactly the near-dependent
rows a stabilizer generator set produces (e.g. three rows where the third is
the XOR of the first two -- floating-point rank may or may not notice,
depending on numerical noise; GF(2) elimination always gets it right).
"""

import numpy as np


def _row_reduce(A: np.ndarray) -> np.ndarray:
    """Reduced row-echelon form over GF(2).

    Unlike a textbook forward-elimination-only sweep, this clears each pivot
    column from *every* other row (both above and below), not just rows
    below the pivot -- so by the time column processing moves on, a pivot
    row's own pivot bit is the only 1 anywhere in that column, permanently
    (no later step reintroduces one: later pivot rows always have a 0 in
    already-fixed pivot columns, so XORing them into another row can't set
    that column back to 1). That's what makes gf2_in_row_span's single-pass
    membership test correct: each returned row can be used to clear its own
    pivot column from a query vector independent of order.

    Returns the first `rank` rows only -- rows past the rank carry no new
    information relative to the returned ones.
    """
    A = np.asarray(A, dtype=np.uint8).copy() & 1
    n_rows, n_cols = A.shape
    rank = 0

    for col in range(n_cols):
        pivots = np.flatnonzero(A[rank:, col])
        if len(pivots) == 0:
            continue

        pivot = rank + int(pivots[0])
        if pivot != rank:
            A[[rank, pivot]] = A[[pivot, rank]]

        mask = A[:, col].astype(bool)
        mask[rank] = False
        A[mask] ^= A[rank]

        rank += 1
        if rank == n_rows:
            break

    return A[:rank]


def gf2_rank(A) -> int:
    """GF(2) rank of a binary matrix (any 0/1-valued array-like; entries
    outside {0,1} are reduced mod 2 first)."""
    return len(_row_reduce(np.asarray(A, dtype=np.uint8)))


class Gf2RowSpace:
    """A GF(2) row space, reduced once so repeated membership queries
    (`contains`) are cheap -- built for harness/v2/score.py's per-term
    certification loop, which asks "is this vector in the stabilizer span?"
    once per scored Hamiltonian term against the *same* stabilizer basis.
    Recomputing a fresh elimination on every query (as the module-level
    gf2_in_row_span convenience function below does) would redo that work
    from scratch each time.
    """

    def __init__(self, basis):
        """basis: a (r, n) binary array-like, r >= 0. Always pass a
        genuinely 2D array even when r == 0 (e.g. np.zeros((0, n))) -- this
        class doesn't guess the column count from an empty, shapeless input.
        """
        basis = np.asarray(basis, dtype=np.uint8) & 1
        self._basis = _row_reduce(basis)
        self._pivots = [int(np.flatnonzero(row)[0]) for row in self._basis]

    def rank(self) -> int:
        return len(self._basis)

    def contains(self, v) -> bool:
        v = np.asarray(v, dtype=np.uint8).copy() & 1
        for row, pivot in zip(self._basis, self._pivots):
            if v[pivot]:
                v ^= row
        return not v.any()


def gf2_in_row_span(v, basis) -> bool:
    """Whether `v` lies in the GF(2) row space spanned by `basis`'s rows.

    One-shot convenience wrapper around Gf2RowSpace -- prefer Gf2RowSpace
    directly when checking many vectors against the same basis.
    """
    return Gf2RowSpace(basis).contains(v)
