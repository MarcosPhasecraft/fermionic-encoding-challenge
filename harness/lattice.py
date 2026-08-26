"""Lattice specifications: builds `spec` dicts for rectangular fermionic lattices.

See PLAN.md Sec 1.1-1.2 for the data format. Only row_major ordering is
implemented so far; snake/diagonal/arbitrary permutation come with the
ordering-sensitivity test (Sec 1.7 Test 3).
"""


def rectangle(Lx: int, Ly: int, ordering: str = "row_major") -> dict:
    """Lx * Ly rectangular lattice, nearest-neighbour edges. Ly=1 is a chain."""
    if ordering != "row_major":
        raise NotImplementedError(f"ordering {ordering!r} not implemented yet")

    def index(x, y):
        return y * Lx + x

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


_VALID_MODELS = {"hopping", "quadratic", "full"}


def hamiltonian(spec: dict, model: str = "quadratic") -> list[tuple[int, ...]]:
    """Majorana-index term list for spec's Hamiltonian. See PLAN.md Sec 1.3.

    Each term is a tuple of Majorana indices whose product is one term of
    the Hamiltonian (index convention: 2j=gamma_j, 2j+1=gammabar_j, Sec 1.1).
    A real-coefficient hopping a_i^dagger a_j + h.c. is (i/2)(gamma_i
    gammabar_j - gammabar_i gamma_j) -- two bilinears. A number operator n_i
    is (1/2)(I + i gamma_i gammabar_i) -- one bilinear, dropping the
    weight-0 identity part.
    """
    if model not in _VALID_MODELS:
        raise ValueError(f"unknown model {model!r}, expected one of {_VALID_MODELS}")

    m = spec["M"]
    terms = []

    for i, j in spec["edges"]:
        terms.append((2 * i, 2 * j + 1))
        terms.append((2 * i + 1, 2 * j))

    if model in ("quadratic", "full"):
        for i in range(m):
            terms.append((2 * i, 2 * i + 1))

    if model == "full":
        for i, j in spec["edges"]:
            # n_i * n_j: quartic in Majoranas, support is all four combined.
            terms.append((2 * i, 2 * i + 1, 2 * j, 2 * j + 1))

    return terms
