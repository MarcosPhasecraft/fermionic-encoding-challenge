![Total Pauli weight progress, Tri-Lattice](../assets/progress_triangular_weight.png?v=b40761f3b13c)

Best total Pauli weight reached so far on the Tri-Lattice at 8x8 (arXiv 2504.21636's own Table II comparison point), plotted against submission date -- shown for Tri-Lattice only since it's the one graph type whose paper-comparison shape is itself Lx=Ly (Hex-Lattice's is not -- see NOTES.md). Dashed lines are the JW reference and the better of Table II's own two Tri-Lattice numbers (JW, TT). See the full tables below for the complete picture across both graph types and every swept size.

## Tri-Lattice — Total Pauli weight

`D = Num + ReHop + ImHop + Inter`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 | 11×11 | 12×12 | 13×13 | 14×14 | 15×15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **297**<br>[JW](../baselines/jw_triangular.py) | **700**<br>[JW](../baselines/jw_triangular.py) | **1337**<br>[JW](../baselines/jw_triangular.py) | **2256**<br>[JW](../baselines/jw_triangular.py) | **3363**<br>[TT](../baselines/tt_triangular.py) | **2384**<br>JW [[1]](#references) | **6089**<br>[TT](../baselines/tt_triangular.py) | **7921**<br>[TT](../baselines/tt_triangular.py) | **9879**<br>[TT](../baselines/tt_triangular.py) | **12278**<br>[TT](../baselines/tt_triangular.py) | **14731**<br>[TT](../baselines/tt_triangular.py) | **17350**<br>[TT](../baselines/tt_triangular.py) | **20376**<br>[TT](../baselines/tt_triangular.py) |
| 2 | **369**<br>[TT](../baselines/tt_triangular.py) | **806**<br>[TT](../baselines/tt_triangular.py) | **1474**<br>[TT](../baselines/tt_triangular.py) | **2342**<br>[TT](../baselines/tt_triangular.py) | **3505**<br>[JW](../baselines/jw_triangular.py) | **2478**<br>TT [[1]](#references) | **7185**<br>[JW](../baselines/jw_triangular.py) | **9712**<br>[JW](../baselines/jw_triangular.py) | **12761**<br>[JW](../baselines/jw_triangular.py) | **16380**<br>[JW](../baselines/jw_triangular.py) | **20617**<br>[JW](../baselines/jw_triangular.py) | **25520**<br>[JW](../baselines/jw_triangular.py) | **31137**<br>[JW](../baselines/jw_triangular.py) |
| 3 |  |  |  |  |  | **4613**<br>[TT](../baselines/tt_triangular.py) |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  | **5132**<br>[JW](../baselines/jw_triangular.py) |  |  |  |  |  |  |  |

## Tri-Lattice — Maximum Pauli weight

`D = max(Num, ReHop, ImHop, Inter)`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 | 11×11 | 12×12 | 13×13 | 14×14 | 15×15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **5**<br>[JW](../baselines/jw_triangular.py) | **6**<br>[JW](../baselines/jw_triangular.py)<br>[TT](../baselines/tt_triangular.py) | **7**<br>[JW](../baselines/jw_triangular.py) | **8**<br>[JW](../baselines/jw_triangular.py) | **8**<br>[TT](../baselines/tt_triangular.py) | **10**<br>[JW](../baselines/jw_triangular.py) | **11**<br>[JW](../baselines/jw_triangular.py) | **10**<br>[TT](../baselines/tt_triangular.py) | **12**<br>[TT](../baselines/tt_triangular.py) | **12**<br>[TT](../baselines/tt_triangular.py) | **11**<br>[TT](../baselines/tt_triangular.py) | **13**<br>[TT](../baselines/tt_triangular.py) | **14**<br>[TT](../baselines/tt_triangular.py) |
| 2 | **6**<br>[TT](../baselines/tt_triangular.py) |  | **10**<br>[TT](../baselines/tt_triangular.py) | **10**<br>[TT](../baselines/tt_triangular.py) | **9**<br>[JW](../baselines/jw_triangular.py) | **11**<br>[TT](../baselines/tt_triangular.py) | **12**<br>[TT](../baselines/tt_triangular.py) | **12**<br>[JW](../baselines/jw_triangular.py) | **13**<br>[JW](../baselines/jw_triangular.py) | **14**<br>[JW](../baselines/jw_triangular.py) | **15**<br>[JW](../baselines/jw_triangular.py) | **16**<br>[JW](../baselines/jw_triangular.py) | **17**<br>[JW](../baselines/jw_triangular.py) |

## Hex-Lattice — Total Pauli weight

`D = Num + ReHop + ImHop + Inter`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 |
|---|---|---|---|---|---|---|---|---|
| 1 | **366**<br>[JW](../baselines/jw_hexagonal.py) | **800**<br>[JW](../baselines/jw_hexagonal.py) | **1470**<br>[JW](../baselines/jw_hexagonal.py) | **2415**<br>[TT](../baselines/tt_hexagonal.py) | **3456**<br>[TT](../baselines/tt_hexagonal.py) | **4614**<br>[TT](../baselines/tt_hexagonal.py) | **5911**<br>[TT](../baselines/tt_hexagonal.py) | **7470**<br>[TT](../baselines/tt_hexagonal.py) |
| 2 | **467**<br>[TT](../baselines/tt_hexagonal.py) | **944**<br>[TT](../baselines/tt_hexagonal.py) | **1587**<br>[TT](../baselines/tt_hexagonal.py) | **2424**<br>[JW](../baselines/jw_hexagonal.py) | **3710**<br>[JW](../baselines/jw_hexagonal.py) | **5376**<br>[JW](../baselines/jw_hexagonal.py) | **7470**<br>[JW](../baselines/jw_hexagonal.py) | **10040**<br>[JW](../baselines/jw_hexagonal.py) |

## Hex-Lattice — Maximum Pauli weight

`D = max(Num, ReHop, ImHop, Inter)`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 | 9×9 | 10×10 |
|---|---|---|---|---|---|---|---|---|
| 1 | **6**<br>[JW](../baselines/jw_hexagonal.py)<br>[TT](../baselines/tt_hexagonal.py) | **8**<br>[JW](../baselines/jw_hexagonal.py)<br>[TT](../baselines/tt_hexagonal.py) | **10**<br>[JW](../baselines/jw_hexagonal.py) | **10**<br>[TT](../baselines/tt_hexagonal.py) | **10**<br>[TT](../baselines/tt_hexagonal.py) | **12**<br>[TT](../baselines/tt_hexagonal.py) | **11**<br>[TT](../baselines/tt_hexagonal.py) | **11**<br>[TT](../baselines/tt_hexagonal.py) |
| 2 |  |  | **11**<br>[TT](../baselines/tt_hexagonal.py) | **12**<br>[JW](../baselines/jw_hexagonal.py) | **14**<br>[JW](../baselines/jw_hexagonal.py) | **16**<br>[JW](../baselines/jw_hexagonal.py) | **18**<br>[JW](../baselines/jw_hexagonal.py) | **20**<br>[JW](../baselines/jw_hexagonal.py) |

## References

[1] Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings via quadratic assignment*, [arXiv 2504.21636](https://arxiv.org/abs/2504.21636), Table II.
