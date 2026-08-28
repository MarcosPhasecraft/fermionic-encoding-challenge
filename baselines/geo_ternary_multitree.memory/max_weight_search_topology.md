# Max-weight: from "tie at 8/13, lose at 1" to "zero losses" via a second tree topology

Context: `geo_ternary_opt` (registered) already tied or beat arXiv
2504.21636's own solver-optimized (Hexaly QAP) max Pauli weight at 12 of
13 sizes -- a fast greedy local search matching a real combinatorial
solver almost everywhere. The one gap was 4x4 (ours 6, published 5).
Asked to push further, this file is what was tried.

## Dead end 1: simulated annealing (the lever that worked for total weight)

Total weight's plateau was fixed by SA with a high starting temperature
(escaping bad basins a greedy search got stuck in -- see
`total_weight_search.md`). Tried the same idea here, adapted for a
lexicographic (max, total) objective (max has its own temperature/accept
criterion; total is a secondary anneal only when a move doesn't change
max). Result: *worse* than the existing greedy search at every size
tested, not better:

| L | greedy (geo_ternary_opt) | SA | paper |
|---|---|---|---|
| 9 | 9 | 10 | 9 |
| 12 | 9 | 10 | 10 |
| 15 | 10 | 11 | 11 |

Makes sense in hindsight: max weight is a min-max objective, and the
existing greedy search already evaluates *every* candidate swap at each
step (not a sampled subset) before committing -- there's no "stuck
choosing a locally-good-but-globally-bad move" problem for annealing's
randomness to fix here. It just adds noise to an already-thorough search.

## Dead end 2: more restarts / bigger budget, same tree

Tried 10 independent restarts (different seeds) and a single run at 10x
the iteration budget, both against `geo_ternary_opt`'s own tree:

| L | current | 10 restarts | 10x budget |
|---|---|---|---|
| 4 | max=6 | max=6 (total improved 504->496) | max=6 (total improved to 494) |
| 12 | max=9 | max=9 (total improved 8312->7994) | max=9 (total improved to 7760) |

Max weight never moved, at either size, under either lever -- only total
weight improved, as a side effect. That's the signature of a genuine
structural floor of *this specific tree*, not a search-budget problem:
more compute exploring the same tree's mode-assignment space converges to
the same worst-case bottleneck every time.

## What worked: a second, differently-shaped tree

If the floor is the tree's, not the search's, the fix is a different
tree -- not a longer search on the same one. Reused arXiv 2504.21636's
own ternary tree (the Sierpinski-recursion matrix construction already in
`baselines/ternary.py`, reimplemented self-contained here rather than
imported -- see the module docstring for why) as a *second* candidate,
searched by the exact same generic `_optimize_order` (which only ever
looks at a `tree_pairs` list's (x, z) content, never at its origin).

First check: does Sierpinski + search fix 4x4 specifically?

| construction | max@4x4 |
|---|---|
| geo_ternary tree + search | 6 |
| Sierpinski tree + search | **5** (matches published exactly) |
| BK/Fenwick (binary) tree + search | 7 (worse, as expected -- binary trees have larger depth for the same M) |

Yes. Then the full 3x3-15x15 sweep, both topologies searched from the
same geometric starting order, keeping whichever gives the lower
(max, total):

| L | geo_ternary tree | Sierpinski tree | best-of-both | paper |
|---|---|---|---|---|
| 3 | (5, 243) | (5, 245) | (5, 243) | 5 |
| 4 | (6, 504) | **(5, 518)** | (5, 518) | 5 |
| 5 | **(6, 928)** | (7, 934) | (6, 928) | 7 |
| 6 | (7, 1498) | (7, 1506) | (7, 1498) | 7 |
| 7 | **(7, 2137)** | (7, 2205) | (7, 2137) | 8 |
| 8 | (8, 3029) | (8, 3057) | (8, 3029) | 8 |
| 9 | (9, 4077) | (9, 4063) | (9, 4063) | 9 |
| 10 | (9, 5141) | (9, 5059) | (9, 5059) | 9 |
| 11 | (9, 6383) | (9, 6383) | (9, 6383) | 9 |
| 12 | **(9, 8312)** | (9, 8396) | (9, 8312) | 10 |
| 13 | (10, 9912) | (10, 9873) | (10, 9873) | 10 |
| 14 | **(10, 10802)** | (10, 11646) | (10, 10802) | 10 |
| 15 | **(10, 13786)** | (11, 13778) | (10, 13786) | 11 |

Neither topology dominates the other size-by-size (geo_ternary alone
wins outright at 5x5/7x7/12x12/15x15; Sierpinski is what rescues 4x4, and
also quietly improves total weight at several tied-on-max sizes). That's
exactly why running both and keeping the better result -- not picking one
a priori -- is the fix, not a coincidence of these particular sizes.

## Result: zero losses against the paper's Table I max weight

| | ties | beats | losses |
|---|---|---|---|
| geo_ternary tree alone (`geo_ternary_opt`, registered) | 8 | 4 | 1 (4x4) |
| geo_ternary + Sierpinski, best-of-both (this submission) | 9 | 4 | **0** |

Verified end-to-end through the actual harness (`harness.evaluate.evaluate`,
not just the raw search), full 3x3-15x15 sweep, all `passed: True`.

## Runtime

~0.1-16s per size (both topologies searched, greedy not annealed --
much cheaper than the total-weight submission's SA). Full 3x3-15x15
sweep: ~80s.

## Not tried (out of scope here, noted for later)

- More than two topologies (e.g. a hybrid/interpolated tree, or BK
  despite its worse showing here -- binary trees might still help at a
  specific size the other two don't).
- Restarts *combined with* the dual-topology approach (restarts helped
  total weight as a side effect in the single-topology tests above; might
  do the same here without costing anything on max, since they never hurt
  max weight, only failed to improve it, in every test run).
