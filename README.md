# The Fermionic Encoding Challenge



> **Goal.** Write the fermion-to-qubit encoding that produces the
> lowest-weight qubit Hamiltonian for a given fermionic lattice, scored on
> **total Pauli weight** and **maximum Pauli weight** — two independent
> measures of success, one mattering most for VQE-style measurement, the
> other for Trotterized time dynamics.

**[Live leaderboard →](https://marcosphasecraft.github.io/fermionic-encoding-challenge/)**

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
on the lattices that actually describe real materials, it isn't. We take
arXiv 2504.21636 as our primary reference and baseline for this
challenge.

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

**Found something better? Open a pull request.**

Fork the repo, add one self-contained folder under `submissions/`, and open
a PR:

```
submissions/<your-name>/
  encode.py         # def encode(spec) -> mapping; optional def order(Lx, Ly) -> perm
  submission.json   # {"name": "...", "label": "...", "sizes": "3-15"}
  memory/           # OPTIONAL -- notes on what you tried, welcome but not required
```

**Change nothing else** — a PR that mixes a submission with other edits is
rejected automatically. That's the whole rule.

CI then verifies your encoding at every size you claim and reports the
scores on the PR, usually within minutes. You don't need to run anything
locally, though you can check first with
`scripts/submit_baseline.py --file ... --name ...` (see `CONTRIBUTING.md`)
if you'd rather not iterate through CI.

`submission.json`'s exact schema is in [`inbox/README.md`](inbox/README.md);
the short version is `name` (a filesystem-safe identifier), `label` (what
shows on the leaderboard), and `sizes` (which grids it claims to be valid
for), all required. If you include a `memory/` folder of markdown notes on
what worked and what didn't, it's carried into the accepted record and
indexed in `MEMORY.md` for the next person to learn from — the same idea as
ecdsa.fail's own shared memory notes.

A maintainer merges once the check is green; a second, trusted workflow then
recomputes the scores, registers the submission, and regenerates the
leaderboard. Nothing you submit is published on the strength of the PR check
alone.

(Submissions can still be handed over as a folder and processed by hand with
`python3 scripts/process_inbox.py` — same pipeline, same verification, just
without the PR.)

## How to play

```bash
git clone https://github.com/MarcosPhasecraft/fermionic-encoding-challenge.git
cd fermionic-encoding-challenge
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
        "stabilizers": [],           # non-empty only for the ancilla/stabilizer challenge -- see below
    }
```

Leave `stabilizers` empty (`N = M`) for this challenge and the graph challenge
below — that's what most of this section describes. If you're using ancilla
qubits (`N > M`), see "The ancilla/stabilizer challenge" further down: it's a
separate challenge with its own submission format and detection mechanism,
not a variant of this one.

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

## The ancilla/stabilizer challenge

A separate challenge from everything above, with its own leaderboard
([`LEADERBOARD_ANCILLAS.md`](LEADERBOARD_ANCILLAS.md)) and its own submission
format. Everywhere else on this page, "valid" means `N = M` and `stabilizers`
is empty; here it's the opposite — a submission is expected to use ancilla
qubits (`N > M`) and a real, non-empty stabilizer group, verified against the
full set of stabilizer-code checks (pairwise Majorana anticommutation,
stabilizers mutually commuting, stabilizers commuting with every Majorana,
and the stabilizer group having exactly the right rank to leave a genuine
`M`-mode Fock space behind — see `harness/v2/verify.py`).

**The challenge, precisely.** Cap the maximum Pauli weight, then *minimize
the number of ancilla qubits* (`N - M`) needed to reach a genuinely valid
encoding under that cap. Lower is better, and the cap is checked at every
size a submission claims, not just asserted.

**You choose the cap.** It's `"max_weight"` in `submission.json` (default
`3`), not something the challenge fixes for you — the interesting object
here is the whole locality/ancilla trade-off curve, and pinning one cap
would only ever show one point on it. Boards are currently rendered for
**weight 3, 4 and 5**; any other cap is still verified, scored, and
cached, just not displayed yet (one line in
`scripts/update_leaderboard_ancillas.py` showcases a new one).

**A submission is ranked by the weight it actually achieves, not the cap it
claimed**, so it appears on *every* board whose cap it satisfies — an
encoding reaching weight 3 everywhere is listed on both the weight-3 and
weight-4 boards, since it trivially satisfies the looser cap. That's what
makes the weight-4 board honest: "how few ancillas if you're allowed weight
4" has to include the weight-3 constructions too.

Square lattices `3×3` through `15×15` (the same range as the ancilla-free
challenge above); hexagonal lattices are a valid target too (same sizes as
the graph challenge's own hexagonal sweep — see
[`LEADERBOARD_GRAPHS.md`](LEADERBOARD_GRAPHS.md)), accepted, verified, and
scored identically, but not yet shown on the leaderboard — there's no working
hexagonal reference construction there yet (see `NOTES.md` if you're curious
why, or want to take a crack at it yourself).

**The starting point** on every board is
[Derby-Klassen](https://arxiv.org/abs/2003.06939)
(`harness/v2/baselines/dk.py`), reconstructed directly from the paper and
verified to reproduce its own claimed results exactly (max weight 3, fewer
than 1.5 qubits per mode) — shown as the dotted reference line on each
chart. It anchors the weight-4 board as well as the weight-3 one: no
published construction reaches weight 4 with fewer qubits than DK reaches
weight 3 with, so there's real room there. Beating it means using *fewer*
ancillas while still genuinely meeting the cap, not gaming either
constraint.

**How a submission is told apart from the others.** `submission.json` gets
one new field: `"challenge": "ancillas"`. That's the *entire* detection
mechanism — its presence (and only its presence) routes a submission through
this challenge's own pipeline (`harness/v2`'s stabilizer-aware verifier and
scorer) instead of the ancilla-free one; its absence means "business as
usual" and nothing about how existing submissions are processed changes.
Concretely:

```json
{
  "name": "alice_dk_variant",
  "label": "Alice's DK Variant",
  "sizes": "3-15",
  "challenge": "ancillas",
  "max_weight": 4,
  "graph": "square"
}
```

`max_weight` defaults to `3` if omitted — set it to `4` (or anything else)
to target a looser board. `graph` defaults to `"square"` if omitted; set it
to `"hexagonal"` to target the hexagonal lattice instead (using the graph challenge's own explicit
`"LxxLy"` sizes grammar there, exactly as in `inbox/README.md`'s existing
description of that grammar). `encode.py` may additionally define
`represent(term, raw_pauli, spec, mapping) -> str`, an optional hook for
proposing a lower-weight, stabilizer-equivalent representative of a specific
Hamiltonian term — the harness certifies any proposed representative exactly
before trusting its weight (see `harness/v2/score.py`); without it, the raw
Majorana product is scored as-is. Full schema, the exact acceptance
criteria, and how this reaches the leaderboard: see `inbox/README.md`'s own
"Ancilla/stabilizer challenge" section.

`scripts/run_challenge.py` is this challenge's own local testing CLI (the
analogue of `run.py evaluate` above):

```bash
python3 scripts/run_challenge.py ancillas --graph square --max-weight 3 \
    --sizes 3-15 --solution solution/encode.py
```

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
