![Total Pauli weight progress, Tri-Lattice](../assets/progress_triangular_weight.png?v=a2c2ad3e5f1d)

Best total Pauli weight reached so far on the Tri-Lattice at 8x8 (arXiv 2504.21636's own Table II comparison point), plotted against submission date -- shown for Tri-Lattice only since it's the one graph type whose paper-comparison shape is itself Lx=Ly (Hex-Lattice's is not -- see NOTES.md). Dashed lines are the JW reference and the better of Table II's own two Tri-Lattice numbers (JW, TT). See the full tables below for the complete picture across both graph types and every swept size.

## Tri-Lattice — Total Pauli weight

`D = Num + ReHop + ImHop + Inter`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 |
|---|---|---|---|---|---|---|
| 1 | **257**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **586**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **1059**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **1730**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **2572**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **2384**<br>JW [[1]](#references) |
| 2 | **297**<br>[JW](../baselines/jw_triangular.py) | **700**<br>[JW](../baselines/jw_triangular.py) | **1337**<br>[JW](../baselines/jw_triangular.py) | **2256**<br>[JW](../baselines/jw_triangular.py) | **3363**<br>[TT](../baselines/tt_triangular.py) | **2478**<br>TT [[1]](#references) |
| 3 | **369**<br>[TT](../baselines/tt_triangular.py) | **806**<br>[TT](../baselines/tt_triangular.py) | **1474**<br>[TT](../baselines/tt_triangular.py) | **2342**<br>[TT](../baselines/tt_triangular.py) | **3505**<br>[JW](../baselines/jw_triangular.py) | **3569**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) |
| 4 |  |  |  |  |  | **4613**<br>[TT](../baselines/tt_triangular.py) |
| 5 |  |  |  |  |  | **5132**<br>[JW](../baselines/jw_triangular.py) |

## Tri-Lattice — Maximum Pauli weight

`D = max(Num, ReHop, ImHop, Inter)`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 |
|---|---|---|---|---|---|---|
| 1 | **4**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **6**<br>[JW](../baselines/jw_triangular.py)<br>[TT](../baselines/tt_triangular.py)<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **7**<br>[JW](../baselines/jw_triangular.py) | **8**<br>[JW](../baselines/jw_triangular.py) | **8**<br>[TT](../baselines/tt_triangular.py) | **10**<br>[JW](../baselines/jw_triangular.py) |
| 2 | **5**<br>[JW](../baselines/jw_triangular.py) |  | **8**<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **10**<br>[TT](../baselines/tt_triangular.py)<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **9**<br>[JW](../baselines/jw_triangular.py)<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) | **11**<br>[TT](../baselines/tt_triangular.py)<br>[Triangular axial multistart (deep Clifford refined)](../baselines/triangular_axial_deep_refine.py) |
| 3 | **6**<br>[TT](../baselines/tt_triangular.py) |  | **10**<br>[TT](../baselines/tt_triangular.py) |  |  |  |

## Hex-Lattice — Total Pauli weight

`D = Num + ReHop + ImHop + Inter`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 |
|---|---|---|---|---|---|---|
| 1 | **366**<br>[JW](../baselines/jw_hexagonal.py) | **800**<br>[JW](../baselines/jw_hexagonal.py) | **1470**<br>[JW](../baselines/jw_hexagonal.py) | **2415**<br>[TT](../baselines/tt_hexagonal.py) | **3456**<br>[TT](../baselines/tt_hexagonal.py) | **4614**<br>[TT](../baselines/tt_hexagonal.py) |
| 2 | **467**<br>[TT](../baselines/tt_hexagonal.py) | **944**<br>[TT](../baselines/tt_hexagonal.py) | **1587**<br>[TT](../baselines/tt_hexagonal.py) | **2424**<br>[JW](../baselines/jw_hexagonal.py) | **3710**<br>[JW](../baselines/jw_hexagonal.py) | **5376**<br>[JW](../baselines/jw_hexagonal.py) |

## Hex-Lattice — Maximum Pauli weight

`D = max(Num, ReHop, ImHop, Inter)`

| rank | 3×3 | 4×4 | 5×5 | 6×6 | 7×7 | 8×8 |
|---|---|---|---|---|---|---|
| 1 | **6**<br>[JW](../baselines/jw_hexagonal.py)<br>[TT](../baselines/tt_hexagonal.py) | **8**<br>[JW](../baselines/jw_hexagonal.py)<br>[TT](../baselines/tt_hexagonal.py) | **10**<br>[JW](../baselines/jw_hexagonal.py) | **10**<br>[TT](../baselines/tt_hexagonal.py) | **10**<br>[TT](../baselines/tt_hexagonal.py) | **12**<br>[TT](../baselines/tt_hexagonal.py) |
| 2 |  |  | **11**<br>[TT](../baselines/tt_hexagonal.py) | **12**<br>[JW](../baselines/jw_hexagonal.py) | **14**<br>[JW](../baselines/jw_hexagonal.py) | **16**<br>[JW](../baselines/jw_hexagonal.py) |

## References

[1] Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings via quadratic assignment*, [arXiv 2504.21636](https://arxiv.org/abs/2504.21636), Table II.
