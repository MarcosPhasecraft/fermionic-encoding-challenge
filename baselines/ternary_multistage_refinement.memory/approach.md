# Ternary multistage Clifford refinement

## Construction

This submission uses one uniform algorithm for every grid from 3x3 through
15x15.  It does not contain a Jordan-Wigner fallback, a size switch, or a table
of precomputed solutions.

The initial candidate family contains a breadth-first ternary heap and a
recursively balanced ternary tree.  It tries five deterministic heap seeds and
one balanced-tree seed with two annealing lengths, `100000` and
`max(100000, 2500*M)`.  For each candidate it optimizes the placement of paired
Majoranas, optimizes individual Majorana placement, and applies the same local
Clifford descent.  Candidate selection happens only after all of those steps.

Postselecting after Clifford refinement matters because the best starting
score need not have the best refinement basin.  At 7x7, for example, the old
1987-point winner refined to 1910, whereas a 2013-point state from the same
family refined to 1864 with the same maximum weight 8.

The selected candidate then passes through five deterministic refinements:

1. A width-64, depth-12 barrier search over ancestor-pair Clifford moves.
2. Exhaustive two-qubit symplectic (`Sp(4,2)`) block moves for physical pairs
   at tree distance at most two, including plateau and barrier depths 2 and 4.
3. Radius-three Majorana swaps, using best single swaps and a depth-two
   width-200 beam for jointly improving pairs of swaps.
4. Logical weight-four transvections on geometrically local Majorana quartets.
5. Sixteen deterministic 100,000-step anneals over arbitrary physical
   weight-two Pauli transvections.  This pass is reheated until unchanged, with
   a maximum of three passes.

Every stage preserves the maximum-weight cap inherited from the selected
candidate.  Clifford deltas are evaluated from the affected Pauli columns in
vectorized form; this is algebraically equivalent to transforming all complete
Hamiltonian products and makes the 15x15 search practical.

## Independent validation

Three fresh validator processes imported the packaged `encode` function and
ran the frozen exhaustive Majorana verifier and scorer at every claimed size.
Every output used exactly `M` qubits, was well formed, and had zero Majorana
violations.  Several sizes ran concurrently, so the elapsed times below are
operational measurements rather than isolated CPU benchmarks.

| grid | total | max | seconds |
|---:|---:|---:|---:|
| 3x3 | 201 | 4 | 75.8 |
| 4x4 | 438 | 6 | 80.1 |
| 5x5 | 773 | 7 | 84.4 |
| 6x6 | 1231 | 8 | 127.9 |
| 7x7 | 1810 | 8 | 181.3 |
| 8x8 | 2630 | 9 | 197.4 |
| 9x9 | 3430 | 12 | 227.3 |
| 10x10 | 4363 | 12 | 261.5 |
| 11x11 | 5366 | 11 | 307.3 |
| 12x12 | 6623 | 12 | 370.3 |
| 13x13 | 8006 | 13 | 398.6 |
| 14x14 | 9619 | 13 | 436.5 |
| 15x15 | 11202 | 17 | 382.7 |

Against the registered total-weight leaders present during validation, this
ties 3x3 and improves every size from 4x4 through 15x15.  The method reaches
those results through the same search at every size; the 3x3 tie is not a
Jordan-Wigner selection.  Maximum weight is a separate leaderboard metric,
and this total-focused submission does not claim to lead it at every size.
