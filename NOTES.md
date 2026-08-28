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

## Second baseline: parity basis (`baselines/parity.py`)

Built via `harness/constructors.py`'s `from_linear_encoding(U)` — also
built ahead of Stage 2, since BK and ternary tree will need the same
general constructor with a different `U`. `U_parity` is lower-triangular
ones including the diagonal (the paper's own code names this `pb`, for
"parity basis" — same matrix, confirmed by feeding `from_linear_encoding`
the identity matrix and requiring it reproduce `baselines/jw.py`'s
hand-written mapping character-for-character, which only holds if the
`L` used internally (in `R = L @ F`, `P = R + F`) includes the diagonal —
PLAN.md's original eq. 18 note said "L strictly lower-triangular," which
this disproves).

The resulting structure is the expected JW dual: mode `i`'s X-support is
the shrinking suffix `{i,...,M-1}` (vs. JW's growing prefix `{0,...,i}`),
which pushes weight out of `Num` and into an X-string hopping term instead
of JW's Z-string.

Row-major, snake, and diagonal on the 3×3 grid give:

| ordering | total | max |
|---|---|---|
| row_major | 237 | 5 |
| snake | 233 | 7 |
| diagonal | 253 | 5 |

Snake beats row-major on total but loses badly on max — a real
metric-disagreeing tradeoff for this encoding, unlike JW where row-major
happened to win on both. (The `237` matching JW's *published* total is very
likely coincidence — different encoding, no mechanism connects them — not
a finding to lean on.)

**Update — exhaustively searched, via `evaluate()` (all `9!` orderings,
`verify()` included at each step, ~190s):** the true global optimum for
parity is `total=233` (achieved exactly at the `snake` permutation above,
confirmed no ordering beats it) and `max=5` (achieved exactly at
`row_major`, also confirmed optimal). So the two casual guesses above
weren't lucky — they really are each objective's true optimum, just at
*different* orderings, unlike JW where row-major is jointly optimal for
both.

**JW vs parity, both now exhaustively proven optimal, 3×3 grid:**

| | JW | parity |
|---|---|---|
| best total | **201** (row-major) | 233 (snake) |
| best max | **4** (row-major) | 5 (row-major) |

JW wins outright on both metrics at this size — consistent with the
paper's qualitative claim that JW is preferred for small grids, even
though our absolute numbers differ from theirs for the reasons documented
above.

## Third and fourth baselines: Bravyi-Kitaev and ternary tree

Both built via `harness/constructors.py`'s `from_linear_encoding(U)`, same
as parity — only `U` differs, built by `baselines/bk.py`'s Fenwick-tree
construction and `baselines/ternary.py`'s Sierpinski-tree construction
respectively (both cross-checked against arXiv 2504.21636's released code,
`hexaly_quadratic_assignment.py`'s `fenwick()`/`bk()` and
`sierpinski()`/`tt()`). Needed a new shared helper,
`harness/constructors.py`'s `transitive_closure(u)` (vectorized
Floyd-Warshall-style relaxation, `k` outermost) — verified against a plain
triple-loop on a random test matrix before trusting it.

Both pass `verify()` across a broad range of `M` (including non-power-of-two
and non-power-of-three sizes, since both constructions pad internally), and
both degenerate to exactly JW's mapping at `M=1`, as expected.

**BK's number-term weight has a clean closed form at exact powers of two**:
`ceil(log2(M)) + 1`, matching a perfectly balanced Fenwick tree's height —
verified exactly at `M = 1, 2, 4, 8, 16, 32, 64, 128`, and confirmed as a
valid upper bound at every non-power-of-two `M` tested (padding can only
shrink a mode's ancestor count relative to the fully-padded tree, never
grow it). Ternary tree does *not* have an equally clean closed form — its
recursion is asymmetric (the middle third's own children aren't wired
directly to the outer thirds, only through the middle's own representative
node), so its number-term weight grows log-like but not exactly
`ceil(log3(M)) + 1`; a generous `2*ceil(log2(M)) + 2` envelope holds at
every size checked (`tests/test_ternary.py`'s
`test_num_weight_grows_log_like`).

### Comparison against Table I (row_major/snake/diagonal, best-of-3)

```
bk total:       244, 531, 971, 1542, 2235, 3087, 4095, 5213, 6501, 7978, 9594, 11289, 13226
paper BK total: 304, 635, 1107, 1712, 2473, 3331, 4467, 5741, 7127, 8850, 10438, 12595, 14522
bk max:         5, 7, 9, 9, 11, 11, 12, 13, 13, 13, 14, 15, 15
paper BK max:   5, 7, 9, 9, 11, 11, 12, 13, 13, 13, 14, 15, 15

ternary total:       257, 532, 938, 1476, 2107, 2873, 3849, 4835, 5947, 7358, 8743, 10240, 12020
paper TT total:      313, 628, 1080, 1676, 2375, 3237, 4303, 5473, 6799, 8342, 9853, 11844, 13942
ternary max:         6, 6, 8, 10, 8, 9, 12, 10, 10, 12, 11, 11, 14
paper TT max:        5, 5, 7, 7, 8, 8, 9, 9, 9, 10, 10, 10, 11
```

BK's max weight matches published **exactly at every single size** (13/13)
and beats published total everywhere — as strong a confirmation as JW got.

TT's max weight, unlike every other encoding checked so far, is *worse*
than published at every size. Before trusting this, ran the same check
used to validate JW/parity at `3×3`: an exhaustive search over all `9!`
orderings, `verify()` included at every step.

```
true best total (3x3): 245, at permutation (0, 1, 2, 3, 6, 7, 4, 5, 8)
true best max   (3x3): 5,   at the same permutation
paper TT (3x3):        total=313, max=5
```

The true global optimum matches the paper's published max exactly (`5`)
and beats its total (`245` vs `313`) — same pattern as every other
encoding. So the earlier "worse at every size" result was an artifact of
`row_major`/`snake`/`diagonal` being poorly suited to a genuinely
tree-structured encoding (they were designed with linear-chain adjacency
in mind, which is the right fit for JW/BK/PB's cost structure but not for
TT's recursive-partition structure) — not a construction bug. TT is
correct; its max-weight numbers on the leaderboard, unlike the other three
encodings', likely have room to improve with a better-chosen ordering
(the leaderboard's own preamble already flags this as a general caveat of
the three-orderings-only methodology).
