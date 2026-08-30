"""geo_ternary_deep_refine -- annealed geo-ternary placement + a deep Clifford refiner.

Total-weight-focused, ancilla-free (N = M), one uniform rule at every size.

The pipeline is four stages, every one of which operates on an encoding that
is already valid (pairwise-anticommuting) at every intermediate step:

1. **Placement.** A ternary tree (two topologies: the breadth-first heap and
   a recursively balanced tree), lattice sites assigned to tree slots by a
   recursive 3-way spatial partition, then refined by simulated annealing --
   first over mode-pair placement, then over individual Majorana placement.
   This is the registered `geo_ternary_anneal_ensemble` search widened by the
   second, finer anneal.

2. **Greedy tree-axis Clifford descent.** Weight-2 transvections on
   (parent, child) and (grandparent, grandchild) router pairs.

3. **Deep refinement**, iterated to a fixed point -- the part that is new:
   a size-scaled transvection anneal, an *exhaustive* two-qubit Clifford
   descent, and a descent over data-driven axes (below).

4. **Postselection on the final score**, never on an intermediate one.

**Why transvections are safe.** Conjugating every Majorana by a fixed Pauli
axis `P` sends `O -> O + <O,P>P`. Over GF(2) that is the symplectic
transvection, which preserves *every* pairwise symplectic product -- so the
whole 2M-operator set stays pairwise anticommuting and the encoding stays
valid for **any** `P` whatsoever, not just carefully chosen ones. The same
holds for any element of `Sp(4, 2)` applied to a two-qubit block and the
identity elsewhere: it is symplectic on that block, and the total symplectic
form is a sum over qubits.

Credit: the Clifford-transvection idea entered this benchmark via
`baselines/geo_ternary_clifford.py` (Codex GPT-5.6 Sol), and the
two-qubit `Sp(4, 2)` block parameterisation and the individual-Majorana
placement anneal via `baselines/ternary_multistage_refinement.py` (same
author). What is new here is stage 3, described next.

## What is new

**Data-driven axes.** Every axis set used in this benchmark so far has been
*structural* -- tree-adjacent qubit pairs, lattice-adjacent pairs, random
pairs. But a transvection can only lower the score by *cancelling* support a
term already has, so the axes worth trying are readable off the current
state: restrict a term product to a subset of its own support, and you get an
axis that annihilates exactly that part of it. Enumerating those subsets
(sizes 2, 3, 4) over all terms gives a few tens of thousands of candidates --
small enough to score exhaustively, and reaching weight-3 and weight-4 axes
that no pair-based search can express. Measured at 13x13 from a state already
proven optimal against the *entire* two-qubit neighborhood, the best
data-driven axis was worth -10 in a single move.

**Exhaustive two-qubit descent.** Rather than sampling qubit pairs or
restricting to tree-adjacent ones, all `M(M-1)/2` pairs are scored against
all ten distinct two-qubit support actions of `Sp(4, 2)` at once. The score
change of a block move depends on the term products only through the
histogram of their local two-qubit patterns, so all `M^2` histograms come
from 16 matrix products of indicator matrices; and since a move rewrites only
two qubit columns, the histogram tensor updates in `O(M*T)` instead of
`O(M^2*T)`.

**A size-scaled anneal.** The transvection anneal is the stage that actually
escapes local optima -- exhaustive descent proves the state is a two-qubit
local optimum, and only uphill moves get past that. Its step budget is
therefore scaled to the size of the move space (`~M^2` pairs), not held
fixed: at 13x13 a fixed 100k-step budget is less than one sweep of the pair
space and buys nothing, while a scaled budget is worth ~-65. Implementation
notes that make the scaling affordable: term products are stored transposed
so a qubit column is contiguous, the per-step work is two table lookups on
the local two-qubit pattern, randomness is drawn in batches, and operator
updates are deferred -- accepted moves are recorded and replayed onto the 2M
operators once, for the best state only.

**Maximum weight is capped, not optimized.** Every refinement move is refused
if it would push maximum Pauli weight above where placement left it, so the
refiner is Pareto-safe with respect to its own starting point: it can only
trade total weight downward. Relaxing that cap was measured (7x7: -5 total
for +1 max, -9 for +2) and deliberately not taken -- this submission targets
total weight, and `geo_ternary_multitree` remains the better maximum-weight
operating point by a wide margin.
"""

import itertools

import numpy as np

from harness.lattice import hamiltonian

# --------------------------------------------------------------------------
# Tree topologies
# --------------------------------------------------------------------------

def _heap_topology(m):
    """Perfect ternary tree in breadth-first (heap) order: node k's children
    are 3k+1, 3k+2, 3k+3, labelled X, Y, Z. A leaf's Pauli string is built by
    walking leaf -> root, each ancestor contributing the label of the edge
    taken; weight = leaf depth, so weight grows like log_3(M) rather than M.

    Validity: two distinct leaves' paths agree above their deepest common
    ancestor A (a Pauli commutes with itself qubit-by-qubit), leave A via two
    different children and so carry two distinct labels from {X, Y, Z} (any
    two distinct single-qubit Paulis anticommute -- contributes exactly 1),
    and act on disjoint qubits below A. Total parity is odd, so every pair
    anticommutes, for any M and any tree shape.
    """
    def leaf(index):
        x = z = 0
        node = index
        while node:
            parent, label = (node - 1) // 3, (node - 1) % 3
            if label in (0, 1):
                x |= 1 << parent
            if label in (1, 2):
                z |= 1 << parent
            node = parent
        return x, z

    pairs = [(leaf(a), leaf(a + 1)) for a in range(m, 3 * m, 2)]
    parents = [None] + [(router - 1) // 3 for router in range(1, m)]
    return pairs, parents


def _balanced_topology(m):
    """Recursively balanced ternary tree: each router splits its remaining
    leaf budget three ways as evenly as possible. A genuinely different shape
    from the heap whenever M is not one less than a power of three, and it
    lands in different basins -- which is the point of carrying both.
    """
    leaves = []
    parents = [None] * m
    next_router = [0]

    def visit(count, x, z, parent_router):
        if count == 0:
            leaves.append((x, z))
            return
        router = next_router[0]
        next_router[0] += 1
        parents[router] = parent_router
        base, rem = divmod(count - 1, 3)
        for child in range(3):
            cx, cz = x, z
            if child in (0, 1):
                cx |= 1 << router
            if child in (1, 2):
                cz |= 1 << router
            visit(base + (child < rem), cx, cz, router)

    visit(m, 0, 0, None)
    pairs = [(leaves[2 * k], leaves[2 * k + 1]) for k in range(m)]
    return pairs, parents


def _spatial_order(spec):
    """order[k] is the mode assigned to tree leaf-pair k. Recursively splits
    the lattice into three roughly equal groups along its longer axis,
    mirroring the tree's own branching, so physically adjacent sites tend to
    share long common tree ancestries.

    Group sizes are spread as evenly as possible; dumping the leftover from
    n not dividing by 3 into the last group compounds over recursion levels
    into a lopsided partition at sizes that don't divide cleanly by 3.
    """
    coords = spec["coords"]

    def recurse(indices):
        if len(indices) <= 1:
            return list(indices)
        xs = [coords[i][0] for i in indices]
        ys = [coords[i][1] for i in indices]
        axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
        indices = sorted(indices, key=lambda i: coords[i][axis])
        base, rem = divmod(len(indices), 3)
        out, start = [], 0
        for child in range(3):
            size = base + (child < rem)
            out += recurse(indices[start:start + size])
            start += size
        return out

    return recurse(sorted(coords))


# --------------------------------------------------------------------------
# Placement anneals
# --------------------------------------------------------------------------

def _anneal_pairs(m, terms, tree_pairs, start_order, seed, steps):
    """Simulated annealing over which mode owns which tree slot.

    Relabelling which mode owns which of the 2M operators cannot break the
    Majorana algebra -- that is a property of the operator *set*, not the
    labelling -- so this only ever changes score, never validity.

    A pure greedy hill-climb was tried first and plateaus well short of this;
    a larger budget alone does not move it. Accepting worse moves early -- a
    *high* starting temperature, 20% of the starting total -- is what crosses
    those barriers. Only the terms touching a swapped mode need rescoring, so
    a step is O(local).
    """
    pos = [0] * m
    for slot, mode in enumerate(start_order):
        pos[mode] = slot
    involved = [[] for _ in range(m)]
    for index, term in enumerate(terms):
        for mode in {majorana >> 1 for majorana in term}:
            involved[mode].append(index)

    def weight(term):
        x = z = 0
        for majorana in term:
            ox, oz = tree_pairs[pos[majorana >> 1]][majorana & 1]
            x ^= ox
            z ^= oz
        return (x | z).bit_count()

    weights = [weight(term) for term in terms]
    total = sum(weights)
    best_total, best_pos = total, list(pos)
    rng = np.random.default_rng(seed)
    hot, cold = max(1.0, total * 0.2), max(0.01, total * 0.0001)

    for step in range(steps):
        left, right = (int(v) for v in rng.choice(m, 2, replace=False))
        temperature = hot * (cold / hot) ** (step / steps)
        pos[left], pos[right] = pos[right], pos[left]
        changed, delta = {}, 0
        for index in set(involved[left]) | set(involved[right]):
            new = weight(terms[index])
            changed[index] = new
            delta += new - weights[index]
        if delta <= 0 or rng.random() < np.exp(-delta / temperature):
            total += delta
            for index, new in changed.items():
                weights[index] = new
            if total < best_total:
                best_total, best_pos = total, list(pos)
        else:
            pos[left], pos[right] = pos[right], pos[left]

    order = [None] * m
    for mode, slot in enumerate(best_pos):
        order[slot] = mode
    return order


def _anneal_majoranas(m, terms, tree_pairs, order, seed, steps):
    """Simulated annealing over individual Majorana placement -- letting
    gamma_i and gammabar_i move independently rather than as a locked pair.

    A strictly larger search space than `_anneal_pairs`, and cheap on top of
    it. Note that this is exactly a descent in *weight-two logical*
    transvections: for P = gamma_a gamma_b, the symplectic product with
    gamma_e is 0 unless e is in {a, b}, so the transvection swaps those two
    operators and leaves every other one alone.
    """
    leaves = [operator for pair in tree_pairs for operator in pair]
    assignment = [None] * (2 * m)
    for slot, mode in enumerate(order):
        assignment[2 * mode] = 2 * slot
        assignment[2 * mode + 1] = 2 * slot + 1
    involved = [[] for _ in range(2 * m)]
    for index, term in enumerate(terms):
        for majorana in term:
            involved[majorana].append(index)

    def weight(term):
        x = z = 0
        for majorana in term:
            ox, oz = leaves[assignment[majorana]]
            x ^= ox
            z ^= oz
        return (x | z).bit_count()

    weights = [weight(term) for term in terms]
    total = sum(weights)
    best_total, best_assignment = total, list(assignment)
    rng = np.random.default_rng(seed)
    hot, cold = max(1.0, total * 0.15), max(0.01, total * 0.0001)

    for step in range(steps):
        left, right = (int(v) for v in rng.choice(2 * m, 2, replace=False))
        temperature = hot * (cold / hot) ** (step / steps)
        assignment[left], assignment[right] = assignment[right], assignment[left]
        changed, delta = {}, 0
        for index in set(involved[left]) | set(involved[right]):
            new = weight(terms[index])
            changed[index] = new
            delta += new - weights[index]
        if delta <= 0 or rng.random() < np.exp(-delta / temperature):
            total += delta
            for index, new in changed.items():
                weights[index] = new
            if total < best_total:
                best_total, best_assignment = total, list(assignment)
        else:
            assignment[left], assignment[right] = assignment[right], assignment[left]

    return [leaves[leaf] for leaf in best_assignment]


# --------------------------------------------------------------------------
# Local-code representation
#
# One qubit's Pauli is a 2-bit code: 0 = I, 1 = X, 2 = Z, 3 = Y, i.e.
# x | (z << 1). Arrays are stored *transposed*, (n_qubits, n_columns), so
# that one qubit's slice across all operators (or all term products) is
# contiguous -- every hot loop below reads exactly two such slices.
# --------------------------------------------------------------------------

def _codes_from_operators(operators, m):
    codes = np.zeros((m, len(operators)), dtype=np.uint8)
    for column, (x, z) in enumerate(operators):
        for qubit in range(m):
            codes[qubit, column] = ((x >> qubit) & 1) | (((z >> qubit) & 1) << 1)
    return codes


def _operators_from_codes(codes):
    m, n = codes.shape
    operators = []
    for column in range(n):
        x = z = 0
        for qubit in range(m):
            code = int(codes[qubit, column])
            x |= (code & 1) << qubit
            z |= ((code >> 1) & 1) << qubit
        operators.append((x, z))
    return operators


def _products(codes, terms):
    m = codes.shape[0]
    out = np.zeros((m, len(terms)), dtype=np.uint8)
    for index, term in enumerate(terms):
        acc = np.zeros(m, dtype=np.uint8)
        for majorana in term:
            acc ^= codes[:, majorana]
        out[:, index] = acc
    return np.ascontiguousarray(out)


# --------------------------------------------------------------------------
# Weight-2 transvections: lookup tables and the greedy tree-axis descent
# --------------------------------------------------------------------------

_AXES = (1, 2, 3)  # X, Z, Y


def _pair_tables():
    """For each of the 9 two-qubit axis label pairs and each of the 16 local
    patterns (code_left | code_right << 2): the weight change, and the
    resulting pattern."""
    delta = np.zeros((9, 16), dtype=np.int16)
    newpat = np.zeros((9, 16), dtype=np.uint8)
    for index, (left_axis, right_axis) in enumerate(
            (a, b) for a in _AXES for b in _AXES):
        for pattern in range(16):
            left, right = pattern & 3, pattern >> 2
            anti = ((left != 0) and (left != left_axis)) ^ \
                   ((right != 0) and (right != right_axis))
            if anti:
                new_left, new_right = left ^ left_axis, right ^ right_axis
                delta[index, pattern] = (
                    int(new_left != 0) - int(left != 0)
                    + int(new_right != 0) - int(right != 0))
            else:
                new_left, new_right = left, right
            newpat[index, pattern] = new_left | (new_right << 2)
    return delta, newpat


_PAIR_DELTA, _PAIR_NEWPAT = _pair_tables()


def _tree_axis_pairs(parents, radius=2):
    """(parent, child) and (grandparent, grandchild) router pairs.

    Restricted to tree-adjacent pairs deliberately at this stage: an
    operator's support is still a root-to-leaf path here, so an axis spanning
    an edge of that path can cancel structure two operators share, while an
    axis on two tree-unrelated qubits mostly just adds weight. (Once the
    later stages have reshaped supports away from pure tree paths, that stops
    being true, which is why the deep stages search all pairs instead.)
    """
    pairs = set()
    for descendant in range(len(parents)):
        ancestor = parents[descendant]
        for _ in range(radius):
            if ancestor is None:
                break
            pairs.add(tuple(sorted((ancestor, descendant))))
            ancestor = parents[ancestor]
    return sorted(pairs)


def _greedy_tree_descent(codes, terms, parents):
    """Steepest descent over weight-2 transvections on tree-adjacent pairs,
    never letting maximum weight rise above its starting value."""
    products = _products(codes, terms)
    weights = np.count_nonzero(products, axis=0).astype(np.int32)
    cap = int(weights.max())
    moves = [(left, right, index)
             for left, right in _tree_axis_pairs(parents)
             for index in range(9)]

    while True:
        best = None
        for left, right, index in moves:
            pattern = products[left] + (products[right] << 2)
            delta = _PAIR_DELTA[index][pattern]
            total = int(delta.sum())
            if total >= 0:
                continue
            if int((weights + delta).max()) > cap:
                continue
            if best is None or total < best[0]:
                best = (total, left, right, index)
        if best is None:
            break
        _, left, right, index = best
        for array in (products, codes):
            pattern = array[left] + (array[right] << 2)
            out = _PAIR_NEWPAT[index][pattern]
            array[left] = out & 3
            array[right] = out >> 2
        weights = np.count_nonzero(products, axis=0).astype(np.int32)

    return codes, int(weights.sum()), cap


# --------------------------------------------------------------------------
# Size-scaled transvection anneal
# --------------------------------------------------------------------------

def _anneal_transvections(products, weights, pool, cap, seed, steps,
                          hot=4.0, cold=0.01):
    """Metropolis annealing over weight-2 transvections on arbitrary qubit
    pairs -- the stage that actually escapes local optima.

    Returns (best_total, moves) where `moves` is the accepted-move prefix
    leading to the best state seen. Operators are not touched here: replaying
    that prefix onto them once at the end is far cheaper than maintaining
    them step by step.
    """
    products = products.copy()
    weights = weights.astype(np.int32).copy()
    total = int(weights.sum())
    best_total, best_length = total, 0
    moves = []
    rng = np.random.default_rng(seed)
    batch, cursor = 8192, 8192
    pool_size = len(pool)

    for step in range(steps):
        if cursor >= batch:
            draw_pair = rng.integers(0, pool_size, size=batch)
            draw_axis = rng.integers(0, 9, size=batch)
            draw_uniform = rng.random(batch)
            cursor = 0
        pair = pool[draw_pair[cursor]]
        axis = int(draw_axis[cursor])
        uniform = draw_uniform[cursor]
        cursor += 1
        left, right = int(pair[0]), int(pair[1])

        pattern = products[left] + (products[right] << 2)
        delta = _PAIR_DELTA[axis][pattern]
        if not delta.any():
            continue
        candidate = weights + delta
        if candidate.max() > cap:
            continue
        change = int(delta.sum())
        if change > 0:
            temperature = hot * (cold / hot) ** (step / steps)
            if uniform >= np.exp(-change / temperature):
                continue
        out = _PAIR_NEWPAT[axis][pattern]
        products[left] = out & 3
        products[right] = out >> 2
        weights = candidate
        total += change
        moves.append((left, right, axis))
        if total < best_total:
            best_total, best_length = total, len(moves)

    return best_total, moves[:best_length]


def _replay(codes, moves):
    for left, right, axis in moves:
        pattern = codes[left] + (codes[right] << 2)
        out = _PAIR_NEWPAT[axis][pattern]
        codes[left] = out & 3
        codes[right] = out >> 2
    return codes


# --------------------------------------------------------------------------
# Exhaustive two-qubit Sp(4, 2) descent
# --------------------------------------------------------------------------

# Stable representatives of the ten distinct two-qubit support actions of
# Sp(4, 2), as permutations of the 16 local patterns. Elements sharing a
# support action differ only by single-qubit Cliffords, which relabel X/Y/Z
# within a qubit and so can never change any support anywhere -- so one
# representative per class is without loss of generality.
_BLOCK_MAPS = np.asarray([
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15),
    (0, 1, 6, 7, 4, 5, 2, 3, 9, 8, 15, 14, 13, 12, 11, 10),
    (0, 1, 6, 7, 9, 8, 15, 14, 4, 5, 2, 3, 13, 12, 11, 10),
    (0, 1, 6, 7, 9, 8, 15, 14, 13, 12, 11, 10, 4, 5, 2, 3),
    (0, 5, 2, 7, 4, 1, 6, 3, 10, 15, 8, 13, 14, 11, 12, 9),
    (0, 5, 2, 7, 10, 15, 8, 13, 4, 1, 6, 3, 14, 11, 12, 9),
    (0, 5, 2, 7, 10, 15, 8, 13, 14, 11, 12, 9, 4, 1, 6, 3),
    (0, 5, 6, 3, 4, 1, 2, 7, 11, 14, 13, 8, 15, 10, 9, 12),
    (0, 5, 6, 3, 11, 14, 13, 8, 4, 1, 2, 7, 15, 10, 9, 12),
    (0, 5, 6, 3, 11, 14, 13, 8, 15, 10, 9, 12, 4, 1, 2, 7),
], dtype=np.uint8)
_LOCAL_WEIGHT = np.asarray(
    [int(bool(p & 3)) + int(bool(p & 12)) for p in range(16)], dtype=np.int16)
_BLOCK_PROFILE = np.stack([_LOCAL_WEIGHT[_BLOCK_MAPS[i]] for i in range(10)])
_PROFILE_DELTA = (_BLOCK_PROFILE - _LOCAL_WEIGHT[None, :]).astype(np.float32)


def _exhaustive_two_qubit_descent(products, codes, weights, cap,
                                  max_moves=20000, shortlist=64):
    """Steepest descent over *every* qubit pair against *every* two-qubit
    support action of Sp(4, 2).

    The score change of a block move on (l, r) depends on the term products
    only through the histogram of their local patterns, so all M^2 histograms
    are 16 matrix products of indicator matrices; and a move rewrites only two
    qubit columns, so the histogram tensor updates in O(M*T). Maximum-weight
    feasibility is checked only for the shortlist of best-scoring moves, where
    it costs O(T) each.
    """
    m = products.shape[0]
    indicator = np.stack([(products == c).astype(np.float32) for c in range(4)])
    counts = np.zeros((m, m, 16), dtype=np.float32)
    for a in range(4):
        for b in range(4):
            counts[:, :, a + 4 * b] = indicator[a] @ indicator[b].T
    rows, cols = np.triu_indices(m, 1)

    def refresh(qubit):
        column = products[qubit]
        for c in range(4):
            indicator[c, qubit] = (column == c)
        for a in range(4):
            for b in range(4):
                counts[qubit, :, a + 4 * b] = indicator[b] @ indicator[a, qubit]
                counts[:, qubit, a + 4 * b] = indicator[a] @ indicator[b, qubit]

    for _ in range(max_moves):
        scores = (counts @ _PROFILE_DELTA.T)[rows, cols].ravel()
        size = min(shortlist, scores.size - 1)
        shortlisted = np.argpartition(scores, size)[:size]
        shortlisted = shortlisted[np.argsort(scores[shortlisted])]
        chosen = None
        for flat in shortlisted:
            if scores[flat] >= -0.5:
                break
            index, profile = divmod(int(flat), 10)
            left, right = int(rows[index]), int(cols[index])
            pattern = products[left] + (products[right] << 2)
            delta = (_BLOCK_PROFILE[profile][pattern]
                     - _LOCAL_WEIGHT[pattern]).astype(np.int32)
            if int(delta.sum()) < 0 and int((weights + delta).max()) <= cap:
                chosen = (left, right, profile)
                break
        if chosen is None:
            break
        left, right, profile = chosen
        for array in (products, codes):
            pattern = array[left] + (array[right] << 2)
            out = _BLOCK_MAPS[profile][pattern]
            array[left] = out & 3
            array[right] = out >> 2
        weights = np.count_nonzero(products, axis=0).astype(np.int32)
        refresh(left)
        refresh(right)

    return products, codes, weights


# --------------------------------------------------------------------------
# Data-driven axes
# --------------------------------------------------------------------------

def _support_axes(products, sizes=(2, 3, 4)):
    """Axes read off the current state: each term product restricted to a
    subset of its own support.

    A transvection can only lower the score by cancelling support a term
    already has, so these are exactly the axes with something to cancel --
    and unlike any pair-based move set they reach weight 3 and weight 4.
    """
    axes = set()
    for column in range(products.shape[1]):
        local = products[:, column]
        support = np.flatnonzero(local)
        for size in sizes:
            if len(support) < size:
                continue
            for subset in itertools.combinations(support.tolist(), size):
                axes.add(tuple((q, int(local[q])) for q in subset))
    return sorted(axes)


def _axis_effect(products, axis):
    """(anticommutation mask, per-term weight change) for one axis."""
    anti = np.zeros(products.shape[1], dtype=bool)
    change = np.zeros(products.shape[1], dtype=np.int16)
    for qubit, label in axis:
        local = products[qubit]
        anti ^= ((local != 0) & (local != label))
        change += (((local ^ label) != 0).astype(np.int16)
                   - (local != 0).astype(np.int16))
    return anti, np.where(anti, change, 0)


def _apply_axis(codes, axis):
    anti = np.zeros(codes.shape[1], dtype=bool)
    for qubit, label in axis:
        local = codes[qubit]
        anti ^= ((local != 0) & (local != label))
    for qubit, label in axis:
        codes[qubit, anti] ^= label
    return codes


def _support_axis_descent(products, codes, weights, cap, max_moves=400):
    """Steepest descent over data-driven axes, regenerating them after every
    move (the supports they are read from have changed)."""
    for _ in range(max_moves):
        best = None
        for axis in _support_axes(products):
            _, change = _axis_effect(products, axis)
            delta = int(change.sum())
            if delta >= 0:
                continue
            if int((weights + change).max()) > cap:
                continue
            if best is None or delta < best[0]:
                best = (delta, axis)
        if best is None:
            break
        _apply_axis(products, best[1])
        _apply_axis(codes, best[1])
        weights = np.count_nonzero(products, axis=0).astype(np.int32)
    return products, codes, weights


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

_SEEDS = 5          # heap-topology placement seeds, m .. m+4
_FINALISTS = 2      # candidates carried into the deep refiner
_PASSES = 20        # deep-refinement passes, stopped early at a fixed point
_ANNEAL_RUNS = 3    # independent anneals per pass; the best one is kept
_PATIENCE = 3       # consecutive passes finding nothing before stopping
#
# Depth beats breadth, measured, and by a lot. Holding total compute roughly
# fixed and trading anneals-per-pass for passes is worth ~-90 at 11x11 and
# ~-210 at 12x12; spending the same budget on more *finalists* instead made
# both worse. But the anneal must still be individually long enough to sweep
# the move space -- halving the per-pass step budget and doubling the passes
# is much worse (11x11: 5457 vs 5336), which is the same undercooling effect
# that the size-scaled budget exists to avoid.

# Anneal budget, as a formula in M -- not a fixed constant. The move space is
# 9 axis labellings on each of the M(M-1)/2 qubit pairs, so a *fixed* step
# count means fewer and fewer sweeps of it as the lattice grows: 100k steps is
# 38 sweeps at 7x7 but 0.4 of one at 15x15, which is why a fixed-budget anneal
# measurably stops paying at exactly the sizes where the deficit was largest.
_ANNEAL_STEPS_PER_PAIR = 120


def _refine_pass(codes, products, weights, terms, cap, pool, runs, steps, seed):
    """One deep pass: best of `runs` anneals, then both descents on top.

    The anneal supplies the uphill moves that get out of a two-qubit local
    optimum; the two descents then take everything left, including the
    weight-3 and weight-4 axes no pair move can express.
    """
    best_total, best_moves = None, None
    for run in range(runs):
        total, moves = _anneal_transvections(products, weights, pool, cap,
                                             seed=seed + run, steps=steps)
        if best_total is None or total < best_total:
            best_total, best_moves = total, moves

    codes = _replay(codes.copy(), best_moves)
    products = _products(codes, terms)
    weights = np.count_nonzero(products, axis=0).astype(np.int32)
    products, codes, weights = _exhaustive_two_qubit_descent(
        products, codes, weights, cap)
    products, codes, weights = _support_axis_descent(
        products, codes, weights, cap)
    return codes, products, weights, int(weights.sum())


def _deep_refine(finalists, terms, m, pool, passes, runs, steps, tag):
    """Iterate `_refine_pass` to a fixed point.

    Every finalist gets the first pass; after that only the leader continues.
    Postselection is worth paying for because refinement is *not* monotonic in
    the pre-refinement score -- measured at 15x15, a candidate starting 134
    points behind finished 73 ahead -- but that unreliability is a property of
    the *placement* score, not of a score that has already been deep-refined
    once. So the comparison is made after one pass, where it is informative,
    and the remaining budget is spent on one state instead of being split.
    """
    states = []
    for total, cap, codes, seed in finalists:
        products = _products(codes, terms)
        weights = np.count_nonzero(products, axis=0).astype(np.int32)
        states.append([codes, products, weights, cap, seed,
                       int(weights.sum())])

    stalled = 0
    for index in range(passes):
        improved = False
        for state in states:
            codes, products, weights, cap, seed, total = state
            new_codes, new_products, new_weights, new_total = _refine_pass(
                codes, products, weights, terms, cap, pool, runs, steps,
                seed=tag + 97 * index + 13 * seed)
            if new_total < total:
                state[:3] = [new_codes, new_products, new_weights]
                state[5] = new_total
                improved = True
        if index == 0 and len(states) > 1:
            states = [min(states, key=lambda state: state[5])]
            continue
        # Patience, not a hair trigger: a pass is a *stochastic* probe, so a
        # single one finding nothing is weak evidence that a fixed point has
        # been reached. Stopping on the first such pass measurably throws
        # results away -- 14x14 halted after 361s at 9645 that way, where
        # letting it continue reaches 9500.
        stalled = 0 if improved else stalled + 1
        if stalled >= _PATIENCE:
            break

    best = min(states, key=lambda state: state[5])
    return best[0], best[5]


def encode(spec):
    m = spec["M"]
    terms = hamiltonian(spec, model="full")
    if m < 2:
        pairs, _ = _heap_topology(m)
        operators = [op for pair in pairs for op in pair]
        return {"n_qubits": m,
                "majoranas": [_to_string(x, z, m) for x, z in operators],
                "stabilizers": []}

    start = _spatial_order(spec)
    schedules = sorted({100_000, max(100_000, 2500 * m)})
    topologies = [(*_heap_topology(m), [m + i for i in range(_SEEDS)]),
                  (*_balanced_topology(m), [31 * m + 4])]

    # ---- stage 1+2: placement, then greedy tree-axis Clifford descent ----
    candidates = []
    for tree_pairs, parents, seeds in topologies:
        seen = set()
        for steps in schedules:
            for seed in seeds:
                order = _anneal_pairs(m, terms, tree_pairs, start, seed, steps)
                key = tuple(order)
                if key in seen:           # identical placement, identical
                    continue              # downstream search
                seen.add(key)
                operators = _anneal_majoranas(m, terms, tree_pairs, order,
                                              seed=1009 * m + 7, steps=100_000)
                codes = _codes_from_operators(operators, m)
                codes, total, cap = _greedy_tree_descent(codes, terms, parents)
                candidates.append((total, cap, codes, seed))

    # ---- stages 3+4: deep refinement of the finalists, ranked on a
    # refined score rather than a placement score -- see `_deep_refine`.
    candidates.sort(key=lambda c: (c[0], c[1]))
    pool = np.array([(i, j) for i in range(m) for j in range(i + 1, m)],
                    dtype=np.int32)
    anneal_steps = max(200_000, _ANNEAL_STEPS_PER_PAIR * len(pool))

    best_codes, _ = _deep_refine(candidates[:_FINALISTS], terms, m, pool,
                                 _PASSES, _ANNEAL_RUNS, anneal_steps,
                                 tag=7919 * m)

    operators = _operators_from_codes(best_codes)
    return {"n_qubits": m,
            "majoranas": [_to_string(x, z, m) for x, z in operators],
            "stabilizers": []}


def _to_string(x, z, m):
    return "".join(
        "Y" if (x >> q) & 1 and (z >> q) & 1
        else "X" if (x >> q) & 1
        else "Z" if (z >> q) & 1
        else "I"
        for q in range(m))
