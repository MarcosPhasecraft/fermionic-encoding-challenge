# Total-weight local search -- findings

Same safety argument as `max_weight_search.md`: relabelling which mode
owns which of the 2M already-valid tree operators can't break the
Majorana algebra (a property of the operator *set*, not the labelling),
so this search is free to hill-climb purely on score.

## Context: why a second search, not a reuse of the max-weight one

The max-weight-focused search (`geo_ternary_opt`, registered) hill-climbs
on `(max_weight, total_weight)` lexicographically -- it will happily take
a total-weight *increase* to buy a max-weight decrease. Checking it
against `LEADERBOARD.md`'s total-weight table confirms this actually
happens: `geo_ternary_opt`'s total weight is *worse* than the
un-optimized `geo_ternary`'s at several sizes (e.g. 12x12: 8312 vs 7732).
So beating total weight specifically needed a different objective, not
just more of the same search.

## What was tried first: greedy hill-climb on total alone

Same move set as the max-weight search (swap two modes' tree slots,
commit the best-of-many-candidates improving swap), objective changed to
minimize total weight directly, candidate mode chosen weighted toward
high current contribution to total weight (instead of "pick from the
current worst term", which doesn't have an analogue when there's no
single bottleneck).

Result: consistently landed *worse* than TT (snake)'s registered total
weight at every size tried (8x8: 3043 vs 2873; 12x12: 7732 vs 7358), and
increasing the iteration budget 5x moved some sizes not at all (12x12
was bit-for-bit identical at 4000 and 20000 iterations) -- a genuine
plateau, not just slow convergence. Random-permutation restarts (5 per
size, different starting points, same greedy search) did not escape it
either -- every restart converged to something worse than the geometric
starting point's own local optimum.

## What worked: simulated annealing, high starting temperature

Same move set (random pair of modes, swap their tree slots), but instead
of greedy-only, accept a worse move too with probability
`exp(-delta/T)`, `T` cooling geometrically over the run. The first
attempt (`T0` = 2% of starting total) beat TT-snake at 3 sizes (7x7,
8x8, 9x9) but plateaued *exactly* at the un-optimized starting value for
12x12-15x15 -- no movement at all, suggesting the temperature was too
low to escape those basins even early on.

Raising `T0` to 20% of the starting total (instead of 2%) is what
actually broke the remaining plateaus. Comparison at a few sizes, same
iteration budget:

| L | T0=2% | T0=20% |
|---|---|---|
| 10 | 4871 | 4675 |
| 12 | 7732 (no change from start) | 7028 |
| 14 | 10320-10422 (near miss) | 9824 |

## Result: beats the leaderboard's best registered total weight at 9 of 13 sizes

Final schedule: `T0 = 0.2 * starting_total`, `Tend = 0.0001 * starting_total`,
`max_iters = max(100_000, 2500*m)`.

| L | search total | best registered (LEADERBOARD.md) | who | delta |
|---|---|---|---|---|
| 3 | 243 | 201 | JW | — |
| 4 | 492 | 448 | JW | — |
| 5 | 876 | 825 | JW | — |
| 6 | 1414 | 1356 | JW | — |
| 7 | 1999 | 2065 | JW | **-3.2%** |
| 8 | 2839 | 2873 | TT (snake) | **-1.2%** |
| 9 | 3629 | 3849 | TT (snake) | **-5.7%** |
| 10 | 4755 | 4835 | TT (snake) | **-1.7%** |
| 11 | 5841 | 5947 | TT (snake) | **-1.8%** |
| 12 | 7028 | 7358 | TT (snake) | **-4.5%** |
| 13 | 8574 | 8743 | TT (snake) | **-1.9%** |
| 14 | 9824 | 10240 | TT (snake) | **-4.1%** |
| 15 | 11734 | 12020 | TT (snake) | **-2.4%** |

3x3-6x6 don't beat JW, and shouldn't be expected to: 3x3's JW total
(201) is proven globally optimal by exhaustive search over all 9!
orderings (see NOTES.md) -- there is no room left to find there, and the
same is plausible (not separately proven) for 4x4-6x6 given how close
JW already is to the information-theoretic floor at that scale (very
few qubits, very little freedom to rearrange).

## Runtime

~1-11s per size across the swept range (dominated by `_optimize_order`,
scales with the `2500*m` iteration budget). Full 3x3-15x15 sweep: well
under a minute. Noted per CLAUDE.md's "evaluation speed is the binding
constraint" trap -- this is the second search living in `encode()`
(after the max-weight one, still available as the registered baseline
`geo_ternary_opt`), so anything building on this file should keep that
in mind if it's ever called in a tighter loop (e.g. inside a leaderboard
sweep across many sizes/orderings).

## Update: this exact version got registered (`geo_ternary_anneal`), then beaten by its own ensemble

The single-run version above was accepted as `baselines/geo_ternary_anneal.py`
and became the leaderboard's rank-1 total weight at every size 7x7-15x15
(`LEADERBOARD.md`, checked directly, not assumed). Asked to improve on it
further -- i.e. beat my own already-registered best -- the next lever
tried was repetition: does re-running `_anneal_once` with a different
seed from the *same* starting order land somewhere different?

Tried, and confirmed yes: each run's own randomness (which pair gets
proposed each step, which Metropolis coin flips land which way) explores
a genuinely different path through the same search space, so independent
runs settle into different local optima even from an identical start.
Concretely tested first at 3 sizes (5 restarts each, same iteration
budget per restart):

| L | single run | best of 5 |
|---|---|---|
| 9 | 3629 | 3605 |
| 12 | 7028 | 6832 |
| 15 | 11734 | 11492 |

Also tried and rejected: mixing in occasional 3-way cyclic moves (rotate
three modes' slots instead of swapping two) alongside the pairwise swaps,
at a few different mix probabilities -- consistently landed *worse* than
pure pairwise swaps at the same total iteration budget (e.g. L=9: 3671
vs 3629), most likely because it dilutes the budget spent on the
pairwise move that's actually doing the work, for a move type that
doesn't obviously help here.

Integrated as `_N_RESTARTS = 5` independent calls to `_anneal_once`
(`solution/encode.py`), keeping the lowest-total result. Seeds are
`m, m+1, ..., m+4` -- a formula, not a lookup table. Full sweep,
verified end-to-end through the actual harness:

| L | single-run (registered `geo_ternary_anneal`) | 5-restart ensemble | change |
|---|---|---|---|
| 3 | 243 | 243 | none (JW=201 still unbeaten) |
| 4 | 492 | 492 | none (JW=448 still unbeaten) |
| 5 | 876 | 876 | none (JW=825 still unbeaten) |
| 6 | 1414 | 1388 | -1.8% (JW=1356 still unbeaten) |
| 7 | 1999 | 1999 | none |
| 8 | 2839 | 2787 | **-1.8%** |
| 9 | 3629 | 3577 | **-1.4%** |
| 10 | 4755 | 4635 | **-2.5%** |
| 11 | 5841 | 5725 | **-2.0%** |
| 12 | 7028 | 6922 | **-1.5%** |
| 13 | 8574 | 8380 | **-2.3%** |
| 14 | 9824 | 9824 | none |
| 15 | 11734 | 11716 | **-0.2%** |

Improves 8 of 13 sizes with zero regressions anywhere (the "none" rows
are exact ties, not losses -- some sizes' local-optimum landscape is
apparently narrow enough that 5 different seeds all converge to the same
place). Full 3x3-15x15 sweep runtime: ~5 minutes (5x the single-run
version's ~1 minute, as expected -- this is `_N_RESTARTS` independent
full anneals, not a smarter search).
