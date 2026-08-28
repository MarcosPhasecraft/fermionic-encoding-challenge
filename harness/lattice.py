"""Lattice specifications: builds `spec` dicts for rectangular fermionic lattices.

See PLAN.md Sec 1.1-1.2 for the data format and orderings, Sec 1.7 Test 3
for the ordering-sensitivity check.
"""


def row_major_perm(Lx: int, Ly: int) -> list[int]:
    return list(range(Lx * Ly))


def snake_perm(Lx: int, Ly: int) -> list[int]:
    """Boustrophedon: row 0 left-to-right, row 1 right-to-left, etc."""
    perm = [0] * (Lx * Ly)
    mode = 0
    for y in range(Ly):
        xs = range(Lx) if y % 2 == 0 else range(Lx - 1, -1, -1)
        for x in xs:
            perm[y * Lx + x] = mode
            mode += 1
    return perm


def diagonal_perm(Lx: int, Ly: int) -> list[int]:
    """Anti-diagonals x+y=const, in order, each scanned by increasing x."""
    perm = [0] * (Lx * Ly)
    mode = 0
    for d in range(Lx + Ly - 1):
        for x in range(max(0, d - Ly + 1), min(d, Lx - 1) + 1):
            y = d - x
            perm[y * Lx + x] = mode
            mode += 1
    return perm


_ORDERINGS = {
    "row_major": row_major_perm,
    "snake": snake_perm,
    "diagonal": diagonal_perm,
}


def rectangle(Lx: int, Ly: int, ordering: str = "row_major", perm: list[int] | None = None) -> dict:
    """Lx * Ly rectangular lattice, nearest-neighbour edges. Ly=1 is a chain.

    ordering: one of "row_major", "snake", "diagonal", or "custom" (with
    `perm` supplied). `perm[k]` is the mode index assigned to the site whose
    row-major raw index is `k` -- built-in orderings produce this array
    internally; "custom" lets the caller supply an arbitrary one directly.
    """
    if ordering == "custom":
        if perm is None or len(perm) != Lx * Ly or sorted(perm) != list(range(Lx * Ly)):
            raise ValueError(f"ordering='custom' requires perm to be a permutation of range({Lx * Ly})")
        mode_of_raw = perm
    elif ordering in _ORDERINGS:
        mode_of_raw = _ORDERINGS[ordering](Lx, Ly)
    else:
        raise ValueError(f"unknown ordering {ordering!r}, expected one of {[*_ORDERINGS, 'custom']}")

    def index(x, y):
        return mode_of_raw[y * Lx + x]

    coords = {index(x, y): (x, y) for y in range(Ly) for x in range(Lx)}

    edges = []
    for y in range(Ly):
        for x in range(Lx):
            if x + 1 < Lx:
                edges.append((index(x, y), index(x + 1, y)))
            if y + 1 < Ly:
                edges.append((index(x, y), index(x, y + 1)))

    return {
        "name": f"rectangle_{Lx}x{Ly}_{ordering}",
        "Lx": Lx,
        "Ly": Ly,
        "M": Lx * Ly,
        "edges": edges,
        "coords": coords,
    }


def build_spec(Lx: int, Ly: int, order_fn=None) -> dict:
    """rectangle(Lx, Ly), using order_fn(Lx, Ly) -> perm if given (normally a
    submission's own declared order()), else row_major. The one place the
    "submission's ordering, or row_major default" fallback lives -- callers
    (run.py, scripts/submit_baseline.py, scripts/update_leaderboard.py) all
    use this instead of duplicating the fallback themselves.
    """
    if order_fn is None:
        return rectangle(Lx, Ly, ordering="row_major")
    return rectangle(Lx, Ly, ordering="custom", perm=order_fn(Lx, Ly))


_VALID_MODELS = {"hopping", "quadratic", "full"}


def hamiltonian(spec: dict, model: str = "quadratic") -> list[tuple[int, ...]]:
    """Majorana-index term list for spec's Hamiltonian. See PLAN.md Sec 1.3.

    Each term is a tuple of Majorana indices whose product is one term of
    the Hamiltonian (index convention: 2j=gamma_j, 2j+1=gammabar_j, Sec 1.1).
    Follows arXiv 2504.21636 eq. 10: H_q = Sum_i c_i A_i^dag A_i + Sum_E
    c^ii_jj A_i^dag A_i A_j^dag A_j + Sum_E (c_ij A_i^dag A_j + c_ij^* A_j^dag
    A_i), interaction/hopping summed over edges E only, not all pairs.

    Hermiticity forces c_i and c^ii_jj real (A_i^dag A_i and A_i^dag A_i
    A_j^dag A_j are each already Hermitian on their own), so Num and the
    quartic interaction piece need no real/imaginary split. The hopping term
    is the one place a genuinely complex coefficient survives -- c_ij A_i^dag
    A_j is not Hermitian alone, hence the +h.c. -- so a real-coefficient
    hopping a_i^dagger a_j + h.c. is (i/2)(gamma_i gammabar_j - gammabar_i
    gamma_j) [[ReHop]], and i(a_i^dagger a_j - a_j^dagger a_i) [[ImHop]] is
    (i/2)(gamma_i gamma_j + gammabar_i gammabar_j); a generic complex c_ij
    needs both. A number operator n_i is (1/2)(I + i gamma_i gammabar_i) --
    one bilinear, dropping the weight-0 identity part. n_i * n_j is (1/4)(I +
    i*G_i + i*G_j - G_i*G_j) with G_i = gamma_i gammabar_i -- THREE
    nontrivial bilinears (the two induced number-like pieces plus the
    quartic product), not just the quartic one; cross-checked against arXiv
    2504.21636's released code (map_cost's Rep term = weight(F_r) +
    weight(F_c) + weight(F_r xor F_c)).
    """
    if model not in _VALID_MODELS:
        raise ValueError(f"unknown model {model!r}, expected one of {_VALID_MODELS}")

    m = spec["M"]
    terms = []

    for i, j in spec["edges"]:
        terms.append((2 * i, 2 * j + 1))      # ReHop: (gamma_i, gammabar_j)
        terms.append((2 * i + 1, 2 * j))      # ReHop: (gammabar_i, gamma_j)
        terms.append((2 * i, 2 * j))          # ImHop: (gamma_i, gamma_j)
        terms.append((2 * i + 1, 2 * j + 1))  # ImHop: (gammabar_i, gammabar_j)

    if model in ("quadratic", "full"):
        for i in range(m):
            terms.append((2 * i, 2 * i + 1))

    if model == "full":
        for i, j in spec["edges"]:
            # n_i * n_j expands to three terms: the two induced number-like
            # bilinears (same Pauli strings as Num, counted separately here
            # since they arise from a distinct physical term) plus the
            # genuine quartic product.
            terms.append((2 * i, 2 * i + 1))
            terms.append((2 * j, 2 * j + 1))
            terms.append((2 * i, 2 * i + 1, 2 * j, 2 * j + 1))

    return terms
