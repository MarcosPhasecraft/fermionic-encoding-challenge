# Clifford transvections for total weight -- what carried, what didn't

Context: `baselines/geo_ternary_clifford.py` (Codex GPT-5.6 Sol) took the
total-weight lead from `geo_ternary_anneal_ensemble` at every size 6x6+.
This is the investigation into *why*, and an attempt to take it back.

## The mechanism, and why it reaches further than anything before it

Conjugating every Majorana by a fixed Pauli axis `P` sends `O -> O + <O,P>P`
(the symplectic transvection): an operator anticommuting with `P` picks up
`P`, one commuting with it is untouched. This preserves every pairwise
symplectic product, so the whole 2M-operator set stays pairwise
anticommuting and the encoding stays valid -- for **any** `P`, not just
carefully chosen ones. Verified directly rather than assumed: 300 random
arbitrary-support axes applied in sequence to a valid 5x5 mapping, checking
all `2M choose 2` pairs after each -- still valid throughout.

Why this matters more than the earlier searches in this project: mode
relabelling and mode-slot annealing only permute *which mode owns which
existing operator*. Even the GF(2) column-XOR experiment (see
`max_weight_search_topology.md`'s "not tried" note and the earlier
matrix-perturbation work) only moves within `GL_M(F_2)`. Transvections
generate the full symplectic group `Sp(2M, F_2)`, which is strictly
larger, and they genuinely reshape operator *supports* rather than
shuffling them. This is the lever that was missing.

Efficiency note: the map is linear over GF(2), so a Hamiltonian term's
*product* transvects by the same rule as a single operator. A candidate
axis can therefore be scored against cached term products directly --
O(#terms) per candidate, no rebuild from operators.

## Axis set: their tree-adjacency was right, my lattice hypothesis was wrong

Measured at 9x9, all starting from `geo_ternary_anneal_ensemble`
(total 3577, max 12); Codex's submission scores 3503 here.

| axis set | total | note |
|---|---|---|
| tree-adjacent (parent/child + grandparent/grandchild) | **3472** | theirs; best |
| tree + lattice-adjacent | 3472 | lattice adds nothing on top |
| lattice-adjacent only | 3564 | barely moves |
| single-qubit only | 3577 | no effect whatsoever |
| all qubit pairs, 3000 sampled of 29160 | 3549 | worse -- dilutes the useful axes |

I predicted lattice-adjacent axes would beat tree-adjacent ones, reasoning
that the cost function is built from lattice edges. Wrong, and instructively
so: operator *supports* are root-to-leaf tree paths, so an axis spanning an
edge of such a path can cancel structure two operators share, while an axis
on two tree-unrelated qubits mostly just adds weight. Widening the set
doesn't help either -- sampling broadly is worse than searching the small
right set exhaustively.

## Stacking more machinery on top: all of it added exactly zero

At 9x9, every variant converged to the same 3472:

| pipeline | total |
|---|---|
| ensemble -> clifford | 3472 |
| ensemble -> individual-Majorana anneal -> clifford | 3472 |
| ensemble -> clifford -> (leaf-anneal -> clifford) x3 | 3472 |
| ensemble -> annealed transvections (Metropolis) | 3577 (no improvement at all) |

Two things worth recording:

- **Individual-Majorana annealing** (letting `gamma_i` and `gammabar_i`
  move independently rather than as a locked pair) is a strictly larger
  search space than the mode-pair annealing this project has always used,
  and it is part of why the Codex submission works. On *my* starting point
  it changes nothing (3577 -> 3577): the mode-pair ensemble has already
  found a local optimum that finer moves can't improve. It helps them
  because their pre-Clifford placement is weaker.
- **Annealing over transvections** instead of greedy descent found nothing.
  Unlike mode placement -- where a high starting temperature was exactly
  what broke the plateau -- greedy descent here already evaluates every
  axis in the (small, well-chosen) set each sweep, so there is no basin to
  escape.

## The selection rule was wrong: stage 1's score does not predict stage 2's

Found while probing 15x15. The pipeline originally annealed `_N_RESTARTS`
times, kept the single best-scoring order, and Clifford-descended that one.
That is the wrong rule, because **Clifford descent is not monotonic in the
pre-Clifford score**. Measured at 15x15 over 14 seeds:

| seed | pre-Clifford | post-Clifford |
|---|---|---|
| 236 | **11582** (best pre) | 11445 |
| 237 | 11600 | 11427 |
| 227 | 11716 | **11372** (best post) |
| 233 | 11726 | 11455 |
| 225 | 11734 | 11507 |

The best starting point finishes third; the third-best starting point wins.
So `_candidate_orders` now returns every annealed order and `encode`
descends all of them, selecting on the *final* score. This can never be
worse than the old rule (the order it used to pick is still a candidate) and
costs `_N_RESTARTS` descents instead of one.

Gains from the fix alone, holding everything else constant: 3x3 207 -> 204,
5x5 838 -> **819**, 9x9 3472 -> **3459**; every other size unchanged. The
5x5 result is an outright board record -- it beats Jordan-Wigner's 825,
which had held that size against every submission to date.

Note it did *not* help at 15x15, where seed 227 happens to win on both
measures, nor at 12x12/13x13 where the deficit is large. Its value is
concentrated in sizes where several candidates finish close together.

## Result: took rank 1 at 6 of 13 sizes; did not reclaim the lead outright

`geo_ternary_anneal_ensemble` + tree-axis Clifford descent, full sweep,
verified end-to-end through the harness (all `passed: True`):

| L | this | Codex clifford | board rank-1 | outcome |
|---|---|---|---|---|
| 3 | 204 | 204 | 201 (JW) | ties Codex, JW wins |
| 4 | 466 | 466 | 448 (JW) | ties Codex, JW wins |
| 5 | **819** | 845 | 825 (JW) | **rank 1 -- new board record** |
| 6 | 1325 | 1322 | 1322 | loses by 3 |
| 7 | **1904** | 1910 | 1910 | **rank 1** |
| 8 | 2703 | 2667 | 2667 | loses |
| 9 | **3459** | 3503 | 3503 | **rank 1** |
| 10 | **4457** | 4539 | 4539 | **rank 1** |
| 11 | **5567** | 5589 | 5589 | **rank 1** |
| 12 | 6826 | 6766 | 6766 | loses |
| 13 | 8289 | 8047 | 8047 | loses |
| 14 | **9679** | 9766 | 9766 | **rank 1** |
| 15 | 11372 | 11361 | 11361 | **loses by 11 (0.1%)** |

Honest read: this is a partial reclaim, not a clean one. The two pipelines
trade wins, and the margins are small in both directions. The pattern that
does hold is that mine is stronger in the 9x9-11x11 and 14x14 band and
weaker at 12x12-13x13 and the small sizes -- consistent with the two
approaches finding different local optima rather than one being better.

**15x15 lost by 11 points (0.1%)** and is the size the leaderboard's
progress chart tracks, so it was the obvious target -- and it resisted.
Probing 14 seeds instead of 5 found starting points as good as 11582
(vs the 11716 the submission uses) but none of them descended below
11372. Raising `_N_RESTARTS` is therefore *not* the missing lever here;
that avenue is spent. 6x6 (losing by 3) looks like the better next
target, and 12x12/13x13 are large enough deficits to need a different
idea rather than more search.

## Max weight: unchanged and deliberately not targeted

Stage 2 refuses any move raising maximum weight above where stage 1 left
it, so it only trades total weight downward. Starting from the
*max*-optimized `geo_ternary_multitree` instead (max 9 at 9x9) the cap is
so tight that Clifford descent achieves almost nothing (4063 -> 4053) --
the two objectives want genuinely different operating points, and
`geo_ternary_multitree` remains far better on max weight (10 vs this
submission's 15 at 15x15).
