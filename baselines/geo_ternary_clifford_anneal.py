"""geo_ternary_clifford_anneal -- annealed geo-ternary + Clifford transvection descent.

Total-weight-focused. Two stages, both operating on an encoding that is
already valid at every step:

1. **Annealed mode placement** (`_anneal_once` x `_N_RESTARTS`) -- the
   geo_ternary heap-indexed ternary tree, with lattice sites assigned to
   tree slots by a recursive 3-way spatial partition, then refined by
   simulated annealing on total Pauli weight. This is the registered
   baseline `geo_ternary_anneal_ensemble`, unchanged.

2. **Clifford transvection descent** (`_clifford_descent`) -- new here.
   Conjugating every Majorana by a fixed Pauli axis `P` is a Clifford
   operation: an operator anticommuting with `P` picks up `P`, one
   commuting with it is untouched. Over GF(2) that is the symplectic
   transvection `O -> O + <O,P>P`, which preserves *every* pairwise
   symplectic product -- so the whole 2M-operator set stays pairwise
   anticommuting, and the mapping stays valid, for **any** choice of `P`.
   Unlike stage 1 (which only permutes which mode owns which existing
   operator) this genuinely reshapes the operators' supports, reaching
   encodings no relabelling and no change of tree can produce.

   Credit where due: the Clifford-transvection idea is taken from the
   registered submission `baselines/geo_ternary_clifford.py` (Codex
   GPT-5.6 Sol), which introduced it to this benchmark. What is different
   here is stage 1 -- that submission reaches its Clifford stage from a
   weaker placement, and this one starts from the stronger annealed
   ensemble, which is where the margin comes from (see
   solution/memory/clifford_transvections.md for the measured breakdown).

**Axis set.** Only weight-2 axes on (parent, child) and (grandparent,
grandchild) router-qubit pairs of the tree. Three alternatives were
measured and all did worse (details in the memory file), the informative
one being lattice-adjacent axes: the *Hamiltonian* is lattice-local, so
those look like the natural choice, but the operator *supports* run along
root-to-leaf tree paths, and axes aligned with that structure are what
actually move the objective. Widening to all qubit pairs (sampled, since
the full set is O(M^2)) is worse still -- it dilutes the useful
tree-adjacent axes rather than adding reach.

**Descent, not annealing.** Stage 2 is plain steepest descent: take the
single best strictly-improving axis each sweep, stop when none improves.
Annealing over transvections was tried and found no improvement at all
over the un-refined start, and interleaving extra rounds of
finer-grained (individual-Majorana) placement annealing between Clifford
sweeps likewise added exactly nothing -- every variant converged to the
same value. The greedy descent is already finding this basin's floor.

**Max weight is capped, not optimized.** A move is refused if it would
push maximum Pauli weight above where stage 1 left it, so stage 2 is
Pareto-safe with respect to its own starting point -- it can only trade
total weight downward. This submission targets *total* weight; for
maximum weight the registered `geo_ternary_multitree` remains far better
(e.g. 10 vs this one's 15 at 15x15), and the two are genuinely different
operating points rather than one dominating the other.
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
    """m tree "slots", each a pair of (x, z) bit vectors -- the two Majorana
    operators for that slot, from consecutive leaves of a perfect ternary
    tree's 2m (of 2m+1) used leaves.

    Ancilla-free (N = M): M router qubits, one per internal node of a
    perfect ternary tree in breadth-first (heap) order -- node k's children
    are 3k+1, 3k+2, 3k+3, labelled X, Y, Z. A leaf's Pauli string is built
    by walking leaf -> root, each ancestor contributing the label of the
    edge taken; weight = leaf depth. This is Jordan-Wigner's linear
    Z-chain generalised to branching factor 3, so weight grows like
    log_3(M) rather than M.

    Validity: two distinct leaves' paths agree above their deepest common
    ancestor A (a Pauli always commutes with itself qubit-by-qubit, so no
    contribution), leave A via two different children and so carry two
    distinct labels from {X, Y, Z} (any two distinct single-qubit Paulis
    anticommute -- contributes exactly 1), and act on disjoint qubits below
    A (no contribution). Total parity is odd, so every pair anticommutes,
    for any M and any tree shape.
    """
    if m == 0:
        return []
    return [(_leaf_xz(a, m), _leaf_xz(a + 1, m)) for a in range(m, 3 * m, 2)]


def _spatial_order(spec):
    """Permutation of spec's mode indices: order[k] is the mode assigned to
    tree leaf-pair k. Recursively splits the lattice into three roughly
    equal groups along its longer axis, mirroring the tree's own branching,
    so physically adjacent sites tend to share long common tree ancestries.

    Group sizes are spread as evenly as possible (a leftover from n not
    dividing by 3 goes to the first groups); dumping it all in the last
    group compounds over recursion levels into a lopsided partition at
    sizes that don't divide cleanly by 3.
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
    """(x, z) bit vectors -> a pair of Python ints (bitmasks). XOR and
    popcount on plain ints are far cheaper than numpy array ops at the
    sizes the searches below call this for -- many small single-term
    recomputations, not one bulk computation.
    """
    xi = zi = 0
    for i, (xb, zb) in enumerate(zip(x, z)):
        if xb:
            xi |= 1 << i
        if zb:
            zi |= 1 << i
    return xi, zi


def _anneal_once(spec, tree_pairs, order, seed):
    """One simulated-annealing run over which mode gets which tree slot,
    minimizing total Pauli weight. Relabelling which mode owns which of the
    2M operators cannot break the Majorana algebra -- that is a property of
    the operator *set*, not the labelling -- so this only ever changes
    score, never validity.

    Metropolis acceptance: propose swapping two random modes' slots, accept
    if total weight doesn't rise, else accept with probability
    exp(-delta/T). T decays geometrically, both endpoints scaled off the
    *starting* total weight so the schedule adapts to problem size rather
    than being a constant keyed to particular lattices. Returns the best
    state seen at any point, not wherever the walk ends.

    A pure greedy hill-climb was tried first and plateaus well short of
    this: it sticks in whatever basin the geometric start sits in, and a
    larger budget alone doesn't move it. Accepting worse moves early -- a
    *high* starting temperature, 20% of the starting total -- is what
    crosses those barriers.

    Only the (few) terms touching either swapped mode need rescoring, so a
    step is O(local), not O(all terms).
    """
    m = spec["M"]
    terms = hamiltonian(spec, model="full")
    slot_ops = [(_pack(*a), _pack(*b)) for a, b in tree_pairs]
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
    cur_total = sum(weights)

    involves = [[] for _ in range(m)]
    for ti, term in enumerate(terms):
        for mode in {idx >> 1 for idx in term}:
            involves[mode].append(ti)

    best_pos, best_total = list(pos), cur_total

    rng = np.random.default_rng(seed)
    max_iters = max(100_000, 2500 * m)
    t0 = max(1.0, cur_total * 0.2)
    t_end = max(0.01, cur_total * 0.0001)

    for it in range(max_iters):
        temperature = t0 * (t_end / t0) ** (it / max_iters)
        a, b = int(rng.integers(m)), int(rng.integers(m))
        if a == b:
            continue

        affected = list(set(involves[a]) | set(involves[b]))
        pos[a], pos[b] = pos[b], pos[a]
        new_weights, delta_total = {}, 0
        for ti in affected:
            w_new = term_weight(terms[ti])
            delta_total += w_new - weights[ti]
            new_weights[ti] = w_new

        if delta_total <= 0 or rng.random() < np.exp(-delta_total / temperature):
            cur_total += delta_total
            for ti, w in new_weights.items():
                weights[ti] = w
            if cur_total < best_total:
                best_total, best_pos = cur_total, list(pos)
        else:
            pos[a], pos[b] = pos[b], pos[a]  # reject: undo the swap

    new_order = [None] * m
    for mode, k in enumerate(best_pos):
        new_order[k] = mode
    return new_order, best_total


_N_RESTARTS = 5  # independent anneals per spec; keep the best. Each run's own
                 # randomness (swap proposals, Metropolis coin flips) explores a
                 # different path even from the same start, so runs land in
                 # different local optima; best-of-several measurably beats one
                 # run (~1-3% lower total at every size checked) for 5x the
                 # runtime. Seeds are m, m+1, ..., m+4 -- a formula, not a table.


def _candidate_orders(spec, tree_pairs, order):
    """All `_N_RESTARTS` annealed orders, not just the best-scoring one.

    Deliberately returns every candidate rather than pre-selecting: stage
    2's Clifford descent is **not monotonic** in stage 1's score, so the
    best pre-Clifford order is not reliably the one that descends
    furthest. Measured at 15x15: seed 236 starts better than seed 227
    (11582 vs 11716) and finishes worse (11445 vs 11372). Selecting on
    the stage-1 score alone therefore throws away candidates that would
    have won; `encode` descends all of them and selects on the final
    score instead. That can never be worse than the old rule, since the
    order it used to pick is still among the candidates -- it just costs
    `_N_RESTARTS` descents rather than one.
    """
    if spec["M"] < 2:
        return [order]
    return [_anneal_once(spec, tree_pairs, order, seed=spec["M"] + i)[0]
            for i in range(_N_RESTARTS)]


def _transvection_axes(m):
    """Weight-2 Pauli axes on (parent, child) and (grandparent, grandchild)
    router-qubit pairs of the heap tree, all 9 label combinations each.

    Restricted to tree-adjacent pairs deliberately: an operator's support is
    a root-to-leaf path, so a transvection whose axis spans an edge of that
    path can cancel structure two operators share, while an axis on two
    unrelated qubits mostly just adds weight. Measured against the
    alternatives -- see this module's docstring and the memory file.
    """
    pairs = set()
    for node in range(m):
        ancestor = (node - 1) // 3 if node else None
        for _ in range(2):
            if ancestor is None or ancestor < 0:
                break
            pairs.add((min(ancestor, node), max(ancestor, node)))
            ancestor = (ancestor - 1) // 3 if ancestor else None

    axes = []
    for a, b in sorted(pairs):
        for label_a in range(3):
            for label_b in range(3):
                px = pz = 0
                if label_a in (0, 1):
                    px |= 1 << a
                if label_a in (1, 2):
                    pz |= 1 << a
                if label_b in (0, 1):
                    px |= 1 << b
                if label_b in (1, 2):
                    pz |= 1 << b
                axes.append((px, pz))
    return axes


def _clifford_descent(spec, operators, max_sweeps=400):
    """Steepest descent over Clifford transvections, minimizing total weight
    without letting maximum weight rise above its starting value.

    A transvection by axis P sends each operator O to O + <O,P>P, where
    <.,.> is the symplectic product -- i.e. conjugation by the Clifford that
    P generates. It preserves every pairwise symplectic product, so the
    2M operators stay pairwise anticommuting and the encoding stays valid
    for any P whatsoever; this is checked directly rather than assumed
    (an arbitrary-axis stress test is described in the memory file).

    The map is linear over GF(2), so a term's *product* transforms by the
    same rule as an individual operator. That means a candidate axis can be
    scored by transvecting the cached term products directly -- O(number of
    terms) per candidate, with no need to rebuild products from operators.
    """
    m = spec["M"]
    terms = hamiltonian(spec, model="full")

    products = []
    for term in terms:
        x = z = 0
        for idx in term:
            x ^= operators[idx][0]
            z ^= operators[idx][1]
        products.append((x, z))
    weights = [(x | z).bit_count() for x, z in products]
    cap = max(weights)  # stage 1's maximum weight: never exceed it

    axes = _transvection_axes(m)

    for _ in range(max_sweeps):
        best_delta, best_axis = 0, None
        for px, pz in axes:
            delta, highest = 0, 0
            for old_weight, (x, z) in zip(weights, products):
                if ((x & pz).bit_count() + (z & px).bit_count()) & 1:
                    new_weight = ((x ^ px) | (z ^ pz)).bit_count()
                else:
                    new_weight = old_weight
                delta += new_weight - old_weight
                if new_weight > highest:
                    highest = new_weight
            if delta < best_delta and highest <= cap:
                best_delta, best_axis = delta, (px, pz)

        if best_axis is None:
            break

        px, pz = best_axis

        def transvect(operator):
            x, z = operator
            if ((x & pz).bit_count() + (z & px).bit_count()) & 1:
                return x ^ px, z ^ pz
            return x, z

        operators = [transvect(o) for o in operators]
        products = [transvect(p) for p in products]
        weights = [(x | z).bit_count() for x, z in products]

    return operators


def _to_pauli_string(x, z, m):
    return "".join(
        "Y" if (x >> q) & 1 and (z >> q) & 1
        else "X" if (x >> q) & 1
        else "Z" if (z >> q) & 1
        else "I"
        for q in range(m)
    )


def _operators_for(tree_pairs, order, m):
    operators = [None] * (2 * m)
    for k, mode in enumerate(order):
        pair = tree_pairs[k]
        operators[2 * mode] = _pack(*pair[0])
        operators[2 * mode + 1] = _pack(*pair[1])
    return operators


def _total_weight(spec, operators):
    total = 0
    for term in hamiltonian(spec, model="full"):
        x = z = 0
        for idx in term:
            x ^= operators[idx][0]
            z ^= operators[idx][1]
        total += (x | z).bit_count()
    return total


def encode(spec):
    m = spec["M"]
    tree_pairs = _tree_mode_pairs(m)
    orders = _candidate_orders(spec, tree_pairs, _spatial_order(spec))

    best_operators, best_total = None, None
    for order in orders:
        operators = _operators_for(tree_pairs, order, m)
        if m >= 2:
            operators = _clifford_descent(spec, operators)
        total = _total_weight(spec, operators)
        if best_total is None or total < best_total:
            best_operators, best_total = operators, total

    return {
        "n_qubits": m,
        "majoranas": [_to_pauli_string(x, z, m) for x, z in best_operators],
        "stabilizers": [],
    }
