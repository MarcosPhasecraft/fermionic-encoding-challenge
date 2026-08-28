# The Fermionic Encoding Challenge

> **Goal.** Write the fermion-to-qubit encoding that produces the
> lowest-weight qubit Hamiltonian for a given fermionic lattice, scored on
> **total Pauli weight** and **maximum Pauli weight** — two independent
> measures of success, one mattering most for VQE-style measurement, the
> other for Trotterized time dynamics.

---

## Why this matters

Simulating fermionic systems — electrons in molecules, materials, lattice
models — is one of the most promising applications of quantum computers.
But quantum computers are built from qubits, which don't obey the same
anticommutation relations fermions do, so every simulation has to start
with a **fermion-to-qubit encoding**: a map from fermionic operators to
qubit (Pauli) operators. Different valid encodings optimize different
things, and can produce wildly different **Pauli weight** — the qubit cost
driving circuit depth and measurement cost — for the exact same physics.
In one dimension the optimal choice is well understood; in two dimensions,
on the lattices that actually describe real materials, it isn't. Recent
work (arXiv 2504.21636, our primary reference) has started mapping out
that space, but nobody knows what the best 2D encoding actually looks like.

## The benchmark, precisely

You are given a Python harness that:

1. **Builds** an encoding by calling `encode(spec) -> mapping`, where
   `spec` fully describes a rectangular `Lx × Ly` lattice of fermionic
   modes (mode count, geometry, nearest-neighbour edges, and the mode
   ordering) and `mapping` gives every one of the `2M` Majorana operators
   as a Pauli string.
2. **Verifies** the mapping by checking that its `2M` Majorana operators
   pairwise anticommute — a symplectic linear-algebra condition over
   `GF(2)`, checked *exactly*, not by simulation or sampling. If the
   generators satisfy this one algebraic condition, the map is provably a
   valid encoding at that system size, full stop: every product of
   Majoranas — and therefore every fermionic Hamiltonian — maps correctly,
   automatically. There is no held-out test set to overfit and no
   approximation to exploit.
3. **Scores** the mapping by building the lattice's physical Hamiltonian —
   one number term per mode, one hopping term per edge (with a genuinely
   complex coefficient, so both its real and imaginary parts count
   separately), one interaction term per edge — translating every term
   into Pauli operators via your mapping, and computing each term's weight
   (how many qubits it acts on nontrivially).

Two independent metrics are reported, and neither is combined into the
other:

- **Total Pauli weight** — the sum of every term's weight. Roughly, the
  cost of measuring the whole Hamiltonian once.
- **Maximum Pauli weight** — the largest weight of any single term.
  Roughly, the non-locality that determines simulation circuit depth.

**Lower is better, on either.** You may optimize for one, the other, or
try for both — they will not always be minimized by the same encoding.

### What "valid" means

A mapping is rejected if:

- it's malformed (wrong qubit count, wrong number of Pauli strings, illegal
  characters), or
- any two of its `2M` Majorana operators fail to anticommute.

That's it — one substantive condition. It's checked at whatever system size
you submit, exactly, every time. There's no larger held-out size where a
mapping that looked valid at small `M` turns out to be broken.

### Leaderboard

See [`LEADERBOARD.md`](LEADERBOARD.md) — total and maximum Pauli weight
for every encoding implemented so far, across every square grid from
`3×3` to `15×15`, with arXiv 2504.21636's own published numbers included
for direct comparison. Every number there comes from actually running
the current code, not hand-typed, and reflects that submission's own
declared mode ordering (see `order()` below) — the harness doesn't search
orderings on your behalf, so there may be room to improve a listed number
just by declaring a better ordering, not only by writing a new encoding.

The open ground is genuinely open: different lattice shapes, better
orderings for the encodings already here, and the much larger space of
encodings beyond JW, parity basis, Bravyi-Kitaev, and ternary tree. See
[`MEMORY.md`](MEMORY.md) for notes past submitters left on what they
tried — unverified, but a real head start over starting from nothing.

**Found something better?**

Package it as one self-contained folder:

```
<any-folder-name>/
  encode.py         # def encode(spec) -> mapping; optional def order(Lx, Ly) -> perm
  submission.json   # {"name": "...", "label": "...", "sizes": "3-15"}
  memory/           # OPTIONAL -- notes on what you tried, welcome but not required
```

and hand that whole folder — as one unit, not just the `.py` file — to
whoever maintains this repo. `submission.json`'s exact schema is in
`inbox/README.md`; the short version is `name` (a filesystem-safe
identifier), `label` (what shows on the leaderboard), and `sizes` (which
grids it claims to be valid for), all required. If you include a `memory/`
folder of markdown notes on what worked and what didn't, it's carried
into the accepted record and indexed in `MEMORY.md` for the next person
to learn from — the same idea as ecdsa.fail's own shared memory notes.

On their end, registering it is one command —
`python3 scripts/process_inbox.py`, run after dropping your folder into
`inbox/` — which validates the manifest and the file, runs `verify()` at
every size claimed, and only if everything passes registers it,
regenerates `LEADERBOARD.md`, and re-runs the test suite. No manual flags,
no case-by-case judgment calls. (A single ad hoc file can still be tested
by hand with `scripts/submit_baseline.py --file ... --name ...` — see
`CONTRIBUTING.md` — useful for trying your own idea locally before
sending it over.)

## How to play

```bash
git clone https://github.com/MarcosPhasecraft/fermionic_encodings_harness.git
cd fermionic_encodings_harness
pip install -r requirements.txt
```

`solution/encode.py` is already there, waiting — it ships as an unfilled
stub that raises `NotImplementedError` until you write something. The
contract:

```python
def encode(spec: dict) -> dict:
    ...
    return {
        "n_qubits": n,               # N >= M
        "majoranas": [...],          # 2M Pauli strings, length N, chars from IXYZ
        "stabilizers": [],           # ancilla-free for now: leave empty
    }
```

`spec` is a dict with `M` (mode count), `Lx`/`Ly`, `edges` (the fermionic
interaction graph), and `coords` — everything you need is already in it;
no other arguments are allowed.

You may also define a companion function that picks which physical site
gets which mode index — the harness builds `spec` using it if present:

```python
def order(Lx: int, Ly: int) -> list[int]:
    ...  # perm[k] = mode index assigned to the site whose row-major raw index is k
```

If you don't define one, the harness defaults to `row_major`. Pauli weight
is very sensitive to this choice — it's part of your submission, not
something the harness searches for you, so a good ordering is as legitimate
a way to improve your score as a better `encode()`. Like `encode()`, it
must be a genuine formula in `Lx, Ly` (as the three examples in
`harness/lattice.py` are), not a lookup table keyed to specific sizes.

A complete, valid (if unremarkable) starting point is Jordan-Wigner itself:

```python
def encode(spec):
    m = spec["M"]
    majoranas = []
    for j in range(m):
        prefix, suffix = "Z" * j, "I" * (m - j - 1)
        majoranas += [prefix + "X" + suffix, prefix + "Y" + suffix]
    return {"n_qubits": m, "majoranas": majoranas, "stabilizers": []}
```

Then score it:

```bash
python3 run.py evaluate --lx 3 --ly 3 --note "what I tried"
```

This builds the `3×3` spec, runs your `encode(spec)`, verifies the result,
scores it if verification passed, prints the full result, and appends a
row to `results.tsv`:

```
{'passed': True,
 'checks': {'well_formed': {'passed': True, 'issues': []},
            'majorana_algebra': {'passed': True, 'n_violations': 0, 'violations': []}},
 'n_qubits': 9,
 'total_weight': 201,
 'max_weight': 4,
 'avg_weight': 2.161290322580645}
```

If verification fails, scoring never runs — you'll see exactly which check
failed and why, with no numbers attached. `--ly` (default `1`, a 1D chain)
and `--model` (`hopping` / `quadratic` / `full`, default `full`) are also
available. `--ordering` (`row_major` / `snake` / `diagonal`) overrides your
own `order()` for one-off local experimentation — omit it to use your
submission's own declared ordering (or `row_major`, if it declares none).
`python3 run.py evaluate --help` for the full list.

**There's no hosted submission service yet** — every `run.py evaluate` run
only appends to your own local `results.tsv`, nothing leaves your machine.
[`LEADERBOARD.md`](LEADERBOARD.md) is the closest thing to a public
leaderboard right now: it's regenerated by whoever adds a baseline (see
"Found something better?" above), not automatically, so it's honest but
not real-time.

### What you can edit

You may edit `solution/encode.py` freely — and `solution/memory/`, for your
own running notes.

You may **not** edit anything under `harness/` or `baselines/` (that's the
frozen referee — the whole point is that it's trustworthy specifically
*because* it doesn't change to accommodate a submission) or `results.tsv`
directly (the harness appends to it for you). You *can* import from
`harness/` — in particular, `harness.constructors.from_linear_encoding(U)`
builds a complete ancilla-free encoding from a single invertible matrix
`U` over `GF(2)`, which is a much smaller design surface than hand-writing
`2M` Pauli strings if your idea is expressible as a linear encoding.

### A caution on running submissions you didn't write

`solution/encode.py` is arbitrary Python — verification checks the
*mapping* it returns, not the code itself. If you're running someone
else's submission, do it somewhere isolated.

## Credits

Metric definitions and the reference baselines here follow Chiew, Ibrahim,
Safro, Strelchuk, *Optimal fermion-qubit mappings via quadratic
assignment*, arXiv 2504.21636 — code:
[`github.com/cameton/QCE_QubitAssignment`](https://github.com/cameton/QCE_QubitAssignment).

This benchmark's design — a frozen, adversarially-robust harness with the
thing being evaluated kept as a separate, swappable piece — follows
[ecdsa.fail](https://ecdsa.fail) and its
[ecdsafail-challenge](https://github.com/Layr-Labs/ecdsafail-challenge)
repo. Thanks to that project for the format.
