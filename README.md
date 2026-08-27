# The Fermion-to-Qubit Encoding Challenge

> **Goal.** Write the fermion-to-qubit encoding that produces the
> lowest-weight qubit Hamiltonian for a given fermionic lattice, scored on
> **total Pauli weight** and **maximum Pauli weight** — two metrics that
> don't agree, so a good encoding has to reckon with both.

---

## Why this matters

Simulating fermionic systems — electrons in molecules, materials, lattice
models — is one of the leading applications of quantum computers. But
fermionic operators obey anticommutation relations that qubits don't, so
every simulation algorithm has to start by translating the physics into a
different language: a **fermion-to-qubit encoding**, a map from fermionic
operators to Pauli operators on a qubit register.

That translation is not unique, and the choice matters enormously. The same
physical Hamiltonian, run through two different (both perfectly valid)
encodings, can come out with wildly different **Pauli weight** — the number
of qubits each term acts on. Weight controls circuit depth, gate count, and
measurement cost directly. A hopping term between two lattice sites that's
weight 2 under one encoding can be weight 20 under another, purely from how
the modes got labeled. On a 2D lattice in particular, naive encodings
routinely produce hopping terms whose weight grows with system size, even
though the underlying interaction is local.

A handful of encodings are well known — Jordan-Wigner, Bravyi-Kitaev,
parity, ternary tree — but the space of valid ancilla-free encodings is
roughly `2^(M²)` for `M` fermionic modes. Four points of that space have
been studied systematically. Nobody knows what the best encoding for a
given lattice actually looks like.

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

Two baselines exist today — Jordan-Wigner and the parity encoding — and
one lattice size has been solved exhaustively (all `9!` mode orderings, for
the `3×3` / 9-mode case):

| encoding | best total weight | best max weight |
|---|---|---|
| Jordan-Wigner | **201** | **4** |
| Parity | 233 | 5 |

Both numbers are provably optimal *for that one lattice size* — no
reordering of either encoding does better. That's the floor for a solved
case, not a target: it exists to confirm the harness is trustworthy, not
because there's room to beat it. The actual open ground is everywhere else
— larger lattices (nothing above `3×3` has been exhaustively solved),
different lattice shapes, and encodings nobody has implemented here yet
(Bravyi-Kitaev, ternary tree, and the much larger space beyond those four
well-known points).

## How to play

```bash
git clone https://github.com/MarcosPhasecraft/fermionic_encodings_harness.git
cd fermionic_encodings_harness
pip install -r requirements.txt
```

Write your encoding in `solution/encode.py`:

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

**There's no public leaderboard or submission service yet** — this is a
local benchmark for now. Every run just appends to your own `results.tsv`;
nothing leaves your machine.

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
