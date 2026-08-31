"""Ternary tree, reference baseline for the graph challenge's Hex-Lattice
table -- see baselines/ternary.py for the encoding itself; the ternary-tree
construction depends only on spec["M"], not lattice geometry, so the same
encode() is reused unchanged.

No order() declared -- see baselines/jw_hexagonal.py's docstring for why:
ternary.py's own order() is sized for M = Lx*Ly (the square-lattice
convention), the wrong length for a hex lattice's M = 2*Lx*Ly.
harness.graphs.build_spec falls back to hex_lattice's own canonical
default ordering when none is given.
"""

from baselines.ternary import encode
