"""Jordan-Wigner baseline: gamma_j -> Z^j X I^(M-j-1), gammabar_j -> Z^j Y I^(M-j-1).

Frozen reference implementation, trusted for Stage 1 calibration. Depends
only on spec["M"] -- JW cares about linear mode order, not lattice geometry,
so the same function handles a 1D chain and a flattened 2D lattice identically.

order() declares row_major -- proven jointly optimal for both total and max
Pauli weight at every grid size checked (NOTES.md's closed form), unlike
every other baseline here, which trades total against max between
row_major and snake.
"""

from harness.lattice import row_major_perm


def order(Lx: int, Ly: int) -> list[int]:
    return row_major_perm(Lx, Ly)


def encode(spec: dict) -> dict:
    m = spec["M"]
    majoranas = []
    for j in range(m):
        prefix = "Z" * j
        suffix = "I" * (m - j - 1)
        majoranas.append(prefix + "X" + suffix)  # gamma_j
        majoranas.append(prefix + "Y" + suffix)  # gammabar_j
    return {
        "n_qubits": m,
        "majoranas": majoranas,
        "stabilizers": [],
    }
