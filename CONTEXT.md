# Fermion-to-qubit encodings: problem and context

## 1. The physical setup

Simulating fermionic systems — electrons in molecules, materials, lattice
models — is one of the main applications of quantum computers. Fermions obey
anticommutation relations that qubits do not, so every quantum simulation
algorithm must begin with a **fermion-to-qubit encoding**: a map from fermionic
operators to Pauli operators on a qubit register.

Fermionic modes carry creation and annihilation operators `a_j†`, `a_j`
satisfying

```
{a_i, a_j} = 0,    {a_i†, a_j} = delta_ij
```

It is convenient to work with **Majorana operators**

```
gamma_j     = a_j + a_j†
gamma-bar_j = -i (a_j - a_j†)
```

whose algebra is simply that all distinct Majoranas anticommute and each
squares to the identity:

```
{gamma_i, gamma-bar_j} = 2 delta_ij,    {gamma_i, gamma_j} = {gamma-bar_i, gamma-bar_j} = 0
```

An encoding assigns each of the `2M` Majoranas a Pauli string on `N` qubits.
For this to be a valid encoding it suffices that the images satisfy the same
anticommutation relations — the map is then an algebra homomorphism, and every
product of Majoranas (hence every fermionic Hamiltonian) maps correctly and
automatically.

## 2. Why the choice of encoding matters

Different valid encodings produce wildly different qubit Hamiltonians.

The oldest, **Jordan–Wigner**, maps each mode to one qubit and attaches a
string of Z operators:

```
gamma_j  ->  Z_0 Z_1 ... Z_{j-1} X_j
```

It is conceptually simple, but a hopping term between two modes that are far
apart in the chosen ordering produces a Pauli operator acting on many qubits.
On a 2D lattice this is severe: modes adjacent on the lattice can be far apart
in any linear ordering, so hopping terms acquire supports that grow with system
size.

The **Pauli weight** of a term — the number of qubits it acts on — is the
central cost parameter. It controls circuit depth, gate count, and measurement
cost. Reducing it is the point of the whole subfield.

Two broad families of encodings exist:

- **Ancilla-free mappings** use exactly `N = M` qubits, the dimensional
  minimum. Bravyi–Kitaev and the ternary-tree mapping bring hopping-term
  weights down to O(log M).
- **Local encodings** spend `N = c·M` qubits with `c > 1` to make all
  Hamiltonian terms O(1)-weight, at the cost of ancillas that scale with
  system size. Examples: Verstraete–Cirac (`N = 2M`), Derby–Klassen compact
  (`N = 1.5M`). Some carry local stabilizers, enabling error mitigation.

Whether the ancilla cost is worth paying depends on the hardware regime, and it
is not settled.

## 3. The optimization problem

> Given a fermionic interaction graph, find the encoding that minimizes the
> Pauli weight of the resulting qubit Hamiltonian.

Two standard cost functions, which do **not** agree:

1. **Total Pauli weight** — the sum, over all Hamiltonian terms, of the number
   of qubits each acts on. Corresponds to the number of single-qubit
   measurements needed to measure every term once, i.e. the cost of
   ground-state estimation.
2. **Maximum Pauli weight** — the largest weight of any single term.
   Corresponds to the non-locality of the Hamiltonian, and is the relevant
   time-complexity parameter for simulation algorithms.

A third variant appears in the literature: Fermi–Hubbard total weight,
`D = ReHop + Inter` (arXiv 2504.21636 eq. after 36) — real-coefficient
hopping *plus* the interaction term, excluding both the number term (`Num`)
and the imaginary-coefficient hopping piece (`ImHop`). (An earlier version
of this doc said "no interaction terms," which was backwards — the
interaction term is exactly what's included; verified directly against the
paper's LaTeX source, not the prose description, which is ambiguous here.)

The **mode ordering** is a free choice — physically irrelevant, but it changes
the Pauli weights substantially. Reordering is itself a special case of a
change of encoding, so it sits inside the same search space rather than beside
it.

## 4. What is known, and what is not

**Known:**

- The ternary-tree mapping achieves provably minimal Pauli weight in the
  average case for ancilla-free encodings, with single Majoranas of weight
  `ceil(log_3(2M+1))`.
- Jordan–Wigner, parity, and Bravyi–Kitaev are all expressible as ternary
  trees — they are points in one family, not separate inventions.
- The optimal fermionic ordering for Jordan–Wigner on a square lattice is
  known analytically (the Mitchison–Durbin numbering, for 6×6 and larger).
- Order-optimized comparisons of the four standard ancilla-free encodings are
  tabulated for square grids from 3×3 to 15×15 (arXiv 2504.21636, Table I).

**A striking feature of those results:** the best encoding *changes with
lattice size, and the crossover point depends on which metric you choose*.

| metric | Jordan–Wigner wins up to | ternary tree wins from |
|---|---|---|
| maximum Pauli weight | 5×5 (ties 6×6–7×7) | 8×8 |
| total Pauli weight | 9×9 | 10×10 |
| Fermi–Hubbard total | 10×10 | 11×11 |

Three different crossovers on the same lattice family, purely from the choice
of cost function.

**Open:**

- The published optimizations search over *orderings within four fixed
  encodings*. The space of ancilla-free linear encodings is all of
  `GL_M(F_2)` — roughly `2^(M^2)` elements. Four points of it have been
  examined systematically.
- Exact methods (SAT-based) find provable optima but do not scale. Heuristic
  methods scale but give no guarantees. Nothing occupies the middle.
- Cost functions incorporating **gate depth and circuit compilation** rather
  than raw Pauli weight are named as future work and have not been attempted.
- Automated search has barely touched the **local/stabilizer encodings**,
  where the design space is richer and error detection is available.

## 5. What we are building

A **generator/verifier harness**: a benchmark arena in which a program
proposes an encoding and frozen code checks and scores it.

- **Generator** — submits a *program* that, given a lattice specification,
  emits an encoding. The artifact is code, not a table of Pauli strings, so
  that improvements are legible, diffable, composable, and apply at every
  system size.
- **Verifier** — frozen, deterministic. Checks the Majorana algebra.
- **Scorer** — frozen, deterministic. Computes Pauli-weight metrics. Runs only
  if verification passes.

There is no verifier agent and no adversarial loop. The verifier's value comes
from being dumb enough to be trustworthy: as soon as it exercises judgement it
becomes something the generator can argue with, and the loop loses its ground
truth.

### Why this problem

Verification is **exact at any system size**, and cheap.

Checking that `2M` Pauli strings mutually anticommute is a symplectic inner
product over `GF(2)` — bit operations on a binary matrix. There is no
simulation, no approximation, no error tolerance, and therefore no question of
whether a result verified at small size still holds at large size.

That property is unusual. It means a submission can be checked exactly at the
size it claims to work at, which in turn means the benchmark has no
extrapolation gap for a search process to exploit.

### Precedent

The design follows **ecdsa.fail**, a public benchmark in which solvers submit
code that emits a reversible circuit for elliptic-curve point addition, scored
on Toffoli count × qubit width. Frozen harness, one editable directory,
published baselines, deterministic scoring. Open participation drove the
circuit roughly 50% past the published reference within weeks.

Two lessons carried over:

1. **The harness is the product.** Almost all the design effort there went into
   the evaluator, and almost none into agent architecture.
2. **Verifier-gaming is real, not hypothetical.** The leading submission
   contains a hardcoded 13-digit nonce found by GPU search, plus a knob that
   applies X twice to the same qubit — a pure identity whose only function is
   to shift which test inputs are drawn. Assume any scalar metric will be
   optimized exactly as stated, including its sampling.

## 6. References

**Primary:**

- Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings via
  quadratic assignment*, arXiv **2504.21636**. Metric definitions (§III-C),
  linear-encoding formalism (§III-D, eq. 18), Table I comparison across square
  grids. Code: `github.com/cameton/QCE_QubitAssignment`.

**Encodings:**

- Jordan & Wigner, *Z. Phys.* **47**, 631 (1928).
- Bravyi & Kitaev, *Ann. Phys.* **298**, 210 (2002) — Bravyi–Kitaev and
  superfast encodings.
- Jiang, Kalev, Mruczkiewicz, Neven, *Quantum* **4**, 276 (2020) — ternary
  tree, optimality result.
- Verstraete & Cirac, *JSTAT* 2005 P09012 — local encoding, `N = 2M`.
- Derby, Klassen, Bausch, Cubitt, *PRB* **104**, 035118 (2021) — compact
  encodings with local stabilizers.
- Miller, Zimborás, Knecht, Maniscalco, García-Pérez, *PRX Quantum* **4**,
  030314 (2023) — Bonsai; ternary-tree unification.
- Chiew, Harrison, Strelchuk, arXiv **2412.07578** — ternary tree
  transformations are equivalent to linear encodings of the Fock basis.

**Optimization:**

- Chiew & Strelchuk, *Quantum* **7**, 1145 (2023) — algorithmic enumeration;
  analytic optimal Jordan–Wigner ordering.
- Mitchison & Durbin, *SIAM J. Alg. Disc. Meth.* **7**, 571 (1986) — optimal
  numbering of an N×N array.
- *Fermihedral*, arXiv **2403.17794** — SAT formulation, provably optimal,
  does not scale.
- *HATT*, arXiv **2409.02010** — Hamiltonian-adaptive ternary trees,
  heuristic, scales.
- Miller, Glos, Zimborás, arXiv **2403.03992** — Treespilation,
  architecture- and state-optimized mappings.
- Yu, Liu, Sugiura, Van Voorhis, Zeytinoğlu, arXiv **2502.11933** —
  Clifford-circuit-based heuristic optimization.

**Harness design:**

- `github.com/ecdsafail/ecdsafail-challenge` — contract discipline; see
  `src/point_add/memory/` for what accumulated agent notes look like in
  practice.
- `yukon.org` — platform generalizing the format; `benchmark.json` manifest
  schema.

**Index:**

- `errorcorrectionzoo.org` — encodings cross-referenced to primary sources.
