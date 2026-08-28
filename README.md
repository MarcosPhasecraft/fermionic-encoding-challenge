# The Fermionic Encoding Challenge

> **Goal.** Write the fermion-to-qubit encoding that produces the
> lowest-weight qubit Hamiltonian for a given fermionic lattice, scored on
> **total Pauli weight** and **maximum Pauli weight** — two metrics that
> don't agree, so a good encoding has to reckon with both.

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

### Reference numbers

See [`LEADERBOARD.md`](LEADERBOARD.md) for the current numbers — every
square grid from `3×3` to `15×15`, for every encoding implemented so far,
laid out the same way as arXiv 2504.21636's own Table I (one table for
total Pauli weight, one for maximum), with that paper's published numbers
included alongside ours for direct comparison. It's a generated file, not
hand-maintained text: every one of our own rows is the literal output of
`scripts/update_leaderboard.py` re-running the current code (the best of
the harness's three built-in orderings — a cheap, always-tractable check,
not an exhaustive search over every possible ordering, which stops being
feasible past the smallest sizes), so it can't drift from what the
harness actually computes.

The open ground is genuinely open: different lattice shapes, and
encodings nobody has implemented here yet (Bravyi-Kitaev, ternary tree,
and the much larger space beyond those four well-known points).

**Found something better?** Turn it into a `baselines/<name>.py` (see
`CONTRIBUTING.md`), register it, then run:

```bash
python3 scripts/update_leaderboard.py
```

and commit the regenerated `LEADERBOARD.md` alongside your new baseline.

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
no other arguments are allowed. A complete, valid (if unremarkable)
starting point is Jordan-Wigner itself:

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
failed and why, with no numbers attached. `--ly` (default `1`, a 1D chain),
`--ordering` (`row_major` / `snake` / `diagonal`), and `--model`
(`hopping` / `quadratic` / `full`, default `full`) are also available —
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
assignment*, arXiv 2504.21636.

This benchmark's design — a frozen, adversarially-robust harness with the
thing being evaluated kept as a separate, swappable piece — follows
[ecdsa.fail](https://ecdsa.fail) and its
[ecdsafail-challenge](https://github.com/Layr-Labs/ecdsafail-challenge)
repo. Thanks to that project for the format.
