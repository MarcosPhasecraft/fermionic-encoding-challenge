# Geometry-adaptive ternary tree with local Clifford refinement

This submission begins with the four-topology adaptive ternary search, then
adds a score-decreasing Clifford layer.  The new layer considers weight-two
Pauli transvections between parent/child and grandparent/grandchild router
qubits.  Such conjugations preserve every symplectic inner product, hence the
Majorana algebra, while changing Pauli supports.

The Clifford candidate set is linear in the number of qubits.  At each step
the search chooses one of the two strongest improving moves using a fixed seed,
and refuses any move that raises the starting maximum Pauli weight.  This makes
the final mapping Pareto-safe relative to its pre-Clifford starting point.

On 7x7, the frozen harness reports total Pauli weight 1910 and maximum weight
8, versus 1987 and 8 for `submission_geo_ternary_adaptive`.  The unrestricted
all-qubit-pairs experiment reached 1908 but raised maximum weight to 9; the
max-preserving local-tree rule was retained instead.  Seed ensembles and
re-annealing Majorana placement after Clifford descent did not beat the compact
single seeded path enough to justify their runtime.

Exact `check_at_size` results for the packaged file, evaluated independently at
every claimed square size:

| grid | total | max |
|---:|---:|---:|
| 3x3 | 204 | 5 |
| 4x4 | 466 | 6 |
| 5x5 | 845 | 7 |
| 6x6 | 1322 | 8 |
| 7x7 | 1910 | 8 |
| 8x8 | 2667 | 9 |
| 9x9 | 3503 | 12 |
| 10x10 | 4539 | 10 |
| 11x11 | 5589 | 12 |
| 12x12 | 6766 | 12 |
| 13x13 | 8047 | 13 |
| 14x14 | 9766 | 14 |
| 15x15 | 11361 | 17 |
