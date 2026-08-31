"""Ternary tree, reference baseline for the graph challenge's Tri-Lattice
table -- see baselines/ternary.py for the encoding itself; the ternary-tree
construction depends only on spec["M"], not lattice geometry, so the same
encode() is reused unchanged.

No order() declared -- see baselines/jw_triangular.py's docstring for why:
harness.graphs.build_spec falls back to triangular_lattice's own canonical
default ordering (row-major, same convention ternary.py's own order()
happens to use too) when none is given.
"""

from baselines.ternary import encode
