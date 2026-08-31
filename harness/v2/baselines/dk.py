"""Derby-Klassen: "A Compact Fermion To Qubit Mapping", arXiv 2003.06939
(Charles Derby, Joel Klassen), square-lattice construction (their Sec.
"square lattice" + Fig. 1-3, and the Supplementary Material's explicit
correctness proof) -- reconstructed directly from the paper's PDF (fetched
and read, including the figures) rather than from memory or a lossy text
extraction, per this repo's own CLAUDE.md rule against reconstructing a
paper's content from prose alone when the primary source is checkable.

PAPER-SOURCED, verbatim or near-verbatim (verified against the actual PDF):
  - Qubits: one "vertex" qubit per fermionic mode, plus one "face" qubit
    per ODD face of a checkerboard coloring of the lattice's unit-square
    faces (Eq. 9 and surrounding text). Fewer than 1.5M qubits total.
  - Vertex operator: V~_j := Z_j (Eq. 9).
  - Edge operator (Eq. 7-8), for edge (i,j) with i the tail of its
    assigned arrow and j the head:
        E~_ij := X_i Y_j X_f(i,j)   if (i,j) oriented downwards
                -X_i Y_j X_f(i,j)   if (i,j) oriented upwards
                 X_i Y_j Y_f(i,j)   if (i,j) horizontal
        E~_ji := -E~_ij
    where f(i,j) is the unique ODD face adjacent to edge (i,j); if no odd
    face is adjacent (a boundary edge), the face-qubit factor is omitted
    entirely (stated explicitly in the paper).
  - Edges are oriented "to circulate around the even faces clockwise or
    counterclockwise, alternating on every row of faces" (quoted). Only
    EVEN faces drive an orientation; odd faces get no circulation of their
    own and their would-be stabilizer is trivial (identity).
  - A single Majorana at a corner bounding an odd face: if both its
    incident edges point INTO the corner, the mapped Majorana there is
    X_corner; if both point AWAY, it's Y_corner (quoted, with a proof
    sketch in the Supplementary Material that this, together with the
    edge/vertex operators, generates the entire fermionic algebra).
  - Table I: this construction gives max Pauli weight 3 for hopping terms,
    2 for the Coulomb (n_i n_j) term, on a square lattice, using the full
    fermionic Fock space (not a restricted parity sector) whenever the
    number of faces nF = (Lx-1)(Ly-1) is EVEN ("case I" in the
    Supplementary Material's Theorems 1-3). When nF is odd (Theorems 2-3;
    equivalently Lx and Ly both even), the construction instead represents
    either the even-parity-only Fock space or the full space plus one
    extra logical qubit -- neither of which fits this harness's
    contract of "exactly the full M-mode Fock space, no more, no less"
    (harness.v2.verify's codespace_dimension check). encode() raises a
    clear error for these sizes rather than silently returning something
    that would fail verification for a non-obvious reason -- matching this
    extension's own guidance on finite-size parity cases: mark a size
    unavailable rather than fake a completion. (Lx == Ly == 1, M == 1, has
    zero faces at all -- also excluded, trivially: there is no lattice for
    DK's construction to act
    on.)

MY OWN COMPLETION (not directly given by the paper's text/figures -- the
paper's Fig. 1 illustrates one full worked example but the general
algorithmic rule for "which way do arrows point" beyond the verbal
description above, and the choice of spanning structure used to build a
single Majorana per vertex out of the edge operators, are filled in here):

  - Concretely: face (fx, fy) [corners (fx,fy),(fx+1,fy),(fx,fy+1),
    (fx+1,fy+1)] is EVEN iff (fx+fy) is even. A horizontal edge in vertex
    row y is oriented left-to-right if y is even, right-to-left if y is
    odd; a vertical edge in vertex column x is oriented bottom-to-top (in
    increasing-y-is-"down" terms: from the larger-y endpoint to the
    smaller) if x is even, top-to-bottom if x is odd -- uniform per row or
    column regardless of the other coordinate. This was *derived*, not
    guessed: computing the circulation implied by the paper's own rule
    from both faces neighbouring an interior edge always agrees and always
    reduces to this row/column-uniform "comb" pattern (see NOTES.md), and
    it's simply extended unchanged to boundary edges that only have one
    neighbouring face (or none) -- the natural, simplest continuation of
    the same uniform rule, not a separately-invented case.
  - A single Majorana is anchored at one corner bounding an odd face
    (there are always at least one whenever nF is even and M > 1; picked
    deterministically among the lattice's 4 corners). Every other vertex's
    Majorana is then obtained via the *exact* operator identity
    gamma_k = i * gamma_j * E_jk (from E_jk := -i*gamma_j*gamma_k),
    applied along an L-shaped path (across the anchor's row, then up the
    target's column) from the anchor to that vertex -- an arbitrary but
    fixed spanning-tree choice; the paper only requires *some* fixed
    choice, since any two differ by a stabilizer.

Once a global Majorana pair (gamma_j, gammabar_j) is fixed this way for
every vertex (satisfying the Clifford algebra *exactly*, by the
correctness argument above -- verified empirically too, see
tests/test_v2_dk.py), the paper's own edge/vertex operators translate into
*exact* (not merely certified-but-approximate) closed-form low-weight
representatives for every one of this harness's Hamiltonian term
categories, via gammabar_j = i*gamma_j*Z_j (from V_j := -i*gamma_j*gammabar_j
= Z_j):

    Num   (2j, 2j+1)                     -> Z_j                    (exact cancellation)
    Int   (2i,2i+1)/(2j,2j+1)/quartic     -> Z_i / Z_j / Z_i (xor) Z_j
    ImHop (2i,2j)                         -> E~_ij as-is
    ImHop (2i+1,2j+1)                     -> E~_ij (xor) Z_i (xor) Z_j
    ReHop (2i,2j+1)                       -> E~_ij (xor) Z_j
    ReHop (2i+1,2j)                       -> E~_ij (xor) Z_i

(XORing in Z on a qubit where E~_ij already has a Y just swaps it to X --
same weight -- so every one of the six representatives above has *exactly*
the same weight as E~_ij itself, reproducing Table I's claimed max weight
3 for every hopping-type term, not just a subset of them.)
"""

import numpy as np

from harness.paulis import xz_to_string


def _faces(Lx, Ly):
    return [(fx, fy) for fy in range(Ly - 1) for fx in range(Lx - 1)]


def _face_is_even(fx, fy):
    return (fx + fy) % 2 == 0


def _edge_orientation(v1, v2):
    """(v1, v2) an unordered grid-adjacent pair -> (tail, head) per the
    row/column-uniform "comb" pattern derived in this module's docstring.
    """
    (x1, y1), (x2, y2) = v1, v2
    if y1 == y2:  # horizontal
        y = y1
        lo, hi = (v1, v2) if x1 < x2 else (v2, v1)
        return (lo, hi) if y % 2 == 0 else (hi, lo)
    else:  # vertical
        x = x1
        lo, hi = (v1, v2) if y1 < y2 else (v2, v1)  # lo = smaller y, hi = larger y
        return (hi, lo) if x % 2 == 0 else (lo, hi)


def _direction_type(tail, head):
    if tail[1] == head[1]:
        return "horizontal"
    return "downward" if head[1] > tail[1] else "upward"


def _odd_face_for_edge(v1, v2, Lx, Ly):
    (x1, y1), (x2, y2) = v1, v2
    if y1 == y2:  # horizontal: faces (x,y-1) [above] and (x,y) [below]
        x, y = min(x1, x2), y1
        candidates = [(x, y - 1), (x, y)]
    else:  # vertical: faces (x-1,y) [left] and (x,y) [right]
        x, y = x1, min(y1, y2)
        candidates = [(x - 1, y), (x, y)]
    for fx, fy in candidates:
        if 0 <= fx < Lx - 1 and 0 <= fy < Ly - 1 and not _face_is_even(fx, fy):
            return (fx, fy)
    return None


def _build_geometry(spec):
    Lx, Ly, m = spec["Lx"], spec["Ly"], spec["M"]
    pos_to_mode = {pos: mode for mode, pos in spec["coords"].items()}

    odd_faces = [f for f in _faces(Lx, Ly) if not _face_is_even(*f)]
    n_faces = len(_faces(Lx, Ly))
    if n_faces % 2 != 0:
        raise ValueError(
            f"DK baseline unavailable at {Lx}x{Ly}: {n_faces} faces (odd) means Lx, Ly "
            "are both even -- the construction then represents a restricted/extended "
            "Fock space (Supplementary Material Theorems 2-3), not the plain full "
            "M-mode space this harness requires. See this module's docstring."
        )
    if n_faces == 0:
        raise ValueError(f"DK baseline unavailable at {Lx}x{Ly}: no faces to build stabilizers from")

    face_qubit = {f: m + k for k, f in enumerate(odd_faces)}
    n_ancillas = len(odd_faces)
    n_qubits = m + n_ancillas

    def edge_xz(v1, v2):
        tail, head = _edge_orientation(v1, v2)
        dtype = _direction_type(tail, head)
        odd_face = _odd_face_for_edge(v1, v2, Lx, Ly)
        x = np.zeros(n_qubits, dtype=np.uint8)
        z = np.zeros(n_qubits, dtype=np.uint8)
        t, h = pos_to_mode[tail], pos_to_mode[head]
        x[t] = 1  # X on the tail
        x[h] = 1; z[h] = 1  # Y on the head
        if odd_face is not None:
            f = face_qubit[odd_face]
            if dtype == "horizontal":
                x[f] = 1; z[f] = 1  # Y on the face qubit
            else:
                x[f] = 1  # X on the face qubit
        return x, z

    edge_cache = {}
    for i, j in spec["edges"]:
        edge_cache[frozenset((i, j))] = edge_xz(spec["coords"][i], spec["coords"][j])

    # Anchor: a corner bounding an odd face. (0,0) always borders face
    # (0,0), which is even by this module's convention, so it's never a
    # valid anchor -- check the other three deterministically.
    corners = [(Lx - 1, 0), (0, Ly - 1), (Lx - 1, Ly - 1)]
    anchor = None
    for c in corners:
        cx, cy = c
        adjacent_face = (min(cx, Lx - 2), min(cy, Ly - 2))
        if not _face_is_even(*adjacent_face):
            anchor = c
            break
    if anchor is None:
        raise ValueError(f"DK baseline: no odd-bounding corner found at {Lx}x{Ly} -- unexpected, see module docstring")

    anchor_mode = pos_to_mode[anchor]
    incident = [v for v in spec["coords"].values() if _is_grid_neighbor(v, anchor)]
    directions = [_edge_orientation(anchor, v) for v in incident]
    all_in = all(head == anchor for _, head in directions)
    all_out = all(tail == anchor for tail, _ in directions)
    if all_in:
        anchor_x, anchor_z = np.zeros(n_qubits, dtype=np.uint8), np.zeros(n_qubits, dtype=np.uint8)
        anchor_x[anchor_mode] = 1  # X
    elif all_out:
        anchor_x, anchor_z = np.zeros(n_qubits, dtype=np.uint8), np.zeros(n_qubits, dtype=np.uint8)
        anchor_x[anchor_mode] = 1; anchor_z[anchor_mode] = 1  # Y
    else:
        raise ValueError(f"DK baseline: anchor corner {anchor} has mixed edge directions -- unexpected, see module docstring")

    # gamma_j for every vertex j, via an L-shaped path from the anchor.
    ax, ay = anchor
    gamma_x = {anchor_mode: anchor_x.copy()}
    gamma_z = {anchor_mode: anchor_z.copy()}
    for mode, (tx, ty) in spec["coords"].items():
        if mode == anchor_mode:
            continue
        gx, gz = anchor_x.copy(), anchor_z.copy()
        xs = range(min(ax, tx), max(ax, tx))
        for x in xs:
            step = ((x, ay), (x + 1, ay))
            ex, ez = edge_cache[frozenset((pos_to_mode[step[0]], pos_to_mode[step[1]]))]
            gx ^= ex; gz ^= ez
        ys = range(min(ay, ty), max(ay, ty))
        for y in ys:
            step = ((tx, y), (tx, y + 1))
            ex, ez = edge_cache[frozenset((pos_to_mode[step[0]], pos_to_mode[step[1]]))]
            gx ^= ex; gz ^= ez
        gamma_x[mode], gamma_z[mode] = gx, gz

    return {
        "n_qubits": n_qubits, "n_ancillas": n_ancillas,
        "pos_to_mode": pos_to_mode, "face_qubit": face_qubit,
        "edge_cache": edge_cache, "gamma_x": gamma_x, "gamma_z": gamma_z,
    }


def _is_grid_neighbor(v, w):
    return abs(v[0] - w[0]) + abs(v[1] - w[1]) == 1


def encode(spec: dict) -> dict:
    geo = _build_geometry(spec)
    m = spec["M"]
    n_qubits = geo["n_qubits"]

    majoranas = []
    for j in range(m):
        gx, gz = geo["gamma_x"][j], geo["gamma_z"][j]
        majoranas.append(xz_to_string(gx, gz))  # gamma_j
        # gammabar_j = gamma_j XOR Z_j (exact identity -- see module docstring)
        gbx, gbz = gx.copy(), gz.copy()
        gbz[j] ^= 1
        majoranas.append(xz_to_string(gbx, gbz))

    stabilizers = []
    Lx, Ly = spec["Lx"], spec["Ly"]
    for fx, fy in _faces(Lx, Ly):
        if not _face_is_even(fx, fy):
            continue
        corners = [(fx, fy), (fx + 1, fy), (fx + 1, fy + 1), (fx, fy + 1)]
        sx = np.zeros(n_qubits, dtype=np.uint8)
        sz = np.zeros(n_qubits, dtype=np.uint8)
        for a, b in zip(corners, corners[1:] + corners[:1]):
            ma, mb = geo["pos_to_mode"][a], geo["pos_to_mode"][b]
            ex, ez = geo["edge_cache"][frozenset((ma, mb))]
            sx ^= ex; sz ^= ez
        stabilizers.append(xz_to_string(sx, sz))

    return {"n_qubits": n_qubits, "majoranas": majoranas, "stabilizers": stabilizers, "_dk_geometry": geo}


def represent(term, raw_pauli: str, spec: dict, mapping: dict) -> str:
    geo = mapping["_dk_geometry"]
    n_qubits = geo["n_qubits"]

    def z_only(j):
        x = np.zeros(n_qubits, dtype=np.uint8)
        z = np.zeros(n_qubits, dtype=np.uint8)
        z[j] = 1
        return x, z

    if term.category == "num":
        _, j = term.source
        x, z = z_only(j)
        return xz_to_string(x, z)

    _, i, j = term.source

    if term.category == "int":
        if len(term.majoranas) == 4:
            x1, z1 = z_only(i)
            x2, z2 = z_only(j)
            return xz_to_string(x1 ^ x2, z1 ^ z2)
        target = i if term.majoranas == (2 * i, 2 * i + 1) else j
        x, z = z_only(target)
        return xz_to_string(x, z)

    # rehop / imhop
    ex, ez = geo["edge_cache"][frozenset((i, j))]
    ex, ez = ex.copy(), ez.copy()
    if term.majoranas == (2 * i, 2 * j):
        pass
    elif term.majoranas == (2 * i + 1, 2 * j + 1):
        ez[i] ^= 1; ez[j] ^= 1
    elif term.majoranas == (2 * i, 2 * j + 1):
        ez[j] ^= 1
    elif term.majoranas == (2 * i + 1, 2 * j):
        ez[i] ^= 1
    return xz_to_string(ex, ez)
