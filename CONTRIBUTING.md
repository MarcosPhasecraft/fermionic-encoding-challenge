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
  constructor
- The `run.py evaluate` CLI and `results.tsv` logging
- 99 passing tests
- `scripts/submit_baseline.py` (test + register a new baseline) and
  `scripts/update_leaderboard.py` (regenerate `LEADERBOARD.md`)

An extensive investigation validated this against arXiv 2504.21636's
published Table I: our Bravyi-Kitaev max Pauli weight exactly matches
their published values at every one of the 13 grid sizes checked; our
Jordan-Wigner max Pauli weight matches for `3×3` through `8×8` (and
provably beats them beyond that); our total Pauli weight beats their
published values everywhere, for every encoding. Ternary tree's max Pauli
weight, unlike the other three, comes out *worse* than published at every
size under our three built-in orderings — an exhaustive `9!` search at
`3×3` confirmed this is a limitation of that restricted ordering search,
not a construction bug (the true optimum matches published exactly). Full
details, including real bugs found and fixed along the way, are in
`NOTES.md`.

Not yet built: stabilizer support. No hosted leaderboard/submission
service exists yet — see `README.md`'s "How to play" for the current,
local-only workflow.

## Code structure

```
harness/            FROZEN — the trusted core; nothing here should change
                     to make a submission pass
  paulis.py          Pauli strings <-> symplectic bit-vector representation;
                     vectorized pairwise commutation check
  lattice.py         rectangle() builds lattice specs under various mode
                     orderings; hamiltonian() builds Majorana-index term
                     lists from a spec
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

baselines/           FROZEN — trusted reference implementations
  __init__.py        builds BASELINES from registry.json, by name
  registry.json       {"name": {"module": ..., "sizes": [...]}} manifest --
                     never hand-edit; scripts/submit_baseline.py writes it
  jw.py              Jordan-Wigner
  parity.py          Parity basis (dual to Jordan-Wigner)
  bk.py              Bravyi-Kitaev (Fenwick-tree linear encoding)
  ternary.py         Ternary tree (Sierpinski-tree linear encoding)

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
   exactly.
2. Test and register it in one step:

   ```bash
   python3 scripts/submit_baseline.py --file your_file.py --name your_name --sizes 3-15
   ```

   `--sizes` accepts a range (`3-15`), a single size (`8`), or a list
   (`8,10,12`) — a submission doesn't have to cover the full range;
   defaults to `3-15` if omitted. This checks `verify()` passes at *every*
   claimed size under all three built-in orderings, and only if everything
   passes does it copy the file to `baselines/your_name.py` and add it to
   `baselines/registry.json`. A failure explains exactly which size and why,
   and touches nothing. Never hand-edit `registry.json` directly.
3. Add `tests/test_<name>.py` — at minimum, `verify()` passes for a few
   sizes, and pin the resulting Pauli-string structure so a future refactor
   can't silently change it.
4. Run `python3 scripts/update_leaderboard.py` (seconds — evaluates the
   three built-in orderings across every grid size each registered baseline
   claims, not an exhaustive search over all orderings; see the file's own
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
  metric definitions and the Table I comparison in `NOTES.md`.
- [ecdsa.fail](https://ecdsa.fail) / [ecdsafail-challenge](https://github.com/Layr-Labs/ecdsafail-challenge)
  — the benchmark-design precedent this project follows (frozen harness,
  adversarially-robust verifier, published baselines).

See `CONTEXT.md`'s references section for the full encoding/optimization
literature.
