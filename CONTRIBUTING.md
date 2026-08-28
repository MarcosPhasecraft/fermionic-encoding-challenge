# Working on the harness itself

This file is for extending or fixing the *benchmark* (`harness/`,
`baselines/`, the tooling) — not for submitting an encoding. If you just
want to try beating the benchmark, see `README.md` instead; nothing here is
required reading for that.

## Documentation map

Four markdown files, each with a distinct job — see `CLAUDE.md` for why
they're kept separate rather than merged:

| File | Purpose |
|---|---|
| `CONTEXT.md` | The physics problem and why it matters |
| `PLAN.md` | The staged implementation plan: what to build, in what order, and the exact specs/contracts |
| `NOTES.md` | Investigation log: findings, ruled-out hypotheses, corrections (e.g. the Table I comparison against arXiv 2504.21636) |
| `CLAUDE.md` | Durable rules for working on this codebase — traps, conventions, the frozen/editable boundary |

## Status

Stage 1 (build and validate the verifier/scorer against known answers, no
agent, no search) is well underway. Currently working:

- Symplectic Pauli representation, vectorized Majorana-algebra verification
- Rectangular lattice specs with multiple mode orderings (row-major, snake,
  diagonal, arbitrary custom permutation)
- Hamiltonian term-list construction (hopping, number, interaction), with a
  genuinely complex hopping coefficient per arXiv 2504.21636 eq. 10
- Pauli-weight scoring (total, max, average)
- Four baseline encodings: Jordan-Wigner, parity basis, Bravyi-Kitaev, and
  ternary tree, all but JW built from a single general linear-encoding
  constructor. Parity/BK/ternary tree are each registered twice — once
  under `row_major`, once under `snake` (`baselines/*_snake.py`) — since no
  single one of the three built-in orderings is best on both total and max
  weight for those three encodings (JW alone has one ordering that's
  jointly optimal on both)
- Every baseline (and every submission) declares its own mode ordering via
  an optional `order(Lx, Ly) -> perm`, defaulting to `row_major` if it
  declares none — the harness does not search orderings on anyone's behalf
  (see "Adding a baseline" below)
- The `run.py evaluate` CLI and `results.tsv` logging
- 112 passing tests
- `scripts/submit_baseline.py` (test + register a new baseline) and
  `scripts/update_leaderboard.py` (regenerate `LEADERBOARD.md`)

An extensive investigation validated this against arXiv 2504.21636's
published Table I: our Bravyi-Kitaev max Pauli weight, under `row_major`,
exactly matches their published values at every one of the 13 grid sizes
checked; our Jordan-Wigner max Pauli weight matches for `3×3` through
`8×8` (and provably beats them beyond that); our total Pauli weight beats
their published values everywhere, for every encoding, under `snake`.
Ternary tree's max Pauli weight, unlike the other three, initially looked
*worse* than published under both built-in orderings — an exhaustive `9!`
search at `3×3` confirmed this is a limitation of the harness's built-in
orderings for a tree-structured encoding, not a construction bug (the true
optimum matches published exactly). Full details, including real bugs
found and fixed along the way, are in `NOTES.md`.

Not yet built: stabilizer support. No hosted leaderboard/submission
service exists yet — see `README.md`'s "How to play" for the current,
local-only workflow.

## Code structure

```
harness/            FROZEN — the trusted core; nothing here should change
                     to make a submission pass
  paulis.py          Pauli strings <-> symplectic bit-vector representation;
                     vectorized pairwise commutation check
  lattice.py         rectangle() builds lattice specs under a given mode
                     ordering; build_spec(Lx, Ly, order_fn) builds one from
                     a submission's own order() (row_major if None);
                     hamiltonian() builds Majorana-index term lists
  verify.py          verify(spec, mapping) -- checks the mapping is a valid
                     encoding (well-formed, satisfies the Majorana algebra).
                     Never raises on malformed input.
  score.py           score_majorana(spec, mapping, terms) -- Pauli-weight
                     metrics (total/max/avg) for a verified mapping
  evaluate.py        evaluate(spec, encode_fn, terms) -- the combinator:
                     calls encode_fn(spec), then verify(), then score()
                     only if verification passed
  constructors.py    from_linear_encoding(U) -- general ancilla-free linear
                     encoding constructor; baselines build on this
  loading.py         load_submission(path) -- (encode_fn, order_fn_or_None)
                     from an arbitrary file

baselines/           FROZEN — trusted reference implementations
  __init__.py        builds BASELINES from registry.json, by name
  registry.json       {"name": {"module": ..., "sizes": [...]}} manifest --
                     never hand-edit; scripts/submit_baseline.py writes it
  jw.py              Jordan-Wigner (order = row_major, jointly optimal)
  parity.py          Parity basis (dual to Jordan-Wigner), order = row_major
  parity_snake.py    Same encode() as parity.py, order = snake instead
  bk.py              Bravyi-Kitaev (Fenwick-tree linear encoding), order = row_major
  bk_snake.py        Same encode() as bk.py, order = snake instead
  ternary.py         Ternary tree (Sierpinski-tree linear encoding), order = row_major
  ternary_snake.py   Same encode() as ternary.py, order = snake instead

solution/            EDITABLE -- a submission's encode(spec) -> mapping goes
                     here; ships as an unfilled NotImplementedError stub,
                     see solution/README.md

tests/               pytest suite
examples/            Hand-written spec/mapping JSON for run.py's debug path
run.py               CLI entry point -- `run.py evaluate` scores a
                     solution/baseline; `run.py verify` is the raw-JSON
                     debug path
results.tsv          append-only log of every `run.py evaluate` run
```

The core design principle (see `PLAN.md`'s "Strategy" section for the full
reasoning): every baseline — and every submission — is a function
`encode(spec) -> mapping`, never a raw table of Pauli strings. A raw mapping
can't be meaningfully diffed, doesn't generalize across lattice sizes, and
almost any local edit to it breaks validity. Code, by contrast, reads as
*ideas* ("build a ternary tree", "order modes by lattice distance") that
can be improved and compared.

## Adding a baseline

1. Write `encode(spec) -> mapping` in a file (anywhere — it doesn't need to
   be inside the repo yet). If it's a linear encoding (most ancilla-free
   ones are), build it from `harness/constructors.py`'s
   `from_linear_encoding(U)` rather than hand-writing Pauli strings — see
   `baselines/parity.py` for the pattern, and sanity-check against
   `from_linear_encoding(I)`, which must reproduce `baselines/jw.py`
   exactly. Optionally also define `order(Lx, Ly) -> perm` (defaults to
   `row_major` if omitted) — see `harness/lattice.py`'s `row_major_perm`
   /`snake_perm`/`diagonal_perm` for reusable examples, or write your own.
   If your encoding's best total and best max weight come from genuinely
   different orderings (true for parity/BK/ternary tree — see `NOTES.md`),
   consider registering it twice, once per ordering, the way
   `baselines/bk_snake.py` reuses `baselines/bk.py`'s `encode()` under a
   different declared `order()` rather than duplicating logic — one
   leaderboard entry shouldn't silently mix numbers from two different runs.
2. Test and register it in one step:

   ```bash
   python3 scripts/submit_baseline.py --file your_file.py --name your_name --sizes 3-15
   ```

   `--sizes` accepts a range (`3-15`), a single size (`8`), or a list
   (`8,10,12`) — a submission doesn't have to cover the full range;
   defaults to `3-15` if omitted. This checks `verify()` passes at *every*
   claimed size under your declared `order()` (or `row_major`, if you
   declared none), and only if everything passes does it copy the file to
   `baselines/your_name.py` and add it to `baselines/registry.json`. A
   failure explains exactly which size and why, and touches nothing. Never
   hand-edit `registry.json` directly.
3. Add `tests/test_<name>.py` — at minimum, `verify()` passes for a few
   sizes, pin the resulting Pauli-string structure so a future refactor
   can't silently change it, and (if you defined one) pin `order()` against
   whichever built-in permutation function it should match.
4. Run `python3 scripts/update_leaderboard.py` (seconds — evaluates each
   registered baseline once per grid size it claims, under its own declared
   ordering, not a search over multiple orderings; see the file's own
   docstring) and commit the regenerated `LEADERBOARD.md` alongside your
   new baseline. Never hand-edit that file directly.

## Running the test suite

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

## References

- Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings via
  quadratic assignment*, arXiv 2504.21636 — the primary reference for
  metric definitions and the Table I comparison in `NOTES.md`. Their
  released code, cross-checked repeatedly throughout `NOTES.md` (cost
  model, Fenwick/Sierpinski constructions, solver objectives):
  [`github.com/cameton/QCE_QubitAssignment`](https://github.com/cameton/QCE_QubitAssignment).
- [ecdsa.fail](https://ecdsa.fail) / [ecdsafail-challenge](https://github.com/Layr-Labs/ecdsafail-challenge)
  — the benchmark-design precedent this project follows (frozen harness,
  adversarially-robust verifier, published baselines).

See `CONTEXT.md`'s references section for the full encoding/optimization
literature.
