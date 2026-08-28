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

Raw Pauli strings remain available as a **debug path** (`run.py verify
--spec spec.json --mapping mapping.json`) for hand-written unit tests such
as the small rejection cases. The primary path is always a function
(`run.py evaluate --solution encode.py --lx ... --ly ...`, built ahead of
schedule — see `NOTES.md`).

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

Turned out not to be needed as a separate function: `score_majorana` +
`hamiltonian(..., model="full")` already reproduce this convention exactly,
verified against the paper's own published equations. See `NOTES.md` for
the full investigation (two real bugs were found and fixed in
`hamiltonian()` along the way) and `CLAUDE.md`'s traps for the durable
modeling rules that came out of it.

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

Row-major, not snake, turns out to be the ordering with the clean closed
form (`max weight = Lx + 1`, provably) — see `NOTES.md` for the derivation
and why standard boustrophedon snake doesn't actually help here.

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

**Progress so far**: all four baselines (JW, parity, BK, ternary tree) are
now built; see `NOTES.md` for the full comparison against published Table I
across all 13 sizes for each. Bravyi-Kitaev's max Pauli weight matches
published exactly at every size — the cleanest validation of the four.
Jordan-Wigner's matches published for `L=3..8`, provably better from `L=9`.
Total Pauli weight beats published everywhere checked, for every encoding,
likely because their solver's search wasn't exhaustive — also in
`NOTES.md`.

The qualitative crossover (JW favored for small grids, ternary tree for
large ones) does reproduce using our own best-of-three-orderings numbers,
but the exact crossover point wobbles (JW briefly retakes the lead at
`9×9` before ternary tree wins from `10×10` on) rather than switching
cleanly at `8×8` as the paper's own solver-optimized orderings show. This
traces to the same limitation documented in `NOTES.md`: our restricted
three-ordering search underperforms ternary tree's true optimum (confirmed
via an exhaustive `9!` search at `3×3`), so its numbers here likely have
more headroom than the other three baselines'.

**Stage 1 is complete when Tests 1–4 pass.** Report results and stop.

---

## Stage 2 — an agent-written program becomes the submission

Do not begin until Stage 1 is signed off.

> **Built early**: `harness/evaluate.py`'s `evaluate(spec, encode_fn, terms)`
> already exists, ahead of Stage 2 — see `NOTES.md`. Nothing here needs to
> change.

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

**Built already**, ahead of Stage 2 — see `NOTES.md` for why (same reasoning
as `evaluate.py`) and for the parity-basis baseline that uses it.

Importable by `solution/`, so the generator can work in a convenient
parameterization and hand back canonical form:

- `from_linear_encoding(U)` — `U` invertible over `F_2`.
  `gamma_i -> X_{U(i)} Z_{P(i)}`, `gamma-bar_i -> X_{U(i)} Z_{R(i)}`, where
  `F = U^-1`, `R = LF` (`L` lower-triangular ones **including** the
  diagonal), `P = R + F`. (Corrected from an earlier draft of this note
  that had `L` strictly below the diagonal and `P`/`R` computed in the
  opposite order — disproven by requiring `from_linear_encoding(I)` to
  reproduce `baselines/jw.py` exactly; see `tests/test_constructors.py`.)
  Reference: arXiv 2504.21636 eq. (18).
- Ternary tree and Bravyi-Kitaev turned out not to need a separate
  constructor: both are expressible as `from_linear_encoding(U)` with `U`
  built from a recursive tree structure (Sierpinski/Fenwick respectively,
  see `baselines/ternary.py`/`bk.py`'s `tt_matrix`/`bk_matrix`) plus a
  shared `harness/constructors.py` helper, `transitive_closure(u)`, rather
  than a bespoke "labels along root-to-leaf paths" constructor as originally
  envisioned here.
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
  NOTES.md                investigation log (Table I, etc.) -- not a plan, don't trim it in here
  README.md               project overview + code structure, written early
                          for the GitHub repo; the Stage-2-specific
                          submission "contract" section still to come
  run.py                  entry point: `evaluate` (primary) + `verify` (debug), built ahead of schedule
  results.tsv             append-only log, written by `run.py evaluate`
  harness/                FROZEN
    paulis.py             symplectic representation, vectorized
    lattice.py            rectangle(), orderings, Hamiltonian term lists
    verify.py             the five checks
    score.py              score_majorana (score_paper judged unnecessary, see NOTES.md)
    evaluate.py           encode_fn -> verify -> score combinator (built ahead of Stage 2)
    constructors.py       from_linear_encoding() etc (built ahead of Stage 2)
  baselines/              FROZEN
    __init__.py           builds BASELINES from registry.json
    registry.json         {"name": {"module": ..., "sizes": [...]}} manifest
    jw.py  parity.py  bk.py  ternary.py -- all built
  tests/
    test_chain_analytic.py
    test_rejection.py
    test_ordering.py
    test_table1.py
    test_paulis.py  test_lattice.py  test_evaluate.py   -- per-module unit tests, added as gaps were found
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
4. **Neither the paper's prose nor their released code is reliable on its
   own for the cost model** (§1.6, `NOTES.md`) — their code's `Cre`/`Ciu`
   don't actually match their own published equations. Pull the LaTeX
   source and read the actual equations if it matters.
5. **Published baselines are heuristic** except where they match analytic
   results. "Beating" a Table I entry may mean beating a solver run rather
   than a bound — confirmed, not just suspected: see `NOTES.md`.
6. **Evaluation speed is the binding constraint** in later stages, not
   cleverness. Vectorize now.
