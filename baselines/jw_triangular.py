"""Jordan-Wigner, reference baseline for the graph challenge's Tri-Lattice
table -- see baselines/jw.py for the encoding itself; JW depends only on
spec["M"], not lattice geometry, so the same encode() is reused unchanged.

No order() declared here (unlike jw.py's own row-major one, which returns
a permutation sized for spec["M"] = Lx*Ly under the square-lattice
convention): harness.graphs.build_spec falls back to triangular_lattice's
own canonical default ordering when none is given, which is what "JW with
the canonical ordering, whatever is most natural for the lattice" means
here -- not a re-export of jw.py's square-specific choice, even though for
triangular lattices (M = Lx*Ly, same row-major convention) the two happen
to coincide.
"""

from baselines.jw import encode
