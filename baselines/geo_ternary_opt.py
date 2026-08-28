"""geo_ternary -- a from-scratch ternary-tree fermion-to-qubit encoding.

Built directly (leaf-to-root walks over a heap-indexed tree), not via
harness.constructors.from_linear_encoding and not sharing any code with
baselines/ternary.py's Sierpinski-matrix construction -- an independent
implementation of the same underlying idea (arXiv 2504.21636's ternary
tree), distinguished here as "geo_ternary" because its distinguishing
piece is the mode ordering: it uses spec["coords"] directly to place
physically nearby lattice sites under nearby tree ancestors, rather than
choosing among the harness's fixed row_major/snake/diagonal orderings.

Verified against every registered baseline (jw, parity, bk, ternary, and
their _snake variants) across the full 3x3-15x15 sweep: total Pauli weight
beats bk almost everywhere and beats the official ternary at a few sizes
(11x11, 15x15); max Pauli weight ties or beats *every* registered
encoding, including both ternary variants and bk, from 9x9 through 15x15.

Ancilla-free (N = M): M "router" qubits, one per internal node of a perfect
ternary tree built in breadth-first (heap) order -- node k's three children
sit at indices 3k+1, 3k+2, 3k+3, labelled X, Y, Z respectively. A tree with
M internal nodes has exactly 2M+1 leaf slots; 2M of them become the
Majorana operators (one is left unused). A leaf's Pauli string is built by
walking from the leaf to the root: every ancestor router qubit contributes
the X/Y/Z label of the edge taken toward the next node on the path, and
weight = leaf depth.

This is Jordan-Wigner's linear Z-chain generalised to branching factor 3
(JW is the degenerate case where every router only ever uses one of its
three children) so weight grows like log_3(M) instead of M.

Correctness sketch: take two distinct leaves. Their root-to-leaf paths
agree down to their deepest common ancestor A, then diverge into two
different, and therefore node-disjoint, subtrees of A.
  - Above A: both operators carry the same label at each shared ancestor
    qubit, which never contributes to the symplectic pairing (a Pauli
    always "commutes" with itself qubit-by-qubit).
  - At A: the two paths leave via two different children of A, so they
    carry two distinct labels drawn from {X, Y, Z} -- any two distinct
    single-qubit Paulis among X, Y, Z anticommute, contributing 1.
  - Below A: the two operators act on disjoint qubit sets (disjoint
    subtrees), contributing 0.
  Total parity is always odd, so every pair of leaves anticommutes,
  independent of M or tree shape.

Mode ordering: spec's mode indices are assigned to tree leaf-pairs via a
recursive 3-way spatial partition of the lattice (split the longer axis
into three, recurse) so that lattice-adjacent sites tend to land under
nearby tree ancestors, the same mechanism that makes Jordan-Wigner cheap
for adjacent-index hopping. That geometric assignment is then refined by
a bounded local search (`_optimize_order`) targeting max Pauli weight
specifically, since which of the 2M already-valid operators gets called
"mode j" never affects validity (anticommutation is a property of the
operator *set*, untouched by relabelling which physical site owns which
pair) -- so the search is free to hill-climb purely on score, with zero
risk of producing an invalid mapping. This closed most of the remaining
gap to arXiv 2504.21636's own solver-optimized Table I max-weight numbers:
ties or beats them at every size checked, 8x8 through 15x15, and beats
them outright at 12x12 and 15x15 (see solution/memory/max_weight_search.md).
"""

import numpy as np

from harness.lattice import hamiltonian
from harness.paulis import xz_to_string

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

    A leaf's parent contributes 1, 2, or 3 leaves (only the bottom tier of
    routers contributes 3; higher routers contribute 0), so consecutive
    leaves aren't always siblings, and a pair straddling two different
    parents has weight > 1 (its two operators then only share ancestry
    above their more distant common ancestor). That looks fixable by
    pairing within each parent first and only matching leftovers
    (a 3-leaf parent's odd-one-out) across parents -- tried, including a
    version that escalates an unmatched leftover to its parent's own
    parent and repeats, recursively, to always match it at the closest
    available level. Neither changed the *multiset* of pair weights at
    all (verified by direct comparison, M=169): it's a structural
    invariant of the tree's shape at a given m, fixed regardless of which
    valid pairing strategy assigns it to which specific leaves. What the
    fancier strategies did change is *which* leaf ends up in which pair,
    which broke consecutive-slot-index proximity in leaf-index space --
    and that proximity is exactly what `_spatial_order` relies on to keep
    physically adjacent sites tree-close. Flat consecutive pairing came
    out ahead in practice (full sweep, 3x3-15x15) for that reason, so it's
    what's kept, despite occasionally pairing non-siblings.
    """
    if m == 0:
        return []
    return [(_leaf_xz(a, m), _leaf_xz(a + 1, m)) for a in range(m, 3 * m, 2)]


def _spatial_order(spec):
    """Permutation of spec's mode indices: order[k] is the mode assigned to
    tree leaf-pair k. Recursively splits the lattice into three roughly
    equal groups along its longer axis, mirroring the tree's own branching,
    so physically adjacent sites tend to share long common tree ancestries.

    Group sizes are spread as evenly as possible (any leftover from n not
    dividing by 3 goes to the first groups, not dumped entirely into the
    last one) -- tried both, and dumping the remainder at the end
    compounds over recursion levels into a systematically lopsided
    partition at sizes that don't divide cleanly by 3, which was the
    direct cause of a real anomaly (13x13's max weight jumping to 13,
    against 10 and 12 at the neighbouring 12x12/14x14). Spreading it
    evenly improved both total and max weight in aggregate over the full
    3x3-15x15 sweep, not just at 13x13.
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
                          # practice never gets close to this; see the module
                          # docstring for what a hit here would mean (it can't,
                          # short of a lattice far outside the covered range).


def _optimize_order(spec, tree_pairs, order):
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

    Bookkeeping for speed: each term's current weight is cached, and a
    swap only needs to recompute the (few) terms touching modes `a` or `b`,
    not the full term list; a fixed-size histogram of weight -> count of
    terms at that weight (bounded by _MAX_TRACKED_WEIGHT, comfortably above
    anything reachable here) gives the new max after a candidate swap in
    O(_MAX_TRACKED_WEIGHT) rather than O(number of terms).

    Iteration budget scales with m (20*m, floor 200) rather than being
    fixed, so it stays a size-driven formula, not a lookup keyed to specific
    Lx/Ly values (CLAUDE.md's "one uniform rule" requirement) -- verified
    empirically (solution/memory/max_weight_search.md) that this budget
    already captures nearly all of the achievable improvement: tripling it
    at 12x12/13x13/15x15 moved total weight by well under 1%, and max
    weight not at all.
    """
    m = spec["M"]
    if m < 2:
        return order

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

    rng = np.random.default_rng(m)  # seeded by m alone: deterministic, no lattice-shape-keyed table
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
    return new_order


def encode(spec):
    m = spec["M"]
    tree_pairs = _tree_mode_pairs(m)
    order = _optimize_order(spec, tree_pairs, _spatial_order(spec))

    majoranas = [None] * (2 * m)
    for k, mode in enumerate(order):
        (xa, za), (xb, zb) = tree_pairs[k]
        majoranas[2 * mode] = xz_to_string(xa, za)
        majoranas[2 * mode + 1] = xz_to_string(xb, zb)

    return {"n_qubits": m, "majoranas": majoranas, "stabilizers": []}
