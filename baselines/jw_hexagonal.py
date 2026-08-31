"""Jordan-Wigner, reference baseline for the graph challenge's Hex-Lattice
table -- see baselines/jw.py for the encoding itself; JW depends only on
spec["M"], not lattice geometry, so the same encode() is reused unchanged.

No order() declared: jw.py's own row-major order() returns a permutation
sized for spec["M"] = Lx*Ly (the square-lattice convention), which is the
wrong length for a hex lattice (M = 2*Lx*Ly, two sites per unit cell) --
importing it here would raise a mismatched-permutation-length error the
moment it's used. harness.graphs.build_spec falls back to hex_lattice's
own canonical default ordering (row-major over unit cells, A/B sublattice
sites adjacent) when none is given, which is the correct, natural choice
for this lattice type anyway.
"""

from baselines.jw import encode
