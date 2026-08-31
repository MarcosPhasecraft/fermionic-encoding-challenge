![Fewest ancillas progress, square lattice](../assets/progress_ancillas_square.png?v=cbb724782085)

Best ancilla count reached so far at 15x15, subject to max Pauli weight ≤ 3, plotted against submission date -- a new point only appears if it's a strict improvement on the prior record. The dotted line is Derby-Klassen's own ancilla count at this size (arXiv 2003.06939) -- both the starting point and the published result here, since this challenge doesn't yet have a separate community record to beat. See the full table below for the complete picture across every swept size.

Lower is better.

## Square lattice -- fewest ancillas at max weight ≤ 3

`min n_ancillas subject to max_weight ≤ 3`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 | 11×11 | 12×12 | 13×13 | 14×14 | 15×15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **2**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |  | **8**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |  | **18**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |  | **32**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |  | **50**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |  | **72**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |  | **98**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |

