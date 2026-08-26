# Implementation plan

Read `CONTEXT.md` first for the problem and its background.

We build in stages and **verify each stage before starting the next**. Do not
skip ahead. Stage 1 has no agent, no generator, and no optimization — it exists
solely to produce a verifier and scorer we can trust.

## Strategy

The end goal is a harness where **an agent submits a program** that generates a
fermion-to-qubit encoding, and frozen code verifies and scores it.

We get there in two stages:

- **Stage 1** validates the *referee* — the verifier and scorer — against known
  answers, using reference encodings we already trust. No agent, no
  optimization.
- **Stage 2** swaps in an agent-written program as the thing being scored.

Splitting them this way means that if something breaks in Stage 2, it can only
be the generator's fault: the referee was already signed off against published
numbers and an analytically known case.

### Making the transition free

Three choices now make Stage 2 a file move rather than a rewrite. **Follow
them even where they seem like extra ceremony in Stage 1.**

1. **The harness never takes a program.** `verify(spec, mapping)` and
   `score(spec, mapping, terms)` are the frozen interface in *both* stages.
   Stage 2 adds one thin wrapper, `evaluate(spec, encode_fn)`, which calls
   `encode_fn(spec)` and passes the result to the unchanged functions.

2. **Baselines are written as `f(spec) -> mapping` from day one.** Nobody
   hand-types 450 Pauli strings for a 15×15 grid, so Stage 1's baselines are
   programs regardless. Give them the exact `encode()` signature and Stage 2 is
   `cp baselines/jw.py solution/encode.py`.

3. **The spec is complete.** No baseline may take extra arguments or close over
   lattice data. Signature is exactly `f(spec)`. Anything a smart encoder could
   want — `coords`, `edges`, `Lx`, `Ly` — goes in the spec now.

Raw Pauli strings remain available as a **debug path** (`run.py --mapping
file.json`) for hand-written unit tests such as the small rejection cases. The
primary path is always a function.

A consequence: the Stage 2 regression test becomes trivially true, since it is
the same code. That is the intended outcome. The real Stage 2 question is
whether a newly written `encode()` runs through an unchanged pipeline.

---

## Scope for now

- Hamiltonians **quadratic in Majorana operators** — hopping terms and number
  terms. Interaction terms (`n_i n_j`, four-Majorana products) are supported by
  the term-list machinery but off by default. See §1.3.
- **Rectangular lattices** `Lx × Ly`. A 1D chain is the special case `Ly = 1`.
- **Ancilla-free** encodings, `N = M`, no stabilizers. The data format must
  admit `N > M` and stabilizers from the start so local encodings can be added
  later without a rewrite.

---

## Stage 1 — verifier and scorer

Reference encodings are supplied as `f(spec) -> mapping` functions (see
*Strategy* above). What makes this Stage 1 rather than Stage 2 is that those
functions are **frozen reference implementations we already trust**, not
candidate submissions. Nothing is being optimized; we are validating the
referee.

### 1.1 Data format

```python
spec = {
  "name":    str,
  "Lx":      int,
  "Ly":      int,
  "M":       int,                # = Lx * Ly
  "edges":   [(i, j), ...],      # fermionic interaction graph
  "coords":  {i: (x, y), ...},   # geometry
}

mapping = {
  "n_qubits":    int,            # N; must be >= M
  "majoranas":   [str] * 2M,     # Pauli strings, length N, chars from IXYZ
  "stabilizers": [str],          # empty in Stage 1
}
```

Index convention: `majoranas[2j]` is `gamma_j = a_j + a_j†`,
`majoranas[2j+1]` is `gamma-bar_j = -i(a_j - a_j†)`.

### 1.2 Lattices and orderings

`rectangle(Lx, Ly, ordering="snake")` builds the spec. Orderings to provide:

- `row_major`
- `snake` (boustrophedon)
- `diagonal`
- arbitrary user-supplied permutation

The ordering determines the mode indices, which is the only thing that varies
in Stage 1. `Ly = 1` gives a 1D chain.

### 1.3 Hamiltonian term lists

`hamiltonian(spec, model)` returns a list of tuples of Majorana indices.
Three settings:

| model | terms |
|---|---|
| `"hopping"` | hopping only |
| `"quadratic"` | hopping + number terms — **Stage 1 default** |
| `"full"` | hopping + number + interaction (`n_i n_j`) |

`"full"` is needed to reproduce Table I's *total* Pauli weight column, which
is defined as `Num + ReHop + ImHop + Inter`. With `"quadratic"` we omit `Inter`
and the total column will not match. The *maximum* weight column is expected to
be insensitive to this for Jordan–Wigner (its interaction terms are weight 2),
but the paper notes that number and interaction terms do **not** stay local
under Bravyi–Kitaev or ternary tree, so verify rather than assume.

### 1.4 Internal representation

Symplectic. A Pauli on `N` qubits is a pair of bit vectors `(x, z)` of length
`N`. X sets `x`, Z sets `z`, Y sets both. Two Paulis anticommute iff

```
x1 . z2 + z1 . x2 = 1  (mod 2)
```

**Vectorize.** Stack the `2M` Majoranas into a `(2M) x (2N)` binary matrix `G`
with rows `[x | z]`. The full pairwise commutation table is one matrix product:

```
C = G @ Lambda @ G.T  (mod 2),    Lambda = [[0, I], [I, 0]]
```

Do not write the O(M²) Python double loop; it takes ~0.3 s at M=256 and will
starve the loop later.

**Pauli product support is XOR of the bit vectors, never OR.** Shared factors
cancel (`Z·Z = I`). Using OR makes Jordan–Wigner look far worse than it is,
because its long Z-strings largely cancel in nearest-neighbour hopping
products. This is an easy bug to introduce and it silently produces
plausible-looking wrong rankings.

### 1.5 Verifier — `harness/verify.py`

Return a structured dict. **Never raise** on malformed input.

| # | check | condition |
|---|---|---|
| 0 | well-formed | `N` a positive int; exactly `2M` strings; each of length `N`; chars in `IXYZ` |
| 1 | Majorana algebra | every distinct pair anticommutes: `C == J - I` |
| 2 | stabilizers abelian | all pairs commute |
| 3 | stabilizer compatible | for each `S`, `sym(S, gamma_j)` is **constant over j** |
| 4 | codespace dimension | `N - rank_GF2(stabilizers) == M` |

**Check 1 carries the entire correctness argument.** If the generators satisfy
the algebra, the map is an algebra homomorphism, so every product of Majoranas
maps correctly and the encoded Hamiltonian is correct automatically. The
Hamiltonian is never checked directly. This is why no simulation is needed.

**Check 3 — known trap.** The condition is *not* "S anticommutes with an even
number of gammas". That is strictly weaker and admits invalid stabilizers.
Counterexample: on `M=4` Jordan–Wigner, `S = ZZII` has signature
`[1,1,1,1,0,0,0,0]` — even sum, but `S` anticommutes with 16 even products
including the physical hopping term `gamma_0 · gamma_4`. Required condition:
the signature is constant (all 0 or all 1).

Checks 2–4 are unexercised in Stage 1 (no stabilizers). Implement and unit-test
them anyway.

**Not checked: signs and phases.** The Pauli-string format cannot express them,
so a mapping with wrong sign conventions passes silently. Note it; do not
attempt to fix it in Stage 1.

### 1.6 Scorer — `harness/score.py`

Runs only after verification passes. Implement **two independent scorers** and
keep them separate — if they disagree, that is information, not corruption.

**`score_majorana(spec, mapping, terms)`** — our own definition. For each term
(a tuple of Majorana indices), XOR the corresponding bit vectors and count the
support. Report `total_weight`, `max_weight`, `avg_weight`, `n_qubits`.

**`score_paper(spec, mapping, terms)`** — the convention of arXiv 2504.21636
§III-C, used only for Table I calibration.

> **Status update, after the eq. 10/36 investigation below: this may not
> need to be a separate function.** `score_majorana` + `hamiltonian(...,
> model="full")` already compute the paper's exact `Num+ReHop+ImHop+Inter`
> convention, verified two independent ways (exhaustive search, closed-form
> arithmetic) against their own published equations — see the long note in
> §1.7 Test 4. `score_paper` would only earn its own function if we find a
> case where the two conventions genuinely diverge; so far, for JW, they
> don't. Revisit if/when other encodings (BK, parity, TT) are added — the
> JW-specific symmetry that made several groupings numerically equivalent
> (all four raw hopping bilinears per edge equal) is **not** guaranteed to
> hold for them.
>
> **A durable modeling rule worth remembering for those future encodings**:
> this convention deliberately does **not** deduplicate identical Pauli
> operators that arise from different physical term categories. E.g. the
> single-qubit `Z`-type operator from a vertex's number term recurs, with
> its own separate weight contribution, once inside every incident edge's
> interaction-term expansion (`Inter_ij` literally re-adds `Num_i` and
> `Num_j`). A vertex of degree `k` has that one operator counted `k+1`
> times, not once. That's not a bug to fix — it's what "Total Pauli weight"
> means here (a sum over Hamiltonian summands, not a minimal distinct-Pauli-
> string count) — but it would be an easy thing to "fix" by accident while
> implementing a new encoding's scoring, so don't.
>
> **Also worth remembering**: a single edge's hopping term is 2 terms at the
> *fermionic operator* level (`c_ij A_i^dag A_j + h.c.`) but decomposes into
> up to 4 distinct *Pauli-string* terms once `A_i = (gamma_i + i*gammabar_i)/2`
> is substituted in and simplified with the Majorana anticommutation
> relations (2 if `c_ij` is purely real or purely imaginary, 4 if genuinely
> complex) — not a contradiction, just two different levels of description.
> Number and interaction terms stay real-only, and need no such split: `A_i^dag
> A_i` and `A_i^dag A_i A_j^dag A_j` are each already Hermitian on their own
> (unlike `A_i^dag A_j` alone), so their coefficients are forced real by
> Hermiticity, not by convenience.

> ⚠ Do not reconstruct their cost model from the paper prose *as your only
> check* — cross-verify against the actual LaTeX source or code. Use their
> released code as an additional reference: `github.com/cameton/QCE_QubitAssignment`.
>
> **This note originally said `total = 4·Σd + 8·|E| + M` (Σd = sum of
> linear-order edge separations) must be "wrong somewhere" because it needs
> `Σd=33` for their 3×3 value of 237, while row-major gives `Σd=24`. That
> premise was backwards.** The formula is correct — independently re-derived
> from their own published equations, and it reproduces our code's actual
> output exactly (`201, 448, 825, 4113` for `L=3,4,5,9`). Since Total is
> strictly increasing in `Σd` for a fixed graph, minimizing Total is exactly
> equivalent to minimizing `Σd` — and we've *exhaustively proven* (full `9!`
> search, §1.7 investigation below) that `Σd=24` is the true global minimum
> for the `3×3` grid. `Σd=33` is achievable by *some* ordering but is
> provably not optimal. So `237` isn't a value the formula fails to reach —
> it's a value that doesn't correspond to any achievable optimum, which is a
> different and more specific claim than "the reconstruction is wrong."
>
> **Update, after actually inspecting `hexaly_quadratic_assignment.py`:** one
> real bug was found and fixed by this — our own `hamiltonian(..., model=
> "full")` was under-building the interaction term. `n_i n_j` expands to
> *three* nontrivial Pauli terms (`G_i`, `G_j`, `G_i·G_j` with `G_i = gamma_i
> gammabar_i`), not just the quartic product; we were only emitting the
> quartic one. Confirmed against their `map_cost`'s `Rep` term, which is
> literally `weight(F_r) + weight(F_c) + weight(F_r xor F_c)`. Fixed in
> `harness/lattice.py`.
>
> **Second update, after pulling the arXiv LaTeX source directly (not the
> paper prose, not their code — the actual published equations, Eq. right
> before Table I):** `Num_i := ||F_i||_0`; `ReHop_ij := ||max(P_i+R_j,
> U_i+U_j)||_0 + ||max(R_i+P_j, U_i+U_j)||_0`; `ImHop_ij` is the same with
> `(P_i+P_j)` and `(R_i+R_j)`; `Inter_ij := ||F_i||_0 + ||F_j||_0 + ||F_i +
> F_j||_0`; total = `(Σ_edges D_ij) + (Σ_vertices D_ii)` with `⊕ = +`. This
> is *exactly* what we already had (confirms the interaction-term fix above,
> and confirms `ReHop`/`ImHop` are literally the two real-part and two
> imaginary-part Majorana bilinears per edge, summed). Note: their released
> code's `Cre`/`Ciu` in `map_cost` do NOT match these published equations
> (the code double-counts one bilinear and drops another) — but for JW
> specifically this doesn't matter, because all four raw bilinear weights
> per edge are numerically equal by a JW-specific symmetry, so both the
> (buggy) code grouping and the (correct) paper grouping sum to the same
> number. Don't assume that symmetry holds for BK/parity/ternary tree.
>
> Exhaustively re-searched all `9!` orderings (not just row-major) under the
> verbatim formula above: **true global minimum is `total=201`, `max=4`,
> Fermi–Hubbard=`120`**, achieved at row-major for every variant tried.
> Paper reports `237` / `4` / `138`. Max matches exactly; total and
> Fermi–Hubbard are each short by a consistent-feeling amount (`36`, `18`,
> ratio 2) that survives every hypothesis tested and exhaustively
> re-searched for its own true optimum, not just evaluated at row-major:
> generic complex hopping coefficients (included, confirmed present in their
> model — didn't close the gap), periodic boundary conditions (18 edges
> instead of 12 — makes it worse, `345`, still row-major-optimal), and
> optimizing for hopping-cost alone before evaluating the full total (lands
> on the same row-major ordering, no change). Also checked both linked
> Mathematica notebooks in their repo — both are about hexagonal/triangular
> lattices, unrelated to the square-grid benchmark.
>
> **Third update — checked row-major against the FULL table, all 13 grid
> sizes (`L=3..15`), not just `3×3`. This is close to conclusive.**
>
> Max Pauli weight: row-major exactly matches the published JW column for
> **eight straight sizes, `L=3` through `L=8`** (`4,5,6,7,8,9`). From `L=9`
> on, row-major's max is *lower* (better) than published — by `1,1,2,2,2,3,4`
> as `L` goes `9..15`. A closed form explains why: row-major puts every
> vertical hop exactly `L` apart in linear order, so its max weight is
> provably `L+1` for any `L` — no search needed, and it matches published
> values exactly wherever the true optimum apparently *is* `L+1` (small `L`),
> then beats published values once their solver (30s time limit per
> instance, from their own code) stops finding it (large `L`).
>
> Total Pauli weight: row-major beats the published JW column at **every one
> of the 13 sizes**, gap growing from `-36` at `L=3` up to `-576` at `L=15`
> — using the exact formula pulled from their LaTeX source (not a guess).
> This is the more surprising one: at `L=3` (`9!` possibilities, trivial for
> any solver) there's no plausible search-difficulty excuse, yet row-major
> already beats their reported "optimized" number by `36`.
>
> **Reading of the evidence:** max weight is now about as validated as
> possible short of literally running their solver — an exact analytic
> formula, matching 8 independent published values, degrading exactly where
> a time-limited heuristic would be expected to degrade. For total weight,
> the likely explanation is that their own QAP optimization (`hexaly_qap` in
> their released code) minimizes `B = Cre + Ciu` only — hopping cost alone,
> literally excluding `Op` (Num) and `Rep` (Inter) from the search objective,
> per `test_weights()` in `hexaly_quadratic_assignment.py` — then the paper
> likely reports the full formula evaluated at whatever ordering that
> incomplete objective converged to, not the ordering that truly minimizes
> the full total. We tested this exact idea for `3×3` (finding the
> hopping-only-optimal ordering, then evaluating the full formula there) and
> it happened to land on row-major too for that one small case, so it didn't
> move the number there — but for larger `L`, hopping-only-optimal and
> jointly-optimal orderings need not coincide, which would explain a gap
> that *grows* with `L` and is nonzero even at `L=3` if their solver's found
> ordering for `L=3` wasn't literally row-major to begin with.
>
> **Conclusion for now: treat the published total-weight numbers as likely
> reflecting their solver's search, not a provable global optimum** — our
> own numbers (verified against their exact equations, and exhaustively
> optimal at `3×3`) are the more trustworthy reference going forward. Max
> weight is fully validated. Revisit only if their actual solver output
> becomes available; don't keep reconstructing from prose or code.
>
> **Fourth update — the `ImHop` bilinears are now in `harness/lattice.py`
> itself, not stranded in a scratch script.** eq. 10's hopping term
> `c_ij A_i^dag A_j + c_ij^* A_j^dag A_i` genuinely needs a complex `c_ij` —
> unlike `Num`/interaction, whose own single-term Hermiticity forces their
> coefficients real, so those needed no split. `hamiltonian()`'s edge loop
> now emits all four bilinears per edge (`ReHop`'s two, `ImHop`'s two); the
> `3×3` total from `score_majorana` is now directly `201`/`4`, matching
> every number in the investigation above, straight from committed code.

Never combine metrics into a single product such as `N × weight`. It asserts an
invented qubit-vs-weight exchange rate, and it would penalize the ancilla
trade-off we may want later. Report a vector of metrics; rank by one component.

### 1.7 Tests — run in this order

**Test 1 — analytic 1D chain. Depends on no external source.**

Jordan–Wigner on `Lx = L, Ly = 1` for `L = 4, 16, 64`. Every nearest-neighbour
hopping term must have Pauli weight **exactly 2** — the Z-strings cancel. Hence
`max_weight == 2` independent of `L`.

This validates the symplectic machinery against a result we can derive by hand.
If it fails, nothing downstream is meaningful. Run it first.

**Test 2 — rejection.**

The verifier must reject, gracefully and with informative output:

- a corrupted Majorana string (e.g. drop a Z prefix) → check 1 fails with a
  specific violation count and an example pair
- too few qubits for the mode count → checks 1 *and* 4 both fail
- malformed input: wrong number of strings, wrong length, illegal characters
- the `S = ZZII` stabilizer from §1.5 → check 3 fails

**Test 3 — ordering sensitivity.**

Jordan–Wigner on rectangular grids under `row_major`, `snake`, and `diagonal`.
Max weight should track the ordering in a way we can predict analytically.
Sanity check, not calibration.

**Correction (found by direct computation, not derived in advance — see
`harness/lattice.py`):** it is `row_major`, not `snake`, that gives every
vertical hop weight exactly `Lx + 1`, provably: `index(x, y+1) - index(x, y)
= Lx` for every site under row-major, so all vertical hops are equally
separated in the linear order. Standard boustrophedon `snake` does *not*
reduce max weight relative to row-major — it only removes the row-wrap
horizontal jump. Interior vertical hops under snake range from weight 2 (at
the column where the row reverses) up to weight `2·Lx` (at the column
farthest from it), which is worse in the worst case than row-major's uniform
`Lx + 1`. Whether snake still wins on *total* weight (many low-weight edges
against row-major's uniformly medium ones) is a separate question, not yet
checked.

**Test 4 — Table I reproduction. This is the gate.**

Feed Jordan–Wigner, parity, Bravyi–Kitaev and ternary tree, under optimized
orderings, on square grids from 3×3 to 15×15. Compare against Table I of
arXiv 2504.21636 across the available metrics. Use `model="full"` for the total
columns.

Their orderings come from a commercial solver, so exact ties are not required.
**What must reproduce is the crossover structure:**

| metric | JW wins up to | crossover | TT wins from |
|---|---|---|---|
| maximum Pauli weight | 5×5 (ties 6×6–7×7) | **8×8** | 8×8 |
| total Pauli weight | 9×9 | **10×10** | 10×10 |
| Fermi–Hubbard total | 10×10 | **11×11** | 11×11 |

Re-pull the paper and check the target numbers against the source before
treating them as ground truth.

**Stage 1 is complete when Tests 1–4 pass.** Report results and stop.

---

## Stage 2 — an agent-written program becomes the submission

Do not begin until Stage 1 is signed off.

> **Built early**: `harness/evaluate.py`'s `evaluate(spec, encode_fn, terms)`
> already exists, ahead of Stage 2. Nothing about it requires an untrusted
> `encode_fn` — every Table I comparison in §1.7 Test 4 was, until now, this
> exact chain hand-rolled inline in ad hoc scripts; formalizing it just means
> future baselines (and eventually submissions) call one named function
> instead of re-deriving the chain each time. `tests/test_evaluate.py`
> confirms it reproduces the verified JW numbers (`total=201, max=4` for
> `3×3` row-major) and that it gates scoring on a failed `verify()` even for
> a locally-broken encode_fn.

Nothing in `harness/` changes. Add one wrapper:

```python
def evaluate(spec, encode_fn, terms):
    mapping = encode_fn(spec)
    v = verify(spec, mapping)
    return v if not v["passed"] else {**v, **score(spec, mapping, terms)}
```

The submission is now `solution/encode.py`, containing one function with the
same signature the baselines already use:

```python
def encode(spec) -> mapping
```

That file is what is version-controlled, diffed, reviewed and improved. A good
submission reads as *ideas* — "build a ternary tree", "order modes by lattice
distance" — which is what makes improvements composable across submissions and
legible to a human reader.

A raw mapping would be the wrong artifact for a submission: it is an
*instance*. It contains no ideas to improve, two good mappings cannot be
meaningfully diffed, almost every local edit breaks validity, and nothing
transfers between sizes.

`encode` must be **one uniform rule**: no branching on `spec["M"]`, `Lx` or
`Ly`, and no size-keyed lookup tables. Enforcement is by held-out sizes, not by
inspection.

### Stage 2 test

`cp baselines/jw.py solution/encode.py` and confirm the scores are **identical**
to Stage 1. Because it is the same code, this should pass trivially — that is
the point of the choices in *Strategy*. If it does not pass, something leaked
outside the `f(spec)` contract.

The substantive test is the next one: write a *new* `encode()` from scratch —
say ternary tree, without copying `baselines/ternary.py` — and confirm it runs
through the unchanged pipeline and matches the known ternary-tree scores.

### Frozen helpers — `harness/constructors.py`

Importable by `solution/`, so the generator can work in a convenient
parameterization and hand back canonical form:

- `from_linear_encoding(U)` — `U` invertible over `F_2`.
  `gamma_i -> X_{U(i)} Z_{P(i)}`, `gamma-bar_i -> X_{U(i)} Z_{R(i)}`, where
  `F = U^-1`, `P = LF` (`L` strictly lower-triangular ones), `R = P + F`.
  Reference: arXiv 2504.21636 eq. (18).
- `from_ternary_tree(tree)` — Pauli labels along root-to-leaf paths.
- `apply_clifford(mapping, ops)` — Clifford conjugation preserves the Majorana
  algebra, so any conjugated valid mapping is valid by construction.
- `permute_modes(mapping, sigma)`.

Note that a mode reordering is a permutation matrix, hence a special linear
encoding — ordering is therefore already inside the submission space and needs
no separate handling.

---

## Layout

```
encoding-bench/
  CONTEXT.md              problem and background
  PLAN.md                 this file
  README.md               the contract (write in Stage 2)
  run.py                  entry point
  results.tsv             append-only log
  harness/                FROZEN
    paulis.py             symplectic representation, vectorized
    lattice.py            rectangle(), orderings, Hamiltonian term lists
    verify.py             the five checks
    score.py              score_majorana + score_paper
    constructors.py       Stage 2 helpers
  baselines/              FROZEN
    jw.py  parity.py  bk.py  ternary.py
  tests/
    test_chain_analytic.py
    test_rejection.py
    test_ordering.py
    test_table1.py
  solution/               EDITABLE — Stage 2 only
    encode.py
    memory/
```

Python. Dependencies: `numpy`; `openfermion` for differential testing later.

---

## Deferred, deliberately

- **Ancillas and stabilizers.** The format supports them; nothing uses them.
  When enabled, switch to constrained scoring — minimize weight subject to
  `N <= budget` — because a product metric would penalize the very move being
  sought.
- **Sign and convention closure.** Add a small-`M` spectrum check: build the
  encoded Hamiltonian densely at `M <= 8`, diagonalize, compare to direct
  diagonalization of the fermionic Hamiltonian. Also differential-test the
  term-list construction against `openfermion.jordan_wigner`.
- **Gate depth and compilation cost.** Named as future work in 2504.21636 and
  not attempted by anyone. Needs a frozen compiler and a hardware coupling
  graph.
- **Held-out instance sets and worst-case scoring.** Needed once a generator is
  actually being optimized, not before.

---

## Traps

1. **OR vs XOR** in Pauli products (§1.4). Produces plausible wrong rankings.
2. **Check 3's even-sum condition is wrong** (§1.5); must be
   constant-signature.
3. **1D chains contain no search.** Jordan–Wigner gives hopping weight 2, the
   floor for a two-mode operator. Useful as a unit test, not as a benchmark.
4. **Do not reconstruct the paper's cost model from prose** (§1.6). Use their
   code.
5. **Published baselines are heuristic** except where they match analytic
   results. "Beating" a Table I entry may mean beating a solver run rather than
   a bound.
6. **Evaluation speed is the binding constraint** in later stages, not
   cleverness. Vectorize now.
