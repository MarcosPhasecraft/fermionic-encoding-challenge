"""geo_ternary_multitree -- max-Pauli-weight-focused, two tree topologies.

Max-weight local search (`_optimize_order`, unchanged from the registered
baseline geo_ternary_opt) plateaus on any *one* tree: repeated restarts
and 10x the iteration budget move total weight but never move max weight
at all (solution/memory/max_weight_search_topology.md has the measurements).
That's the signature of a structural floor of the specific tree, not a
search-budget problem -- so the fix tried here is a second, differently
*shaped* tree, not a longer search on the same one.

Two topologies, both searched by the identical generic `_optimize_order`
(it only ever looks at a `tree_pairs` list of per-slot (x, z) operators,
never at where they came from):

1. `_tree_mode_pairs` -- the geo_ternary heap-indexed ternary tree (see
   its own docstring below for the construction and correctness argument).
2. `_sierpinski_matrix` -- arXiv 2504.21636's own ternary-tree construction
   (a linear encoding built from a Sierpinski-recursion matrix; same
   reimplementation as baselines/ternary.py, kept self-contained here
   rather than imported, since baselines/ is reference material for
   comparison, not a library this is meant to depend on). Structurally a
   *different* tree (different recursive split, different depth profile)
   from the geo_ternary heap tree, despite both being "ternary trees" in
   the general sense -- which is exactly why it doesn't hit the same
   floor at the same sizes.

`encode` runs the search on both, from the same geometric starting order,
and keeps whichever result has the lower (max_weight, total_weight).
Verified against arXiv 2504.21636's own published (solver-optimized)
Table I max weight, full 3x3-15x15 sweep: matches or beats it at *every*
size, with zero losses -- the geo_ternary-alone version
(baselines/geo_ternary_opt.py) tied at 8 of 13 sizes and *lost* at 4x4
(6 vs published 5); the Sierpinski tree wins there specifically (5,
matching published exactly), while the geo_ternary tree keeps its own
wins elsewhere (5x5, 7x7, 12x12, 15x15). Neither topology dominates the
other size-by-size, which is exactly why running both and keeping the
better result -- rather than picking one -- is the actual fix. Full
numbers, and why naive simulated annealing (which worked for total
weight) actively made max weight *worse* here, are in
solution/memory/max_weight_search_topology.md.
"""

import math

import numpy as np

from harness.constructors import from_linear_encoding, transitive_closure
from harness.lattice import hamiltonian
from harness.paulis import string_to_xz, xz_to_string

_LABELS = "XYZ"  # child offset 0, 1, 2 (i.e. (node-1) % 3) -> edge label


def _leaf_xz(leaf, m):
    """(x, z) bit vectors, length m, for a single tree leaf: walk leaf ->
    root, and at each ancestor router qubit set the label of the edge taken
    toward the next node on the path.
    """
    x = np.zeros(m, dtype=np.uint8)
    z = np.zeros(m, dtype=np.uint8)
    node = leaf
    while node != 0:
        parent = (node - 1) // 3
        label = _LABELS[(node - 1) % 3]
        if label in ("X", "Y"):
            x[parent] = 1
        if label in ("Y", "Z"):
            z[parent] = 1
        node = parent
    return x, z


def _tree_mode_pairs(m):
    """m tree "slots", each a pair of (x, z) bit vectors -- the two
    Majorana operators for that slot, drawn from consecutive leaves of a
    perfect ternary tree's 2m (of 2m+1) used leaves.

    Ancilla-free (N = M): M "router" qubits, one per internal node of a
    perfect ternary tree built in breadth-first (heap) order -- node k's
    three children sit at indices 3k+1, 3k+2, 3k+3, labelled X, Y, Z
    respectively. A tree with M internal nodes has exactly 2M+1 leaf
    slots; 2M of them become the Majorana operators (one is left unused,
    the deepest one -- consecutive pairs starting at leaf index m). A
    leaf's Pauli string is built by walking from the leaf to the root:
    every ancestor router qubit contributes the X/Y/Z label of the edge
    taken toward the next node on the path, and weight = leaf depth. This
    is Jordan-Wigner's linear Z-chain generalised to branching factor 3
    (JW is the degenerate case where every router only ever uses one of
    its three children), so weight grows like log_3(M) instead of M.

    Correctness sketch: take two distinct leaves. Their root-to-leaf paths
    agree down to their deepest common ancestor A, then diverge into two
    different, and therefore node-disjoint, subtrees of A.
      - Above A: both operators carry the same label at each shared
        ancestor qubit, which never contributes to the symplectic pairing
        (a Pauli always "commutes" with itself qubit-by-qubit).
      - At A: the two paths leave via two different children of A, so
        they carry two distinct labels drawn from {X, Y, Z} -- any two
        distinct single-qubit Paulis among X, Y, Z anticommute,
        contributing 1.
      - Below A: the two operators act on disjoint qubit sets (disjoint
        subtrees), contributing 0.
      Total parity is always odd, so every pair of leaves anticommutes,
      independent of M or tree shape.

    A leaf's parent contributes 1, 2, or 3 leaves (only the bottom tier of
    routers contributes 3; higher routers contribute 0), so consecutive
    leaves aren't always siblings, and a pair straddling two different
    parents has weight > 1. That looks fixable by pairing within each
    parent first and only matching leftovers across parents -- tried,
    including recursive escalation of an unmatched leftover to its
    parent's own parent. Neither changed the *multiset* of pair weights
    at all (verified by direct comparison, M=169): it's a structural
    invariant of the tree's shape at a given m, fixed regardless of which
    valid pairing strategy assigns it to which specific leaves, and the
    fancier strategies broke the leaf-index locality the spatial ordering
    below relies on. Flat consecutive pairing came out ahead in practice
    for that reason, so it's what's kept.
    """
    if m == 0:
        return []
    return [(_leaf_xz(a, m), _leaf_xz(a + 1, m)) for a in range(m, 3 * m, 2)]


def _spatial_order(spec):
    """Permutation of spec's mode indices: order[k] is the mode assigned to
    tree leaf-pair k. Recursively splits the lattice into three roughly
    equal groups along its longer axis, mirroring a ternary tree's own
    branching, so physically adjacent sites tend to share long common tree
    ancestries -- shared as the starting point for both topologies'
    search below, not just geo_ternary's own tree.

    Group sizes are spread as evenly as possible (any leftover from n not
    dividing by 3 goes to the first groups, not dumped entirely into the
    last one) -- dumping the remainder at the end compounds over recursion
    levels into a systematically lopsided partition at sizes that don't
    divide cleanly by 3.
    """
    coords = spec["coords"]
    sites = sorted(coords.keys())

    def recurse(indices):
        if len(indices) <= 1:
            return list(indices)
        xs = [coords[i][0] for i in indices]
        ys = [coords[i][1] for i in indices]
        axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
        indices = sorted(indices, key=lambda i: coords[i][axis])
        n = len(indices)
        base, rem = divmod(n, 3)
        sizes = [base + (1 if i < rem else 0) for i in range(3)]
        groups, start = [], 0
        for size in sizes:
            if size:
                groups.append(indices[start:start + size])
            start += size
        result = []
        for g in groups:
            result += recurse(g)
        return result

    return recurse(sites)


def _sierpinski_edges(u, c, r):
    """Recursive Sierpinski-tree edge construction, arXiv 2504.21636's own
    ternary tree (reimplemented in plain numpy; see module docstring for
    why this is a self-contained copy rather than importing
    baselines/ternary.py). Pads to the next power of 3, recursively
    connects the middle third's midpoint to the midpoints of the other two
    thirds, preserving the reference's float-arithmetic midpoints (the
    range doesn't always split evenly into thirds).
    """
    if c == r:
        return

    def mid(a, b):
        return int((a + b) // 2)

    third = (r - c + 1) / 3
    l = c + third
    rr = c + 2 * third
    if mid(l, rr - 1) < u.shape[0] and mid(c, l - 1) < u.shape[1]:
        u[mid(l, rr - 1), mid(c, l - 1)] = 1
    if mid(l, rr - 1) < u.shape[0] and mid(rr, r) < u.shape[1]:
        u[mid(l, rr - 1), mid(rr, r)] = 1
    _sierpinski_edges(u, c, l - 1)
    _sierpinski_edges(u, l, rr - 1)
    _sierpinski_edges(u, rr, r)


def _sierpinski_matrix(n):
    padded = 3 ** math.ceil(math.log(n, 3)) if n > 1 else 1
    u = np.zeros((n, n), dtype=np.uint8)
    _sierpinski_edges(u, 0, padded - 1)
    u = transitive_closure(u)
    return (u + np.eye(n, dtype=np.uint8)) % 2


def _matrix_tree_pairs(matrix):
    """A linear-encoding matrix -> the same tree_pairs shape
    `_tree_mode_pairs` produces (a list of per-slot ((x, z), (x, z)) pairs),
    so `_optimize_order` can search over it identically -- it never looks
    at where a tree_pairs list came from, only at the (x, z) content.
    """
    n = matrix.shape[0]
    mapping = from_linear_encoding(matrix)
    pairs = []
    for i in range(n):
        pairs.append((string_to_xz(mapping["majoranas"][2 * i]), string_to_xz(mapping["majoranas"][2 * i + 1])))
    return pairs


def _pack(x, z):
    """(x, z) numpy bit vectors -> a pair of Python ints (bitmasks). XOR and
    popcount on plain ints (via int.bit_count()) are far cheaper than numpy
    array ops at the sizes _optimize_order calls this for -- thousands of
    small, single-term recomputations per search, not one bulk computation.
    """
    xi = zi = 0
    for i, (xb, zb) in enumerate(zip(x, z)):
        if xb:
            xi |= 1 << i
        if zb:
            zi |= 1 << i
    return xi, zi


_MAX_TRACKED_WEIGHT = 64  # weight cannot exceed n_qubits <= a few hundred at
                          # any size this harness's leaderboard covers, and in
                          # practice never gets close to this.


def _optimize_order(spec, tree_pairs, order, seed):
    """Local search over which spec mode gets which tree slot, hill-climbing
    on (max_weight, total_weight) lexicographically. Every candidate here is
    already a valid encoding -- relabelling which mode owns which of the 2M
    operators can't break the Majorana algebra, which is a property of the
    operator *set*, not of the labelling -- so this can only improve score,
    never validity.

    Algorithm: repeatedly take a mode `a` implicated in a current
    worst-weight term, try swapping its tree slot with every other mode
    `b` (a random sample of 80 when there are more candidates than that),
    and commit whichever swap most improves (max, total); if none improves,
    make a random swap anyway (seeded, so still deterministic) to escape a
    local optimum, tracking the best (order, max, total) seen so far to
    return even if later exploration wanders away from it.

    This is the max-weight-focused search from the registered baseline
    geo_ternary_opt (previously the only tree it ran on); unchanged here.
    Simulated annealing -- the lever that worked for *total* weight
    (accepting temporarily worse moves to escape a bad basin) -- was tried
    on this objective too and made things worse at every size tested, not
    better: max is a min-max objective this greedy search already explores
    exhaustively at each step (every candidate swap, every iteration), so
    there's no "stuck in a bad basin" problem annealing's randomness fixes
    -- it just adds noise. Likewise, more restarts and 10x the iteration
    budget move total weight (a few percent) but never move max weight at
    all, at every size tested -- the plateau is the *tree's* structural
    floor, not a search-budget problem, which is why `encode` runs this
    same search on a second, differently-shaped tree instead of running it
    longer on one. Full comparison in
    solution/memory/max_weight_search_topology.md.

    Bookkeeping for speed: each term's current weight is cached, and a
    swap only needs to recompute the (few) terms touching modes `a` or `b`,
    not the full term list; a fixed-size histogram of weight -> count of
    terms at that weight (bounded by _MAX_TRACKED_WEIGHT, comfortably above
    anything reachable here) gives the new max after a candidate swap in
    O(_MAX_TRACKED_WEIGHT) rather than O(number of terms).

    Iteration budget scales with m (20*m, floor 200) rather than being
    fixed, so it stays a size-driven formula, not a lookup keyed to specific
    Lx/Ly values (CLAUDE.md's "one uniform rule" requirement).
    """
    m = spec["M"]
    if m < 2:
        return order, 0, 0

    terms = hamiltonian(spec, model="full")
    slot_ops = [(_pack(*a), _pack(*b)) for a, b in tree_pairs]  # slot -> ((x,z)_gamma, (x,z)_gammabar), packed
    pos = [0] * m
    for k, mode in enumerate(order):
        pos[mode] = k

    def term_weight(term):
        x = z = 0
        for idx in term:
            xi, zi = slot_ops[pos[idx >> 1]][idx & 1]
            x ^= xi
            z ^= zi
        return (x | z).bit_count()

    weights = [term_weight(t) for t in terms]
    counts = [0] * _MAX_TRACKED_WEIGHT
    for w in weights:
        counts[w] += 1
    cur_max = max(w for w in range(_MAX_TRACKED_WEIGHT) if counts[w])
    cur_total = sum(weights)

    involves = [[] for _ in range(m)]
    for ti, term in enumerate(terms):
        for mode in {idx >> 1 for idx in term}:
            involves[mode].append(ti)

    best_pos, best_max, best_total = list(pos), cur_max, cur_total

    rng = np.random.default_rng(seed)
    max_iters = max(200, 20 * m)
    stall_limit = max(150, 3 * m)
    stall = 0
    for _ in range(max_iters):
        if stall >= stall_limit:
            break
        worst = [ti for ti, w in enumerate(weights) if w == cur_max]
        a = int(rng.choice(sorted({idx >> 1 for idx in terms[worst[int(rng.integers(len(worst)))]]})))

        candidates = range(m) if m <= 80 else rng.choice(m, size=80, replace=False)
        best_choice, best_key = None, (cur_max, cur_total)
        for b in candidates:
            b = int(b)
            if b == a:
                continue
            affected = list(set(involves[a]) | set(involves[b]))
            pos[a], pos[b] = pos[b], pos[a]
            new_weights, delta = {}, {}
            for ti in affected:
                w_old, w_new = weights[ti], term_weight(terms[ti])
                new_weights[ti] = w_new
                delta[w_old] = delta.get(w_old, 0) - 1
                delta[w_new] = delta.get(w_new, 0) + 1
            pos[a], pos[b] = pos[b], pos[a]

            tentative_max = max(w for w in range(_MAX_TRACKED_WEIGHT) if counts[w] + delta.get(w, 0) > 0)
            tentative_total = cur_total + sum(w * d for w, d in delta.items())
            key = (tentative_max, tentative_total)
            if key < best_key:
                best_key, best_choice = key, (b, new_weights, delta, tentative_max, tentative_total)

        if best_choice is None:
            stall += 1
            b = int(rng.integers(m))
            if b == a:
                continue
            affected = list(set(involves[a]) | set(involves[b]))
            pos[a], pos[b] = pos[b], pos[a]
            for ti in affected:
                w_old, w_new = weights[ti], term_weight(terms[ti])
                counts[w_old] -= 1
                counts[w_new] += 1
                cur_total += w_new - w_old
                weights[ti] = w_new
            cur_max = max(w for w in range(_MAX_TRACKED_WEIGHT) if counts[w])
            continue

        stall = 0
        b, new_weights, delta, cur_max, cur_total = best_choice
        pos[a], pos[b] = pos[b], pos[a]
        for ti, w in new_weights.items():
            weights[ti] = w
        for w, d in delta.items():
            counts[w] += d
        if (cur_max, cur_total) < (best_max, best_total):
            best_max, best_total, best_pos = cur_max, cur_total, list(pos)

    new_order = [None] * m
    for mode, k in enumerate(best_pos):
        new_order[k] = mode
    return new_order, best_max, best_total


def _emit(tree_pairs, order, m):
    majoranas = [None] * (2 * m)
    for k, mode in enumerate(order):
        (xa, za), (xb, zb) = tree_pairs[k]
        majoranas[2 * mode] = xz_to_string(xa, za)
        majoranas[2 * mode + 1] = xz_to_string(xb, zb)
    return {"n_qubits": m, "majoranas": majoranas, "stabilizers": []}


def encode(spec):
    m = spec["M"]
    start_order = _spatial_order(spec)

    geo_pairs = _tree_mode_pairs(m)
    geo_order, geo_max, geo_total = _optimize_order(spec, geo_pairs, start_order, seed=m)

    sierpinski_pairs = _matrix_tree_pairs(_sierpinski_matrix(m))
    sierpinski_order, sierpinski_max, sierpinski_total = _optimize_order(spec, sierpinski_pairs, start_order, seed=m)

    if (geo_max, geo_total) <= (sierpinski_max, sierpinski_total):
        return _emit(geo_pairs, geo_order, m)
    return _emit(sierpinski_pairs, sierpinski_order, m)
