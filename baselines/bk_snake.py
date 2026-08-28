"""Bravyi-Kitaev under the snake ordering -- see baselines/bk.py for the
encoding construction itself; only the declared ordering differs. Snake
beats row_major on total Pauli weight for this encoding at (almost) every
size checked, at the cost of losing row_major's exact match to the paper's
published max weight (NOTES.md has the full per-size breakdown) --
registered separately so that tradeoff stays visible on the leaderboard
instead of being picked on the maintainers' behalf.
"""

from baselines.bk import encode
from harness.lattice import snake_perm


def order(Lx: int, Ly: int) -> list[int]:
    return snake_perm(Lx, Ly)
