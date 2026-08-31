# Triangular axial deep refinement

## Scope

This is one deterministic, ancilla-free encoding rule for every open
triangular lattice from `3x3` through `8x8`. It contains no table of
precomputed mappings, no score lookup, and no branch selecting a named
encoding at particular sizes. `encode.py` is self-contained apart from
NumPy and consumes only the supplied `spec`.

## Algorithm

The search starts from three complementary families of valid Majorana
frames: a breadth-first ternary tree, a recursively balanced ternary tree,
and a Jordan--Wigner path. The path is an initializer, not an output switch:
all families enter the same optimization and the final mapping is selected
only after common refinement.

For placement, the Cartesian recursive order is supplemented by three
triangular axial recursions. These use the natural coordinates `x`, `y`, and
`x-y`, each constant along one of the three bond directions. Mode pairs are
annealed over tree/path slots, followed by a second anneal that may place the
two Majoranas of a mode independently.

Every later operation is a global Clifford conjugation and therefore
preserves the Majorana algebra exactly:

1. greedy weight-2 transvections on nearby topology routers;
2. size-scaled simulated annealing over every qubit pair and all nine
   weight-2 Pauli axes;
3. exhaustive descent over all ten distinct two-qubit support actions of
   `Sp(4,2)`;
4. greedy data-driven transvections of weights 2, 3, and 4, generated from
   current Hamiltonian-term supports.

Four candidates from each initializer family receive a full refinement
pass. The best refined basin then continues for up to 30 passes, with five
null stochastic passes required before early stopping. Maximum term weight
is capped at the candidate's post-placement value while total weight is
minimized.

## What is new here

Balanced ternary Majorana frames, Jordan--Wigner strings, simulated
annealing, and Clifford/symplectic transformations are established ideas.
The earlier square-lattice submissions in this repository already developed
the deep all-pair Clifford engine and data-driven axes. This submission's
new contribution is their graph-native triangular synthesis: axial
`(x,y,x-y)` placement basins, uniform competition among path/heap/balanced
frames, topology-stratified postselection after common refinement, and a
more aggressive size-scaled escape schedule.

The published Table-II triangular number at `8x8` is retained as a separate
reference: the repository notes that its undisclosed ordering is not
reproduced by the local harness baselines. This submission scores 3569 at
`8x8`: it beats the executable local TT (4613) and JW (5132) baselines, but
does **not** beat the paper's 2384 reference. Results should report both
comparisons rather than treating the paper row as an executable local
submission.

## Exact results

All rows below passed the unchanged exact verifier before scoring.

| L | Total | Max | Current executable total leader | Reduction |
|---:|---:|---:|---:|---:|
| 3 | 257 | 4 | 297 | 13.5% |
| 4 | 586 | 6 | 700 | 16.3% |
| 5 | 1059 | 8 | 1337 | 20.8% |
| 6 | 1730 | 10 | 2256 | 23.3% |
| 7 | 2572 | 9 | 3363 | 23.5% |
| 8 | 3569 | 11 | 4613 | 22.6% |

At `8x8`, the non-executable paper reference is 2384, so this submission
does not beat that reference. The full machine-readable records, including
wall times, are in `memory/validation.json`.

## Reproduction

Submit this directory as a unit. The authoritative sweep is the unchanged
graph harness with `graph="triangular"`, `Lx=Ly`, the full Hamiltonian term
list, exact verification before scoring, and sizes 3 through 8.
