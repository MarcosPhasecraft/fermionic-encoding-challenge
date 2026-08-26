# Investigation notes

Findings from validating the harness against arXiv 2504.21636 (Chiew,
Ibrahim, Safro, Strelchuk) — kept here, separate from `PLAN.md`, so the plan
stays a plan and this stays free to grow. `PLAN.md` points here where
relevant; durable modeling rules that came out of this are in `CLAUDE.md`'s
traps list, not repeated here.

## Table I reproduction (PLAN.md §1.6/1.7 Test 4)

Two real bugs were found and fixed in `harness/lattice.py`'s `hamiltonian()`
while trying to reproduce Table I for Jordan–Wigner on a 3×3 grid:

1. **Interaction term was incomplete.** `n_i n_j` expands to `(1/4)(I +
   i·G_i + i·G_j − G_i·G_j)` with `G_i = γ_iγ̄_i` — three nontrivial Pauli
   terms, not just the quartic product `G_i·G_j`. We were only emitting the
   quartic one. Found by inspecting the paper's released code
   (`hexaly_quadratic_assignment.py`'s `map_cost`, whose `Rep` term is
   literally `weight(F_r) + weight(F_c) + weight(F_r xor F_c)`).
2. **Hopping term was real-coefficient-only.** eq. 10's hopping term
   `c_ij A_i^dag A_j + c_ij^* A_j^dag A_i` needs a genuinely complex `c_ij`
   in general — Hermiticity forces `Num`'s and the interaction term's
   coefficients real (`A_i^dag A_i` and `A_i^dag A_i A_j^dag A_j` are each
   already Hermitian on their own), but hopping's `A_i^dag A_j` alone isn't,
   so `c_ij` is free to be complex. That's 4 Pauli terms per edge (`ReHop`'s
   two, `ImHop`'s two), not 2. We were only building the 2 real-part ones.

Both are fixed; `hamiltonian(..., model="full")` + `score_majorana` now
reproduce the paper's exact equations below, straight from committed code.

### The verified formula

Pulled from the arXiv LaTeX source directly (not prose, not their code):

```
Num_i := ||F_i||_0
ReHop_ij := ||max(P_i+R_j, U_i+U_j)||_0 + ||max(R_i+P_j, U_i+U_j)||_0
ImHop_ij := ||max(P_i+P_j, U_i+U_j)||_0 + ||max(R_i+R_j, U_i+U_j)||_0
Inter_ij := ||F_i||_0 + ||F_j||_0 + ||F_i+F_j||_0
Total    = (Sum_edges [ReHop_ij + ImHop_ij + Inter_ij]) + (Sum_vertices Num_i)
```

(The paper's `⊕` means `+` for total, `max` for maximum weight — same
nested structure either way, so nothing here needs a separate "max mode.")

Their own released code's `Cre`/`Ciu` (in `map_cost`) do **not** actually
match these published equations — it double-counts one hopping bilinear and
drops another. For JW this happens not to matter (all four raw bilinear
weights per edge are numerically equal, a JW-specific symmetry), so the
buggy code grouping and the correct paper grouping sum to the same number.
Don't assume that symmetry holds once BK/parity/ternary tree are added.

### Closed form for JW under row-major

Every JW hopping bilinear between mode-index-separated-by-`d` positions has
weight `d+1` (all four of them, same symmetry as above); the quartic
interaction piece is always weight `2`, independent of `d`; `Num_i` is
always weight `1`. This gives:

```
Total = |V| + 4*Sigma_d + 8*|E|      (Sigma_d = sum over edges of |i - j|)
```

verified to reproduce the code's actual output exactly (`201, 448, 825,
4113` for `L=3,4,5,9`). Total is strictly increasing in `Sigma_d`, so
minimizing Total is exactly equivalent to minimizing `Sigma_d`.

### Comparison against Table I

Row-major throughout, via `hamiltonian(model="full")` + `score_majorana`:

| L | row-major total | published total | diff | row-major max | published max | diff |
|---|---|---|---|---|---|---|
| 3 | 201 | 237 | −36 | 4 | 4 | 0 |
| 4 | 448 | 512 | −64 | 5 | 5 | 0 |
| 5 | 825 | 909 | −84 | 6 | 6 | 0 |
| 6 | 1356 | 1460 | −104 | 7 | 7 | 0 |
| 7 | 2065 | 2189 | −124 | 8 | 8 | 0 |
| 8 | 2976 | 3104 | −128 | 9 | 9 | 0 |
| 9 | 4113 | 4277 | −164 | 10 | 11 | −1 |
| 10 | 5500 | 5632 | −132 | 11 | 12 | −1 |
| 11 | 7161 | 7389 | −228 | 12 | 14 | −2 |
| 12 | 9120 | 9320 | −200 | 13 | 15 | −2 |
| 13 | 11401 | 11609 | −208 | 14 | 16 | −2 |
| 14 | 14028 | 14364 | −336 | 15 | 18 | −3 |
| 15 | 17025 | 17601 | −576 | 16 | 20 | −4 |

**Max weight**: matches published exactly for `L=3..8` — explained by the
closed form (`L+1`) — then *beats* published from `L=9` on. Consistent with
their solver (30s time limit per instance, from their own code) failing to
find the true optimum as the search space grows.

**Total weight**: beats published at every size, gap growing with `L`.
Verified two independent ways for `3×3`: exhaustive search over all `9!`
orderings (true global minimum is `201`/`4`; `237` needs `Sigma_d=33`,
provably worse than the achievable `Sigma_d=24`), and the closed form
above. Also ruled out for `3×3`: periodic boundary conditions (worse,
`345`, still row-major-optimal), king-graph/diagonal connectivity (breaks
max immediately, `5` not `4`), optimizing hopping-cost alone before scoring
the full total (same row-major ordering, no change). For `4×4`, ran 30
independent 2-opt local searches (steepest descent + 15 random restarts,
both objectives) — none beat row-major's `(448, 5)`.

**Likely explanation for the total-weight gap**: their own QAP optimization
(`hexaly_qap`, from their released code) minimizes `B = Cre + Ciu` only —
hopping cost alone, excluding `Num`/`Inter` from the search objective (see
`test_weights()` in `hexaly_quadratic_assignment.py`) — so the paper likely
reports the full formula evaluated at an ordering optimized for a narrower
proxy, not the true joint optimum. Tested this for `3×3` (found the
hopping-only-optimal ordering, evaluated the full formula there) — it
happened to coincide with row-major for that one small case, so the number
didn't move, but larger `L` need not have that coincidence.

**Bottom line**: max Pauli weight is about as validated as possible short
of running their actual solver. Total Pauli weight is provably not worse
than published anywhere checked, and the evidence points to their published
total reflecting solver-search limitations rather than a provable optimum.
Treat our own numbers as the more trustworthy reference. `score_paper` as a
separate function was judged unnecessary — `score_majorana` +
`hamiltonian(model="full")` already reproduce their exact convention.

Also checked and ruled out as the source of Table I: the two Mathematica
notebooks in their GitHub repo (`adjacency matrices for cameron.nb`,
`_2.nb`) — both are about hexagonal/triangular lattices, unrelated to the
square-grid benchmark.

## Ordering sensitivity (Test 3): row-major beats snake

Found by direct computation, not derived in advance: it's `row_major`, not
`snake`, that gives every vertical hop weight exactly `Lx+1` — provably,
since `index(x,y+1) - index(x,y) = Lx` for every site under row-major.
Standard boustrophedon `snake` does *not* reduce max weight relative to
row-major — it only removes the row-wrap horizontal jump. Interior vertical
hops under snake range from weight `2` (at the column where the row
reverses) up to weight `2*Lx` (at the column farthest from it) — worse in
the worst case than row-major's uniform `Lx+1`. Whether snake still wins on
*total* weight (many low-weight edges against row-major's uniformly medium
ones) is a separate question, not checked.

## Corrections made to earlier docs

- `CONTEXT.md` originally described the Fermi–Hubbard metric as "real
  coefficients and no interaction terms" — backwards. Verified against the
  LaTeX source: `Fermi–Hubbard: D = ReHop + Inter` — it *includes* the
  interaction term, and excludes `Num` and `ImHop`. The paper's caption
  phrase "no operator terms" most likely means "no [number] operator
  terms" (`c_i = 0`), not "no interaction terms."
- `PLAN.md` §1.6 originally flagged `total = 4*Sigma_d + 8*|E| + M` as a
  failed reconstruction attempt ("must be wrong somewhere"). It wasn't
  wrong — see the closed form above. The premise that `237` was the
  achievable optimum was the actual error.

## `evaluate()` built ahead of Stage 2

`harness/evaluate.py`'s `evaluate(spec, encode_fn, terms)` was built during
Stage 1, not held for Stage 2 — nothing about it requires an untrusted
`encode_fn`, and every comparison above was, until it existed, this exact
chain hand-rolled inline in ad hoc scripts. `tests/test_evaluate.py`
confirms it reproduces the verified JW numbers and gates scoring on a
failed `verify()`.
