# encoding-bench

A benchmark harness for **fermion-to-qubit encodings** — the maps from
fermionic creation/annihilation operators to Pauli operators on qubits that
every quantum simulation algorithm needs. Different valid encodings produce
wildly different Pauli weights for the same physical Hamiltonian; the goal
here is a trustworthy, deterministic way to generate, verify, and score
candidate encodings, so that eventually an automated (or AI-driven) search
over the encoding space has something reliable to search against.

Modeled on [ecdsa.fail](https://ecdsa.fail): a frozen, adversarially-robust
verifier and scorer, with the thing being evaluated kept as a separate,
swappable piece. See `CONTEXT.md` for the full physics/motivation and
`PLAN.md` for the staged build plan.

## Status

Stage 1 (build and validate the verifier/scorer against known answers, no
agent, no search) is well underway. Currently working:

- Symplectic Pauli representation, vectorized Majorana-algebra verification
- Rectangular lattice specs with multiple mode orderings (row-major, snake,
  diagonal, arbitrary custom permutation)
- Hamiltonian term-list construction (hopping, number, interaction), with a
  genuinely complex hopping coefficient per arXiv 2504.21636 eq. 10
- Pauli-weight scoring (total, max, average)
- Two baseline encodings: Jordan-Wigner and parity basis, both built from a
  single general linear-encoding constructor
- 38 passing tests

An extensive investigation validated this against arXiv 2504.21636's
published Table I: our Jordan-Wigner implementation's max Pauli weight
exactly matches their published values for `3×3` through `8×8` grids (and
provably beats them beyond that), and our total Pauli weight beats their
published values at every grid size checked. Full details, including two
real bugs found and fixed along the way, are in `NOTES.md`.

Not yet built: Bravyi-Kitaev and ternary-tree baselines, stabilizer support,
and the ordering/Table-I tests aren't yet formalized as pytest files (the
underlying validation work is done; see `NOTES.md`).

## Documentation map

Four markdown files, each with a distinct job — see `CLAUDE.md` for why
they're kept separate rather than merged:

| File | Purpose |
|---|---|
| `CONTEXT.md` | The physics problem and why it matters — read this first |
| `PLAN.md` | The staged implementation plan: what to build, in what order, and the exact specs/contracts |
| `NOTES.md` | Investigation log: findings, ruled-out hypotheses, corrections (e.g. the Table I comparison) |
| `CLAUDE.md` | Durable rules for working on this codebase — traps, conventions, the frozen/editable boundary |

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
  evaluate.py         evaluate(spec, encode_fn, terms) -- the combinator:
                     calls encode_fn(spec), then verify(), then score()
                     only if verification passed
  constructors.py    from_linear_encoding(U) -- general ancilla-free linear
                     encoding constructor; baselines build on this

baselines/           FROZEN — trusted reference implementations
  __init__.py         BASELINES = {"jw": ..., "parity": ...} registry, by name
  jw.py               Jordan-Wigner
  parity.py           Parity basis (dual to Jordan-Wigner)

solution/            EDITABLE, Stage 2 only -- reserved for an agent-written
                     encode(spec) -> mapping submission; empty for now

tests/               pytest suite, 38 tests
examples/            Hand-written spec/mapping JSON for run.py's debug path
run.py               CLI debug entry point: run.py --spec f.json --mapping g.json
```

The core design principle (see `PLAN.md`'s "Strategy" section for the full
reasoning): every baseline — and eventually every submission — is a
function `encode(spec) -> mapping`, never a raw table of Pauli strings. A
raw mapping can't be meaningfully diffed, doesn't generalize across lattice
sizes, and almost any local edit to it breaks validity. Code, by contrast,
reads as *ideas* ("build a ternary tree", "order modes by lattice distance")
that can be improved and compared.

## Running it

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v          # run the test suite

# Or evaluate an encoding directly:
python3 -c "
from harness.evaluate import evaluate
from harness.lattice import rectangle, hamiltonian
from baselines.jw import encode

spec = rectangle(3, 3)
result = evaluate(spec, encode, hamiltonian(spec, model='full'))
print(result)
"
```

For hand-written debug inputs (raw Pauli strings, not code) see `run.py
--spec examples/spec_chain4.json --mapping examples/mapping_chain4_jw.json`.

## References

- Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings via
  quadratic assignment*, arXiv 2504.21636 — the primary reference for
  metric definitions and the Table I comparison in `NOTES.md`.
- [ecdsa.fail](https://ecdsa.fail) — the benchmark-design precedent this
  project follows (frozen harness, adversarially-robust verifier, published
  baselines).

See `CONTEXT.md`'s references section for the full encoding/optimization
literature.
