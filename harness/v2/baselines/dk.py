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
    2 for the Coulomb (n_i n_j) term, on a square lattice.
  - The face count nF = (Lx-1)(Ly-1) splits the sizes into the
    Supplementary Material's three cases, and BOTH reachable ones are
    implemented here (see _colour_flip):
      * nF even (case I, Theorem 1): the colouring's two classes are equal
        and the construction encodes the full Fock space directly, in
        m + nF/2 qubits.
      * nF odd, i.e. Lx and Ly both even: which class carries the face
        qubits is a free labelling choice, and the two choices differ.
        Minority-odd is case II (Theorem 2), encoding only the
        even-parity subspace -- half of Fock space, unusable here.
        Majority-odd is case III (Theorem 3): m + ceil(nF/2) qubits
        encoding C^2 (x) F_m, the full Fock space PLUS one extra logical
        qubit. The paper then notes, of the four corner operators it
        builds in that case, that "if one treats one of these operators
        as a stabilizer, then one restricts to the full fermionic code
        space without an extra logical qubit" -- which is exactly what
        this module does (see the logical_stabilizer construction below),
        so case III sizes are fully supported with no extension beyond
        the paper. Their qubit counts land exactly on Table I's own
        "majority odd faces" column, 1.5L^2 - L + 1.
    (Lx == Ly == 1, M == 1, has zero faces at all -- excluded, trivially:
    there is no lattice for DK's construction to act on.)

MY OWN COMPLETION (not directly given by the paper's text/figures -- the
paper's Fig. 1 illustrates one full worked example but the general
algorithmic rule for "which way do arrows point" beyond the verbal
description above, and the choice of spanning structure used to build a
single Majorana per vertex out of the edge operators, are filled in here):

  - Concretely: face (fx, fy) [corners (fx,fy),(fx+1,fy),(fx,fy+1),
    (fx+1,fy+1)] is EVEN iff (fx+fy+flip) is even, for the colouring flip
    _colour_flip picks. A horizontal edge in vertex row y is oriented
    left-to-right if y is even, right-to-left if y is odd; a vertical edge
    in vertex column x is oriented bottom-to-top (in increasing-y-is-"down"
    terms: from the larger-y endpoint to the smaller) if x is even,
    top-to-bottom if x is odd -- uniform per row or column regardless of
    the other coordinate, and with the VERTICAL rule reversing when the
    colouring flips (see _edge_orientation: arrows circulate around the
    even faces, so relabelling which class is even reorients them). This
    was *derived*, not guessed: computing the circulation implied by the
    paper's own rule from both faces neighbouring an interior edge always
    agrees and always reduces to this row/column-uniform "comb" pattern
    (see NOTES.md), and it's simply extended unchanged to boundary edges
    that only have one neighbouring face (or none) -- the natural,
    simplest continuation of the same uniform rule, not a
    separately-invented case.
  - A single Majorana is anchored at one corner bounding an odd face
    (picked deterministically among the lattice's 4 corners). Every other
    vertex's Majorana is then obtained via the *exact* operator identity
    gamma_k = i * gamma_j * E_jk (from E_jk := -i*gamma_j*gamma_k),
    applied along an L-shaped path (across the anchor's row, then up the
    target's column) from the anchor to that vertex -- an arbitrary but
    fixed spanning-tree choice; the paper only requires *some* fixed
    choice, since any two differ by a stabilizer.
  - In case III, the extra stabilizer collapsing the spare logical qubit
    is built as the product of the corner injections at two NON-anchor
    corners, transported to a common site: with the anchor playing the
    paper's A_i = gamma~_i (x) 1, those two are among B_i, C_i, D_i =
    h~_i (x) X_bar/Y_bar/Z_bar, and a product of two of them is a pure
    logical Pauli (the hole operators square away) -- hence commutes with
    every Majorana, which is what makes it a legitimate stabilizer.

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


def _colour_flip(Lx, Ly) -> int:
    """0 or 1 -- which checkerboard class gets the face qubits.

    The paper labels faces even/odd in a checkerboard and puts a qubit on
    every ODD face; which class you call "odd" is a free labelling choice,
    and when the face count nF = (Lx-1)(Ly-1) is odd the two choices are
    genuinely different constructions (Table I's own "majority even faces"
    vs "majority odd faces" columns):

      nF even  -- the classes are the same size; either choice is case I,
                  encoding the full Fock space in m + nF/2 qubits.
      nF odd   -- minority odd (flip 0 here) is case II: m + floor(nF/2)
                  qubits encoding only the EVEN-parity subspace, half of
                  Fock space, which this harness can't represent.
                  Majority odd (flip 1) is case III: m + ceil(nF/2) qubits
                  encoding the full Fock space PLUS one extra logical
                  qubit -- removable with one more stabilizer, see
                  _logical_qubit_stabilizer.

    So flip to majority-odd exactly when nF is odd. The majority class is
    the one containing the corner faces, which are (0,0), (Lx-2,0),
    (0,Ly-2), (Lx-2,Ly-2) -- all of even parity (fx+fy) when both Lx and
    Ly are even, which is precisely when nF is odd.
    """
    return 1 if ((Lx - 1) * (Ly - 1)) % 2 else 0


def _face_is_even(fx, fy, flip=0):
    return (fx + fy + flip) % 2 == 0


def _edge_orientation(v1, v2, flip=0):
    """(v1, v2) an unordered grid-adjacent pair -> (tail, head) per the
    row/column-uniform "comb" pattern derived in this module's docstring.

    The arrows circulate around the EVEN (non-qubit) faces, so the pattern
    is tied to the colouring: flipping which class is "even" (see
    _colour_flip) flips the orientation too. Redoing the derivation with
    the roles swapped, the horizontal rule is unchanged -- both of a
    horizontal edge's candidate faces give the same answer either way, and
    it depends only on the row parity -- while the vertical rule reverses,
    because there the two candidate faces sit in the same face-row and it's
    the column parity that selects between them. Getting this wrong is not
    subtle in its effects: it leaves the lattice corners with mixed
    in/out arrows, and the paper's corner-Majorana injection (which needs
    all arrows at a corner pointing the same way) has nowhere to stand.
    """
    (x1, y1), (x2, y2) = v1, v2
    if y1 == y2:  # horizontal -- unaffected by the colouring flip
        y = y1
        lo, hi = (v1, v2) if x1 < x2 else (v2, v1)
        return (lo, hi) if y % 2 == 0 else (hi, lo)
    else:  # vertical -- reverses with the flip
        x = x1
        lo, hi = (v1, v2) if y1 < y2 else (v2, v1)  # lo = smaller y, hi = larger y
        upward = (x % 2 == 0) != bool(flip)
        return (hi, lo) if upward else (lo, hi)


def _direction_type(tail, head):
    if tail[1] == head[1]:
        return "horizontal"
    return "downward" if head[1] > tail[1] else "upward"


def _odd_face_for_edge(v1, v2, Lx, Ly, flip=0):
    (x1, y1), (x2, y2) = v1, v2
    if y1 == y2:  # horizontal: faces (x,y-1) [above] and (x,y) [below]
        x, y = min(x1, x2), y1
        candidates = [(x, y - 1), (x, y)]
    else:  # vertical: faces (x-1,y) [left] and (x,y) [right]
        x, y = x1, min(y1, y2)
        candidates = [(x - 1, y), (x, y)]
    for fx, fy in candidates:
        if 0 <= fx < Lx - 1 and 0 <= fy < Ly - 1 and not _face_is_even(fx, fy, flip):
            return (fx, fy)
    return None


def _build_geometry(spec):
    Lx, Ly, m = spec["Lx"], spec["Ly"], spec["M"]
    pos_to_mode = {pos: mode for mode, pos in spec["coords"].items()}

    n_faces = len(_faces(Lx, Ly))
    if n_faces == 0:
        raise ValueError(f"DK baseline unavailable at {Lx}x{Ly}: no faces to build stabilizers from")

    flip = _colour_flip(Lx, Ly)
    case_iii = flip == 1  # odd face count -> majority-odd colouring, one extra logical qubit
    odd_faces = [f for f in _faces(Lx, Ly) if not _face_is_even(*f, flip)]

    face_qubit = {f: m + k for k, f in enumerate(odd_faces)}
    n_ancillas = len(odd_faces)
    n_qubits = m + n_ancillas

    def edge_xz(v1, v2):
        tail, head = _edge_orientation(v1, v2, flip)
        dtype = _direction_type(tail, head)
        odd_face = _odd_face_for_edge(v1, v2, Lx, Ly, flip)
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

    def corner_injection(corner):
        """(x, z) for a single Majorana injected at `corner`: X if that
        corner's arrows all point into it, Y if they all point away (the
        paper's own rule). Returns None if the corner doesn't bound an odd
        face -- no qubit there to inject onto.
        """
        cx, cy = corner
        adjacent_face = (min(cx, Lx - 2), min(cy, Ly - 2))
        if _face_is_even(*adjacent_face, flip):
            return None
        incident = [v for v in spec["coords"].values() if _is_grid_neighbor(v, corner)]
        directions = [_edge_orientation(corner, v, flip) for v in incident]
        all_in = all(head == corner for _, head in directions)
        all_out = all(tail == corner for tail, _ in directions)
        if not (all_in or all_out):
            raise ValueError(f"DK baseline: corner {corner} has mixed edge directions -- unexpected, see module docstring")
        x = np.zeros(n_qubits, dtype=np.uint8)
        z = np.zeros(n_qubits, dtype=np.uint8)
        x[pos_to_mode[corner]] = 1
        if all_out:
            z[pos_to_mode[corner]] = 1  # Y rather than X
        return x, z

    def transport(x, z, source, target):
        """XOR in the edge operators along an L-shaped path (across
        `source`'s row, then up `target`'s column) -- the exact operator
        identity gamma_k = i * gamma_j * E_jk applied step by step.
        """
        x, z = x.copy(), z.copy()
        (sx, sy), (tx, ty) = source, target
        for px in range(min(sx, tx), max(sx, tx)):
            ex, ez = edge_cache[frozenset((pos_to_mode[(px, sy)], pos_to_mode[(px + 1, sy)]))]
            x ^= ex; z ^= ez
        for py in range(min(sy, ty), max(sy, ty)):
            ex, ez = edge_cache[frozenset((pos_to_mode[(tx, py)], pos_to_mode[(tx, py + 1)]))]
            x ^= ex; z ^= ez
        return x, z

    all_corners = [(0, 0), (Lx - 1, 0), (0, Ly - 1), (Lx - 1, Ly - 1)]
    injectable = [c for c in all_corners if corner_injection(c) is not None]
    if not injectable:
        raise ValueError(f"DK baseline: no odd-bounding corner found at {Lx}x{Ly} -- unexpected, see module docstring")
    anchor = injectable[0]
    anchor_x, anchor_z = corner_injection(anchor)

    # gamma_j for every vertex j, via an L-shaped path from the anchor.
    gamma_x, gamma_z = {}, {}
    for mode, target in spec["coords"].items():
        gx, gz = transport(anchor_x, anchor_z, anchor, target)
        gamma_x[mode], gamma_z[mode] = gx, gz

    # Case III only: the majority-odd colouring leaves ONE extra logical
    # qubit on top of the full Fock space (Supplementary Material Theorem
    # 3), so the codespace would be 2^(M+1) -- one too large for this
    # harness, which wants exactly the M-mode Fock space. The paper's own
    # remedy: "if one treats one of these operators as a stabilizer, then
    # one restricts to the full fermionic code space without an extra
    # logical qubit". Concretely, with the anchor corner playing the role
    # of A_i = gamma~_i (x) 1, the other three corners give B_i, C_i, D_i =
    # h~_i (x) X_bar / Y_bar / Z_bar, and a product of two of THOSE is a
    # pure logical Pauli (h~_i squares away): C_i D_i = i * 1 (x) X_bar.
    # Being 1 on the fermionic factor, it commutes with every Majorana, so
    # it's a legitimate extra stabilizer -- and it's exactly the
    # corner-to-corner string the paper describes as topologically
    # protecting that logical qubit.
    logical_stabilizer = None
    if case_iii:
        others = [c for c in injectable if c != anchor]
        if len(others) < 2:
            raise ValueError(
                f"DK baseline at {Lx}x{Ly}: case III needs two non-anchor corners bounding odd "
                f"faces to build the logical-qubit stabilizer, found {len(others)}"
            )
        target = anchor  # any common site works; the anchor is as good as any
        parts = [transport(*corner_injection(c), c, target) for c in others[:2]]
        logical_stabilizer = (parts[0][0] ^ parts[1][0], parts[0][1] ^ parts[1][1])

    return {
        "n_qubits": n_qubits, "n_ancillas": n_ancillas,
        "pos_to_mode": pos_to_mode, "face_qubit": face_qubit,
        "edge_cache": edge_cache, "gamma_x": gamma_x, "gamma_z": gamma_z,
        "flip": flip, "logical_stabilizer": logical_stabilizer,
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
    flip = geo["flip"]
    for fx, fy in _faces(Lx, Ly):
        if not _face_is_even(fx, fy, flip):
            continue
        corners = [(fx, fy), (fx + 1, fy), (fx + 1, fy + 1), (fx, fy + 1)]
        sx = np.zeros(n_qubits, dtype=np.uint8)
        sz = np.zeros(n_qubits, dtype=np.uint8)
        for a, b in zip(corners, corners[1:] + corners[:1]):
            ma, mb = geo["pos_to_mode"][a], geo["pos_to_mode"][b]
            ex, ez = geo["edge_cache"][frozenset((ma, mb))]
            sx ^= ex; sz ^= ez
        stabilizers.append(xz_to_string(sx, sz))

    # Case III's extra corner-to-corner string, removing the spare logical
    # qubit -- see _build_geometry for the derivation.
    if geo["logical_stabilizer"] is not None:
        stabilizers.append(xz_to_string(*geo["logical_stabilizer"]))

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
