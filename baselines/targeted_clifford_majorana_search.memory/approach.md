# Targeted Clifford and adaptive Majorana search

The original geometric multitree seed is inlined, with attribution to
`baselines/geo_ternary_multitree.py`. It compares a heap ternary tree and a
Sierpinski linear encoding using the same geometric assignment search.

The new search mixes individual Majorana swaps and Clifford transvections at
every step. Many axes deliberately cancel part of an overweight term's support.
If A agrees with an offending Pauli P on a selected support except at a single
pivot, where it has a different nonidentity label, then A and P anticommute.
Conjugating by exp(-i*pi*A/4) replaces P by AP up to phase, cancelling all the
selected factors except the pivot. The global objective accounts for changes
to every other term.

With target K, the search energy is the weighted squared excess above K, plus
a small total-weight tie breaker. Penalties increase on persistent violations
and decay toward one on satisfied terms. The best state is retained under the
unweighted tuple (squared excess, number of violations, maximum, total).

The uniform driver uses seeds (101,103,107,109), each with
max(100000, int(5000000*637/number_of_terms)) proposals. It lowers the target
after success and continues from partial candidates after failure. Only a
mapping improving actual (maximum,total) relative to the seed can replace the
returned incumbent. This guarantees no regression relative to that seed, not
relative to every earlier submission. No record table controls the search.

Clifford conjugation and Majorana permutation preserve the complete algebra.
Cached products are checked against reconstruction periodically inside the
native helper. Final validity and score remain the frozen evaluator's decision.
The embedded native engine contains optional experimental move modes, but the
uniform submission always uses mode 1, the tested single-move adaptive search.

The helper is compiled from embedded source in a temporary directory and kept
alive for the Python module's lifetime. Its packed-word capacity is computed
from the input, with at least four words to preserve the tested 3-15 layout.
There is no 256-qubit storage cap in this packaged adapter.

Fresh uniform runs achieved maximum 6 at 7x7, 8 at 12x12 and 13x13, and 9 at
15x15. A checkpoint-assisted 9x9 maximum of 7 is not part of this submission's
claimed reproducible curve; its uniform run returned 8. The README distinguishes
these development observations from the administrator's final acceptance gate.
