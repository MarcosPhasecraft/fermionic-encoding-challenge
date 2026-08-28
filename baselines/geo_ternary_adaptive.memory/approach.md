# Geometry-adaptive ternary tree

This submission searches four valid ternary-tree leaf layouts: the existing
heap topology and three recursive geometry-driven topologies. It minimizes
the full harness total-weight objective through mode-slot annealing, then
through a bounded anneal over individual Majorana-leaf assignments.

It is currently claimed only for 7x7, where it was verified locally with
total Pauli weight 1988 and maximum Pauli weight 8. The previous registered
five-restart geometry-aware ternary baseline scored 1999 and 10 respectively.

The individual-Majorana phase grows too expensive for a broad size claim in
the present implementation; do not generalize this result to larger grids
without an incremental scorer or fresh benchmarking.
