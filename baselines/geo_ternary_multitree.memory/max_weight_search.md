# Max-weight local search -- findings

Context: `geo_ternary`'s tree construction gives a valid encoding regardless
of which spec mode is assigned to which tree slot -- the anticommutation
algebra depends only on the *set* of 2M operators, not on the labelling.
That makes the mode<->slot assignment a pure scoring lever, safe to
optimize freely with zero risk of breaking `verify()`.

## What was tried first: pure geometry (`_spatial_order` alone)

Recursive 3-way spatial partition of the lattice, no search. Already beat
the paper's published (arXiv 2504.21636 Table I) *total* weight at every
size 3x3-15x15, but lagged its *max* weight by 1-4 at most sizes, motivating
the search below.

## The search: hill-climb on (max_weight, total_weight)

Repeatedly pick a mode implicated in a current worst-weight term, try
swapping its tree slot with every other mode (sampling 80 when there are
more candidates), commit the best strictly-improving swap, or make a
random one when none improves (to escape local optima) -- track best seen,
return it even if later exploration wanders off. Full algorithm and
bookkeeping details are in `solution/encode.py`'s `_optimize_order`
docstring.

## Result: matches or beats the paper's own solver-optimized numbers

| L | search max | paper TT[1] max | search total | paper TT[1] total |
|---|---|---|---|---|
| 8 | 8 | 8 | 3031 | 3237 |
| 9 | 9 | 9 | 4027 | 4303 |
| 10 | 9 | 9 | 5147 | 5473 |
| 11 | 9 | 9 | 6367 | 6799 |
| 12 | **9** | 10 | 7820 | 8342 |
| 13 | 10 | 10 | 10038 | 9853 |
| 14 | 10 | 10 | 10802 | 11844 |
| 15 | **10** | 11 | 13772 | 13942 |

Ties the paper's published max weight at every size 8-15 except two, where
it's strictly *better* (12x12: 9 vs 10; 15x15: 10 vs 11) -- despite the
paper's number coming from an actual QAP solver (Hexaly), not a formula.
Total weight is a mixed bag by comparison (worse than the paper at 13x13
and 14x14 in this table) -- expected, since the search's objective is
lexicographic on (max, total): it will accept a total-weight increase to
buy a max-weight decrease, every time. This is the right tradeoff *for
this specific ask* (beating max weight specifically), not a strict
improvement on the total-weight-focused version that came before it. See
`results.tsv` and `git log` on `solution/encode.py` for that version if
total weight alone is ever the target again.

## Iteration budget: 20*m (floor 200), not fixed

Tested 4000 vs 12000 iterations at 12x12/13x13/15x15: max weight was
already identical at 4000; total weight moved by well under 1%. The
budget is a size-driven formula (not a lookup table keyed to specific
Lx/Ly, which CLAUDE.md's "one uniform rule" requirement forbids) precisely
because of this -- it needed to generalize past the sizes actually
profiled, and a flat constant would either waste time on small lattices
or undershoot on large ones.

Runtime: roughly 5-8s at 15x15 (M=225) for the full 3x3-15x15 sweep's
worth of calls, dominated by `_optimize_order`, not the tree construction
itself. Worth knowing if this ever needs to run inside a tighter loop
(e.g. a leaderboard sweep across many sizes) -- CLAUDE.md's traps list
flags evaluation speed as the actual binding constraint once search is
involved, and this specific search is the source of it here.
