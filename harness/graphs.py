"""Non-square 2D lattice specifications, for the beyond-square-lattices
graph challenge (arXiv 2504.21636 Table II). Sibling to harness/lattice.py,
same shape and conventions -- harness/verify.py, score.py, evaluate.py, and
hamiltonian() are already graph-agnostic (they only consume
spec["M"]/spec["edges"] and a generic terms list), so nothing there
changes; this module is purely a new way to build a `spec`.

Like harness/lattice.py's rectangle(), each builder here fixes ONE canonical
default ordering -- there is no search over orderings on a submission's
behalf. A submission may still declare its own order(Lx, Ly) -> perm, which
overrides the default the same way it does for square lattices.
"""


def hex_lattice(Lx: int, Ly: int, periodic: bool = False, perm: list[int] | None = None) -> dict:
    """Honeycomb (hexagonal) lattice: Lx * Ly unit cells, 2 sites per cell
    (A, B sublattice), M = 2*Lx*Ly modes, every site degree 3 (degree < 3 at
    the open boundary when periodic=False).

    Canonical ordering: row-major over unit cells, A then B within each cell
    -- cell (x, y)'s A/B sites get raw indices 2*(y*Lx+x) and 2*(y*Lx+x)+1.
    This is the "most natural" default (row-major over cells, sublattice
    sites kept adjacent), not a searched-for one -- perm overrides it
    exactly like rectangle()'s custom ordering does.

    Bond directions per A(x, y) (the standard brick-wall embedding of the
    honeycomb lattice): to B(x, y) (same cell), B(x-1, y) (cell to the left),
    and B(x, y-1) (cell below). periodic=True wraps x, y modulo Lx, Ly
    instead of dropping out-of-range bonds.
    """
    m = 2 * Lx * Ly
    if perm is not None and (len(perm) != m or sorted(perm) != list(range(m))):
        raise ValueError(f"perm must be a permutation of range({m})")
    mode_of_raw = perm if perm is not None else list(range(m))

    def a_index(x, y):
        return mode_of_raw[2 * (y * Lx + x)]

    def b_index(x, y):
        return mode_of_raw[2 * (y * Lx + x) + 1]

    coords = {}
    for y in range(Ly):
        for x in range(Lx):
            coords[a_index(x, y)] = (x, y, "A")
            coords[b_index(x, y)] = (x, y, "B")

    def wrap(x, y):
        return x % Lx, y % Ly

    edges = []
    for y in range(Ly):
        for x in range(Lx):
            edges.append((a_index(x, y), b_index(x, y)))  # same cell

            if x - 1 >= 0:
                edges.append((a_index(x, y), b_index(x - 1, y)))
            elif periodic and Lx > 1:
                xw, yw = wrap(x - 1, y)
                edges.append((a_index(x, y), b_index(xw, yw)))

            if y - 1 >= 0:
                edges.append((a_index(x, y), b_index(x, y - 1)))
            elif periodic and Ly > 1:
                xw, yw = wrap(x, y - 1)
                edges.append((a_index(x, y), b_index(xw, yw)))

    return {"name": f"hex_{Lx}x{Ly}_{'periodic' if periodic else 'open'}", "M": m, "edges": edges, "coords": coords}


def triangular_lattice(Lx: int, Ly: int, periodic: bool = False, perm: list[int] | None = None) -> dict:
    """Triangular lattice: Lx * Ly sites (one per cell, same layout as
    harness.lattice.rectangle), each with up to 6 neighbours -- the square
    lattice's 4 nearest neighbours plus one diagonal direction (x+1, y+1).

    Canonical ordering: row-major, identical convention to
    harness.lattice.row_major_perm (perm[k] is the mode index assigned to
    the site whose row-major raw index is k). periodic=True wraps all three
    bond directions modulo Lx, Ly instead of dropping out-of-range bonds.
    """
    m = Lx * Ly
    if perm is not None and (len(perm) != m or sorted(perm) != list(range(m))):
        raise ValueError(f"perm must be a permutation of range({m})")
    mode_of_raw = perm if perm is not None else list(range(m))

    def index(x, y):
        return mode_of_raw[y * Lx + x]

    coords = {index(x, y): (x, y) for y in range(Ly) for x in range(Lx)}

    def wrap(x, y):
        return x % Lx, y % Ly

    seen = set()
    edges = []

    def add_edge(x0, y0, x1, y1):
        u, v = index(x0, y0), index(x1, y1)
        if u == v:
            return  # degenerate wrap-around at Lx/Ly == 1
        key = (min(u, v), max(u, v))
        if key in seen:
            return  # degenerate double-wrap at Lx/Ly == 2
        seen.add(key)
        edges.append((u, v))

    for y in range(Ly):
        for x in range(Lx):
            if x + 1 < Lx:
                add_edge(x, y, x + 1, y)
            elif periodic and Lx > 1:
                add_edge(x, y, *wrap(x + 1, y))

            if y + 1 < Ly:
                add_edge(x, y, x, y + 1)
            elif periodic and Ly > 1:
                add_edge(x, y, *wrap(x, y + 1))

            if x + 1 < Lx and y + 1 < Ly:
                add_edge(x, y, x + 1, y + 1)
            elif periodic and Lx > 1 and Ly > 1:
                add_edge(x, y, *wrap(x + 1, y + 1))

    return {
        "name": f"triangular_{Lx}x{Ly}_{'periodic' if periodic else 'open'}",
        "M": m,
        "edges": edges,
        "coords": coords,
    }


_BUILDERS = {
    "hexagonal": hex_lattice,
    "periodic_hexagonal": lambda Lx, Ly, perm=None: hex_lattice(Lx, Ly, periodic=True, perm=perm),
    "triangular": triangular_lattice,
    "periodic_triangular": lambda Lx, Ly, perm=None: triangular_lattice(Lx, Ly, periodic=True, perm=perm),
}

# Public, for scripts/submission_lib.py's manifest validation -- the single
# source of truth for "which graph names exist", so that list can't drift
# out of sync with _BUILDERS itself.
GRAPH_TYPES = frozenset(_BUILDERS)

# The ONE (Lx, Ly) per graph type that counts as directly comparable to
# arXiv 2504.21636 Table II -- our own fixed convention, not verified to
# match the paper's own (undisclosed) split. This matters because, unlike
# the square-lattice challenge, mode count M does NOT determine the graph
# here: e.g. hex-lattice Lx=8,Ly=4 and Lx=16,Ly=2 both give M=64 but are
# structurally different graphs (different edge counts/boundary
# structure). Gating the paper comparison on "M=64" alone would let a
# submission pick whichever aspect ratio happens to be easiest to encode
# well while still nominally qualifying -- gating on this exact pair
# instead means every submission in the "vs Table II" table is scored on
# the identical graph as every other one, so comparisons AMONG
# submissions stay rigorous even though the comparison to the paper's own
# number keeps the pre-existing shape-uncertainty caveat (see NOTES.md).
# Chosen to match the paper's M=64 exactly for every type: 2*8*4=64 for
# hex/periodic-hex, 8*8=64 for triangular/periodic-triangular.
CANONICAL_SHAPE = {
    "hexagonal": (8, 4),
    "periodic_hexagonal": (8, 4),
    "triangular": (8, 8),
    "periodic_triangular": (8, 8),
}


def build_spec(graph: str, Lx: int, Ly: int, order_fn=None) -> dict:
    """The graph-challenge analogue of harness.lattice.build_spec: dispatches
    on `graph` (one of _BUILDERS' keys) and applies order_fn(Lx, Ly) -> perm
    if given, else the builder's own canonical default. One place the
    "submission's ordering, or canonical default" fallback lives, so callers
    don't duplicate it -- mirrors harness.lattice.build_spec exactly.
    """
    if graph not in _BUILDERS:
        raise ValueError(f"unknown graph {graph!r}, expected one of {[*_BUILDERS]}")
    builder = _BUILDERS[graph]
    if order_fn is None:
        return builder(Lx, Ly)
    return builder(Lx, Ly, perm=order_fn(Lx, Ly))
