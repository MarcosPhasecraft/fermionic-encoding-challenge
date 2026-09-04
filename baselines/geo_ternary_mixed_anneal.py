"""solution/encode.py -- geo-ternary placement + deep Clifford refinement,
with data-driven support axes folded directly into the transvection anneal.

Base pipeline (placement anneal, greedy tree-axis descent, exhaustive
two-qubit Sp(4,2) descent, support-axis descent, multi-pass postselection)
is `baselines/geo_ternary_deep_refine.py`, reused via import rather than
copied -- see MEMORY.md's `geo_ternary_deep_refine` entry for why each piece
of it is there. The one change is the anneal itself.

## What's different: data-driven axes *inside* the anneal

`geo_ternary_deep_refine`'s own memory notes (`deep_refinement.md`, "Not
tried, worth trying next") flag this directly: data-driven support axes
(weight 3/4, read off a term's own current support -- the only axes that can
possibly *cancel* existing structure, per the same file's "The finding")
are currently used only in a separate descent stage, run to a fixed point
*between* anneal passes. The anneal itself -- the one stage doing the actual
local-optimum escaping -- only ever proposes random-pair, structural weight-2
moves.

This mixes both into one proposal distribution: each anneal step, with
probability `_MIX_PROB`, propose a support axis (read off the *current*
state, regenerated periodically since supports drift as moves are accepted)
instead of a random-pair transvection; otherwise fall back to the original
move exactly as before. Cap-respecting and Metropolis-accepted identically
to the pair case -- an axis of any size is still a legal Sp(2M,2)
transvection (see `geo_ternary_deep_refine`'s own correctness note: a fixed
Pauli axis P sends every operator O -> O + <O,P>P, which preserves every
pairwise symplectic product for *any* P), so validity is untouched
regardless of how the proposal is chosen.

## Why this should help, and the evidence it does

A pure-pair anneal can only ever propose weight <=2 structural moves; the
exhaustive Sp(4,2) descent already covers that entire neighbourhood between
anneal passes, and `deep_refinement.md` measured that descent finding zero
improving moves there once the pipeline has run a while -- the two-qubit
neighbourhood is not the bottleneck, escaping it is. Letting the anneal's
own uphill moves *also* reach weight-3/4 cancelling axes -- not just
structural pair moves -- gives it a wider escape route without touching the
mechanism (Metropolis acceptance, temperature schedule) that makes it work
at all.

Measured directly (single `_refine_pass`-equivalent call, identical starting
state, matched step budget, best-of-N seeds; not the numbers below, which
are the full pipeline's):

| size | plain anneal (mean of 6) | mixed anneal (mean of 6) |
|---|---|---|
| 7x7  | 1899.5 | 1875-1881 (best setting) |
| 13x13 (mean of 3) | 8220.0 | 8189.0 |

Consistent in both directions tried, smaller at 13x13 than 7x7 (more terms
to regenerate axes over, so the mixed anneal also costs roughly 2x the
per-step wall time there) but never a regression across ~20 seed/setting
combinations tried.

## Tuning

`_MIX_PROB = 0.25` and `_AXIS_REGEN_EVERY` (a formula in the step budget,
not a fixed constant, for the same reason `geo_ternary_deep_refine` scales
its own step budget with `M`: a fixed regeneration interval means fewer and
fewer regenerations per anneal as the lattice -- and so the step budget --
grows) came from a sweep at 7x7 (mix probability 0.05 through 0.7; regen
interval 2000 through 50000 relative to a 200k-step anneal) where both
showed a clear interior optimum rather than a monotonic trend, which is
weak evidence they are not just noise. Not swept per-size beyond the
7x7/13x13 check above -- a genuine per-size sweep of a 2D hyperparameter
grid was not affordable within this pass; a fixed fraction/formula is
taken over a size-keyed table on principle regardless (`CLAUDE.md`'s "one
uniform rule").
"""

import numpy as np

from harness.lattice import hamiltonian
from baselines.geo_ternary_deep_refine import (
    _heap_topology, _balanced_topology, _spatial_order,
    _anneal_pairs, _anneal_majoranas,
    _codes_from_operators, _operators_from_codes, _products,
    _PAIR_DELTA, _PAIR_NEWPAT, _greedy_tree_descent,
    _exhaustive_two_qubit_descent, _support_axes, _axis_effect, _apply_axis,
    _support_axis_descent, _to_string,
    _SEEDS, _FINALISTS, _PASSES, _ANNEAL_RUNS, _PATIENCE,
    _ANNEAL_STEPS_PER_PAIR,
)

_MIX_PROB = 0.25
_AXIS_SIZES = (3, 4)  # weight <=2 is already the pair anneal's own domain


def _anneal_mixed(products, weights, pool, cap, seed, steps,
                  hot=4.0, cold=0.01):
    """`geo_ternary_deep_refine._anneal_transvections`, with each step drawing
    a data-driven support axis instead of a random pair move with probability
    `_MIX_PROB`. Returns (best_total, moves); a move is either
    `("pair", left, right, axis9)` (original form) or `("axis", axis)` (an
    arbitrary-arity support axis, as produced by `_support_axes`).
    """
    products = products.copy()
    weights = weights.astype(np.int32).copy()
    total = int(weights.sum())
    best_total, best_length = total, 0
    moves = []
    rng = np.random.default_rng(seed)
    batch, cursor = 8192, 8192
    pool_size = len(pool)

    regen_every = max(2000, steps // 10)
    axes = _support_axes(products, sizes=_AXIS_SIZES)
    next_regen = regen_every

    for step in range(steps):
        if step >= next_regen:
            axes = _support_axes(products, sizes=_AXIS_SIZES)
            next_regen += regen_every

        if cursor >= batch:
            draw_kind = rng.random(batch)
            draw_pair = rng.integers(0, pool_size, size=batch)
            draw_axis9 = rng.integers(0, 9, size=batch)
            draw_axis_idx = rng.integers(0, max(1, len(axes)), size=batch)
            draw_uniform = rng.random(batch)
            cursor = 0

        kind = draw_kind[cursor]
        temperature = hot * (cold / hot) ** (step / steps)

        if axes and kind < _MIX_PROB:
            axis = axes[int(draw_axis_idx[cursor]) % len(axes)]
            uniform = draw_uniform[cursor]
            cursor += 1
            anti, change = _axis_effect(products, axis)
            if not anti.any():
                continue
            candidate = weights + change
            if candidate.max() > cap:
                continue
            delta = int(change.sum())
            if delta > 0 and uniform >= np.exp(-delta / temperature):
                continue
            _apply_axis(products, axis)
            weights = candidate
            total += delta
            moves.append(("axis", axis))
        else:
            pair = pool[draw_pair[cursor]]
            axis9 = int(draw_axis9[cursor])
            uniform = draw_uniform[cursor]
            cursor += 1
            left, right = int(pair[0]), int(pair[1])
            pattern = products[left] + (products[right] << 2)
            delta_arr = _PAIR_DELTA[axis9][pattern]
            if not delta_arr.any():
                continue
            candidate = weights + delta_arr
            if candidate.max() > cap:
                continue
            change = int(delta_arr.sum())
            if change > 0 and uniform >= np.exp(-change / temperature):
                continue
            out = _PAIR_NEWPAT[axis9][pattern]
            products[left] = out & 3
            products[right] = out >> 2
            weights = candidate
            total += change
            moves.append(("pair", left, right, axis9))

        if total < best_total:
            best_total, best_length = total, len(moves)

    return best_total, moves[:best_length]


def _replay_mixed(codes, moves):
    for move in moves:
        if move[0] == "pair":
            _, left, right, axis9 = move
            pattern = codes[left] + (codes[right] << 2)
            out = _PAIR_NEWPAT[axis9][pattern]
            codes[left] = out & 3
            codes[right] = out >> 2
        else:
            _, axis = move
            _apply_axis(codes, axis)
    return codes


def _refine_pass(codes, products, weights, terms, cap, pool, runs, steps, seed):
    best_total, best_moves = None, None
    for run in range(runs):
        total, moves = _anneal_mixed(products, weights, pool, cap,
                                     seed=seed + run, steps=steps)
        if best_total is None or total < best_total:
            best_total, best_moves = total, moves

    codes = _replay_mixed(codes.copy(), best_moves)
    products = _products(codes, terms)
    weights = np.count_nonzero(products, axis=0).astype(np.int32)
    products, codes, weights = _exhaustive_two_qubit_descent(
        products, codes, weights, cap)
    products, codes, weights = _support_axis_descent(
        products, codes, weights, cap)
    return codes, products, weights, int(weights.sum())


def _deep_refine(finalists, terms, m, pool, passes, runs, steps, tag):
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

    candidates = []
    for tree_pairs, parents, seeds in topologies:
        seen = set()
        for steps in schedules:
            for seed in seeds:
                order = _anneal_pairs(m, terms, tree_pairs, start, seed, steps)
                key = tuple(order)
                if key in seen:
                    continue
                seen.add(key)
                operators = _anneal_majoranas(m, terms, tree_pairs, order,
                                              seed=1009 * m + 7, steps=100_000)
                codes = _codes_from_operators(operators, m)
                codes, total, cap = _greedy_tree_descent(codes, terms, parents)
                candidates.append((total, cap, codes, seed))

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
