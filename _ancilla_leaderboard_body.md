One board per maximum-weight cap. A submission picks the cap it targets (`"max_weight"` in `submission.json`, default 3) and is listed on **every** board whose cap it actually satisfies -- an encoding reaching weight 3 everywhere appears on both boards below, since it trivially satisfies the looser cap too. Lower ancilla count is better.

## Square lattice — fewest ancillas at max weight ≤ 3

![Fewest ancillas progress at max weight 3](../assets/progress_ancillas_square_w3.png?v=e9c3936abfc3)

Best ancilla count reached so far at 15x15 under a max Pauli weight of 3, plotted against submission date -- a new point only appears if it's a strict improvement on the prior record. The dotted line is Derby-Klassen's own ancilla count at this size (arXiv 2003.06939), the construction to beat on this board.

`min n_ancillas subject to max_weight ≤ 3`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 | 11×11 | 12×12 | 13×13 | 14×14 | 15×15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **2**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **5**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **8**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **13**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **18**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **25**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **32**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **41**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **50**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **61**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **72**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **85**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **98**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |

## Square lattice — fewest ancillas at max weight ≤ 4

![Fewest ancillas progress at max weight 4](../assets/progress_ancillas_square_w4.png?v=a0a858067b77)

Best ancilla count reached so far at 15x15 under a max Pauli weight of 4, plotted against submission date -- a new point only appears if it's a strict improvement on the prior record. The dotted line is Derby-Klassen's own ancilla count at this size (arXiv 2003.06939), the construction to beat on this board.

`min n_ancillas subject to max_weight ≤ 4`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 | 11×11 | 12×12 | 13×13 | 14×14 | 15×15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **2**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **5**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **8**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **13**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **18**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **25**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **32**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **41**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **50**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **61**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **72**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **85**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) | **98**<br>[Derby-Klassen](../harness/v2/baselines/dk.py) |

