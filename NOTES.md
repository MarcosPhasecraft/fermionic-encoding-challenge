# Investigation notes

Findings from validating the harness against arXiv 2504.21636 (Chiew,
Ibrahim, Safro, Strelchuk) — kept here, separate from `PLAN.md`, so the plan
stays a plan and this stays free to grow. `PLAN.md` points here where
relevant; durable modeling rules that came out of this are in `CLAUDE.md`'s
traps list, not repeated here.

## Table I reproduction (PLAN.md §1.6/1.7 Test 4)

Two real bugs were found and fixed in `harness/lattice.py`'s `hamiltonian()`
while trying to reproduce Table I for Jordan–Wigner on a 3×3 grid:

1. **Interaction term was incomplete.** `n_i n_j` expands to `(1/4)(I +
   i·G_i + i·G_j − G_i·G_j)` with `G_i = γ_iγ̄_i` — three nontrivial Pauli
   terms, not just the quartic product `G_i·G_j`. We were only emitting the
   quartic one. Found by inspecting the paper's released code
   (`hexaly_quadratic_assignment.py`'s `map_cost`, whose `Rep` term is
   literally `weight(F_r) + weight(F_c) + weight(F_r xor F_c)`).
2. **Hopping term was real-coefficient-only.** eq. 10's hopping term
   `c_ij A_i^dag A_j + c_ij^* A_j^dag A_i` needs a genuinely complex `c_ij`
   in general — Hermiticity forces `Num`'s and the interaction term's
   coefficients real (`A_i^dag A_i` and `A_i^dag A_i A_j^dag A_j` are each
   already Hermitian on their own), but hopping's `A_i^dag A_j` alone isn't,
   so `c_ij` is free to be complex. That's 4 Pauli terms per edge (`ReHop`'s
   two, `ImHop`'s two), not 2. We were only building the 2 real-part ones.

Both are fixed; `hamiltonian(..., model="full")` + `score_majorana` now
reproduce the paper's exact equations below, straight from committed code.

### The verified formula

Pulled from the arXiv LaTeX source directly (not prose, not their code):

```
Num_i := ||F_i||_0
ReHop_ij := ||max(P_i+R_j, U_i+U_j)||_0 + ||max(R_i+P_j, U_i+U_j)||_0
ImHop_ij := ||max(P_i+P_j, U_i+U_j)||_0 + ||max(R_i+R_j, U_i+U_j)||_0
Inter_ij := ||F_i||_0 + ||F_j||_0 + ||F_i+F_j||_0
Total    = (Sum_edges [ReHop_ij + ImHop_ij + Inter_ij]) + (Sum_vertices Num_i)
```

(The paper's `⊕` means `+` for total, `max` for maximum weight — same
nested structure either way, so nothing here needs a separate "max mode.")

Their own released code's `Cre`/`Ciu` (in `map_cost`) do **not** actually
match these published equations — it double-counts one hopping bilinear and
drops another. For JW this happens not to matter (all four raw bilinear
weights per edge are numerically equal, a JW-specific symmetry), so the
buggy code grouping and the correct paper grouping sum to the same number.
Don't assume that symmetry holds once BK/parity/ternary tree are added.

### Closed form for JW under row-major

Every JW hopping bilinear between mode-index-separated-by-`d` positions has
weight `d+1` (all four of them, same symmetry as above); the quartic
interaction piece is always weight `2`, independent of `d`; `Num_i` is
always weight `1`. This gives:

```
Total = |V| + 4*Sigma_d + 8*|E|      (Sigma_d = sum over edges of |i - j|)
```

verified to reproduce the code's actual output exactly (`201, 448, 825,
4113` for `L=3,4,5,9`). Total is strictly increasing in `Sigma_d`, so
minimizing Total is exactly equivalent to minimizing `Sigma_d`.

### Comparison against Table I

Row-major throughout, via `hamiltonian(model="full")` + `score_majorana`:

| L | row-major total | published total | diff | row-major max | published max | diff |
|---|---|---|---|---|---|---|
| 3 | 201 | 237 | −36 | 4 | 4 | 0 |
| 4 | 448 | 512 | −64 | 5 | 5 | 0 |
| 5 | 825 | 909 | −84 | 6 | 6 | 0 |
| 6 | 1356 | 1460 | −104 | 7 | 7 | 0 |
| 7 | 2065 | 2189 | −124 | 8 | 8 | 0 |
| 8 | 2976 | 3104 | −128 | 9 | 9 | 0 |
| 9 | 4113 | 4277 | −164 | 10 | 11 | −1 |
| 10 | 5500 | 5632 | −132 | 11 | 12 | −1 |
| 11 | 7161 | 7389 | −228 | 12 | 14 | −2 |
| 12 | 9120 | 9320 | −200 | 13 | 15 | −2 |
| 13 | 11401 | 11609 | −208 | 14 | 16 | −2 |
| 14 | 14028 | 14364 | −336 | 15 | 18 | −3 |
| 15 | 17025 | 17601 | −576 | 16 | 20 | −4 |

**Max weight**: matches published exactly for `L=3..8` — explained by the
closed form (`L+1`) — then *beats* published from `L=9` on. Consistent with
their solver (30s time limit per instance, from their own code) failing to
find the true optimum as the search space grows.

**Total weight**: beats published at every size, gap growing with `L`.
Verified two independent ways for `3×3`: exhaustive search over all `9!`
orderings (true global minimum is `201`/`4`; `237` needs `Sigma_d=33`,
provably worse than the achievable `Sigma_d=24`), and the closed form
above. Also ruled out for `3×3`: periodic boundary conditions (worse,
`345`, still row-major-optimal), king-graph/diagonal connectivity (breaks
max immediately, `5` not `4`), optimizing hopping-cost alone before scoring
the full total (same row-major ordering, no change). For `4×4`, ran 30
independent 2-opt local searches (steepest descent + 15 random restarts,
both objectives) — none beat row-major's `(448, 5)`.

**Likely explanation for the total-weight gap**: their own QAP optimization
(`hexaly_qap`, from their released code) minimizes `B = Cre + Ciu` only —
hopping cost alone, excluding `Num`/`Inter` from the search objective (see
`test_weights()` in `hexaly_quadratic_assignment.py`) — so the paper likely
reports the full formula evaluated at an ordering optimized for a narrower
proxy, not the true joint optimum. Tested this for `3×3` (found the
hopping-only-optimal ordering, evaluated the full formula there) — it
happened to coincide with row-major for that one small case, so the number
didn't move, but larger `L` need not have that coincidence.

**Bottom line**: max Pauli weight is about as validated as possible short
of running their actual solver. Total Pauli weight is provably not worse
than published anywhere checked, and the evidence points to their published
total reflecting solver-search limitations rather than a provable optimum.
Treat our own numbers as the more trustworthy reference. `score_paper` as a
separate function was judged unnecessary — `score_majorana` +
`hamiltonian(model="full")` already reproduce their exact convention.

Also checked and ruled out as the source of Table I: the two Mathematica
notebooks in their GitHub repo (`adjacency matrices for cameron.nb`,
`_2.nb`) — both are about hexagonal/triangular lattices, unrelated to the
square-grid benchmark.

## Ordering sensitivity (Test 3): row-major beats snake

Found by direct computation, not derived in advance: it's `row_major`, not
`snake`, that gives every vertical hop weight exactly `Lx+1` — provably,
since `index(x,y+1) - index(x,y) = Lx` for every site under row-major.
Standard boustrophedon `snake` does *not* reduce max weight relative to
row-major — it only removes the row-wrap horizontal jump. Interior vertical
hops under snake range from weight `2` (at the column where the row
reverses) up to weight `2*Lx` (at the column farthest from it) — worse in
the worst case than row-major's uniform `Lx+1`. Whether snake still wins on
*total* weight (many low-weight edges against row-major's uniformly medium
ones) is a separate question, not checked.

## Corrections made to earlier docs

- `CONTEXT.md` originally described the Fermi–Hubbard metric as "real
  coefficients and no interaction terms" — backwards. Verified against the
  LaTeX source: `Fermi–Hubbard: D = ReHop + Inter` — it *includes* the
  interaction term, and excludes `Num` and `ImHop`. The paper's caption
  phrase "no operator terms" most likely means "no [number] operator
  terms" (`c_i = 0`), not "no interaction terms."
- `PLAN.md` §1.6 originally flagged `total = 4*Sigma_d + 8*|E| + M` as a
  failed reconstruction attempt ("must be wrong somewhere"). It wasn't
  wrong — see the closed form above. The premise that `237` was the
  achievable optimum was the actual error.

## `evaluate()` built ahead of Stage 2

`harness/evaluate.py`'s `evaluate(spec, encode_fn, terms)` was built during
Stage 1, not held for Stage 2 — nothing about it requires an untrusted
`encode_fn`, and every comparison above was, until it existed, this exact
chain hand-rolled inline in ad hoc scripts. `tests/test_evaluate.py`
confirms it reproduces the verified JW numbers and gates scoring on a
failed `verify()`.

## Second baseline: parity basis (`baselines/parity.py`)

Built via `harness/constructors.py`'s `from_linear_encoding(U)` — also
built ahead of Stage 2, since BK and ternary tree will need the same
general constructor with a different `U`. `U_parity` is lower-triangular
ones including the diagonal (the paper's own code names this `pb`, for
"parity basis" — same matrix, confirmed by feeding `from_linear_encoding`
the identity matrix and requiring it reproduce `baselines/jw.py`'s
hand-written mapping character-for-character, which only holds if the
`L` used internally (in `R = L @ F`, `P = R + F`) includes the diagonal —
PLAN.md's original eq. 18 note said "L strictly lower-triangular," which
this disproves).

The resulting structure is the expected JW dual: mode `i`'s X-support is
the shrinking suffix `{i,...,M-1}` (vs. JW's growing prefix `{0,...,i}`),
which pushes weight out of `Num` and into an X-string hopping term instead
of JW's Z-string.

Row-major, snake, and diagonal on the 3×3 grid give:

| ordering | total | max |
|---|---|---|
| row_major | 237 | 5 |
| snake | 233 | 7 |
| diagonal | 253 | 5 |

Snake beats row-major on total but loses badly on max — a real
metric-disagreeing tradeoff for this encoding, unlike JW where row-major
happened to win on both. (The `237` matching JW's *published* total is very
likely coincidence — different encoding, no mechanism connects them — not
a finding to lean on.)

**Update — exhaustively searched, via `evaluate()` (all `9!` orderings,
`verify()` included at each step, ~190s):** the true global optimum for
parity is `total=233` (achieved exactly at the `snake` permutation above,
confirmed no ordering beats it) and `max=5` (achieved exactly at
`row_major`, also confirmed optimal). So the two casual guesses above
weren't lucky — they really are each objective's true optimum, just at
*different* orderings, unlike JW where row-major is jointly optimal for
both.

**JW vs parity, both now exhaustively proven optimal, 3×3 grid:**

| | JW | parity |
|---|---|---|
| best total | **201** (row-major) | 233 (snake) |
| best max | **4** (row-major) | 5 (row-major) |

JW wins outright on both metrics at this size — consistent with the
paper's qualitative claim that JW is preferred for small grids, even
though our absolute numbers differ from theirs for the reasons documented
above.

## Third and fourth baselines: Bravyi-Kitaev and ternary tree

Both built via `harness/constructors.py`'s `from_linear_encoding(U)`, same
as parity — only `U` differs, built by `baselines/bk.py`'s Fenwick-tree
construction and `baselines/ternary.py`'s Sierpinski-tree construction
respectively (both cross-checked against arXiv 2504.21636's released code,
`hexaly_quadratic_assignment.py`'s `fenwick()`/`bk()` and
`sierpinski()`/`tt()`). Needed a new shared helper,
`harness/constructors.py`'s `transitive_closure(u)` (vectorized
Floyd-Warshall-style relaxation, `k` outermost) — verified against a plain
triple-loop on a random test matrix before trusting it.

Both pass `verify()` across a broad range of `M` (including non-power-of-two
and non-power-of-three sizes, since both constructions pad internally), and
both degenerate to exactly JW's mapping at `M=1`, as expected.

**BK's number-term weight has a clean closed form at exact powers of two**:
`ceil(log2(M)) + 1`, matching a perfectly balanced Fenwick tree's height —
verified exactly at `M = 1, 2, 4, 8, 16, 32, 64, 128`, and confirmed as a
valid upper bound at every non-power-of-two `M` tested (padding can only
shrink a mode's ancestor count relative to the fully-padded tree, never
grow it). Ternary tree does *not* have an equally clean closed form — its
recursion is asymmetric (the middle third's own children aren't wired
directly to the outer thirds, only through the middle's own representative
node), so its number-term weight grows log-like but not exactly
`ceil(log3(M)) + 1`; a generous `2*ceil(log2(M)) + 2` envelope holds at
every size checked (`tests/test_ternary.py`'s
`test_num_weight_grows_log_like`).

### Comparison against Table I (row_major/snake/diagonal, best-of-3)

```
bk total:       244, 531, 971, 1542, 2235, 3087, 4095, 5213, 6501, 7978, 9594, 11289, 13226
paper BK total: 304, 635, 1107, 1712, 2473, 3331, 4467, 5741, 7127, 8850, 10438, 12595, 14522
bk max:         5, 7, 9, 9, 11, 11, 12, 13, 13, 13, 14, 15, 15
paper BK max:   5, 7, 9, 9, 11, 11, 12, 13, 13, 13, 14, 15, 15

ternary total:       257, 532, 938, 1476, 2107, 2873, 3849, 4835, 5947, 7358, 8743, 10240, 12020
paper TT total:      313, 628, 1080, 1676, 2375, 3237, 4303, 5473, 6799, 8342, 9853, 11844, 13942
ternary max:         6, 6, 8, 10, 8, 9, 12, 10, 10, 12, 11, 11, 14
paper TT max:        5, 5, 7, 7, 8, 8, 9, 9, 9, 10, 10, 10, 11
```

BK's max weight matches published **exactly at every single size** (13/13)
and beats published total everywhere — as strong a confirmation as JW got.

TT's max weight, unlike every other encoding checked so far, is *worse*
than published at every size. Before trusting this, ran the same check
used to validate JW/parity at `3×3`: an exhaustive search over all `9!`
orderings, `verify()` included at every step.

```
true best total (3x3): 245, at permutation (0, 1, 2, 3, 6, 7, 4, 5, 8)
true best max   (3x3): 5,   at the same permutation
paper TT (3x3):        total=313, max=5
```

The true global optimum matches the paper's published max exactly (`5`)
and beats its total (`245` vs `313`) — same pattern as every other
encoding. So the earlier "worse at every size" result was an artifact of
`row_major`/`snake`/`diagonal` being poorly suited to a genuinely
tree-structured encoding (they were designed with linear-chain adjacency
in mind, which is the right fit for JW/BK/PB's cost structure but not for
TT's recursive-partition structure) — not a construction bug. TT is
correct; its max-weight numbers on the leaderboard, unlike the other three
encodings', likely have room to improve with a better-chosen ordering
(the leaderboard's own preamble already flags this as a general caveat of
the three-orderings-only methodology).

## Submissions declare their own ordering, instead of the harness searching three

The original leaderboard design (see the two sections above) had the
harness itself try all three built-in orderings per baseline and report,
independently, the best total and the best max. Checking each baseline's
full per-ordering breakdown (not just the best-of-three summary) surfaced
that this was quietly mixing runs:

```
jw:       row_major jointly optimal on both metrics at every size (closed form above)
parity:   row_major wins max at every size; snake wins total at every size
bk:       row_major wins max at every size; snake wins total at every size except 4x4, 8x8
ternary:  row_major wins max at every size; snake wins total at every size except 3x3 (tie), 9x9
```

So JW is the exception, not the rule: for parity/BK/ternary tree, the
leaderboard's reported (total, max) pair at a given size was never
actually achieved by any single ordering — total came from one run
(`snake`), max from a different one (`row_major`). That's not just
inelegant, it's dishonest as a benchmark number, and it's also the harness
doing a piece of the submitter's own optimization for them, which cuts
against this project's own frozen-referee design principle (see
`CLAUDE.md`).

Fixed by moving the ordering choice into the submission itself: `encode(spec)
-> mapping` is unchanged, but a submission may also define
`order(Lx, Ly) -> perm`; the harness builds `spec` from that (`row_major` if
none is declared) and scores exactly that one run, no search
(`harness/lattice.py`'s `build_spec`). `scripts/submit_baseline.py` and
`scripts/update_leaderboard.py` both do one evaluation per size now, not
three.

Since row_major/snake genuinely trade off for parity/BK/ternary tree (JW
alone doesn't), each is registered under *both* — `baselines/bk.py`
(`order = row_major`) and `baselines/bk_snake.py` (a thin wrapper reusing
`bk.py`'s `encode()`, `order = snake`), same pattern for `parity`/`ternary`
— so the tradeoff stays visible on the leaderboard (`BK (row-major)` vs.
`BK (snake)` as separate, independently-ranked rows) rather than being
picked once on the maintainers' behalf.

## Leaderboard regeneration caching

`scripts/update_leaderboard.py` used to re-evaluate every registered
baseline from scratch on every run, deliberately (see the earlier note
above) -- fine when every baseline was a cheap closed-form linear
encoding, but once submissions started doing real optimization internally
(`geo_ternary_anneal_ensemble`'s five independent simulated-annealing
restarts per size took ~7.5 minutes on its own), regenerating the whole
leaderboard for one new, unrelated baseline became genuinely slow.

Fixed with a fingerprint-gated cache (`.leaderboard_cache.json`,
gitignored -- local build state, not repo content): each baseline's
per-size `(total, max)` is cached against a hash of that baseline's own
source file, and a hash of every file in `harness/` gates the *entire*
cache at once. The harness-wide gate matters because a baseline's score
can depend on harness utilities its `encode()`/`order()` call into (e.g.
`harness.constructors.from_linear_encoding`), not just the scoring
functions proper -- there's no safe way to track "which harness files
affect which baseline" per-entry, so any change anywhere in `harness/`
invalidates every cached score at once rather than risking a stale one
that "looks" unaffected. The harness isn't expected to change going
forward, but the cache doesn't assume that.

Verified end to end, not just unit-tested: ran the real script twice.
First run (cold cache) took 7:33 and produced byte-identical output to
the pre-caching version; second run (warm cache, nothing changed) took
0.06s and was *also* byte-identical. `scripts/update_leaderboard.py`'s
`scored_with_cache` (the actual per-baseline hit/miss decision) is unit
tested with a call-counting fake `evaluate_baseline`, so a cache hit is
proven by "the expensive function was never called again," not just by
the returned numbers matching.

## Registry uniformity backfill

The four baselines registered before `--label` existed (`jw`, `parity`,
`bk`, `ternary`, plus their `_snake` siblings) had no `label` field in
`registry.json` at all -- the leaderboard's pretty names for them (`JW`,
`BK (row-major)`, etc.) came entirely from a separate hardcoded
`PAPER_ROW_FOR` override dict in `scripts/update_leaderboard.py`, not from
the registry. Backfilled `label` into `registry.json` for all of them
(the same strings `PAPER_ROW_FOR` used to supply) and removed
`PAPER_ROW_FOR` entirely -- every entry's display name now comes from the
same place, the registry's own `label` field, with no special-casing by
name.

Also backfilled `submitted_at` (each baseline's actual first-commit date,
pulled from `git log --follow --diff-filter=A`, not a fabricated "now") and
`generated_by` for every baseline registered before those fields existed,
so all eleven current registry entries share the exact same key set —
no entry's provenance is structurally distinguishable from another's by
"predates the tooling that would have recorded it." `generated_by` for
`geo_ternary`/`geo_ternary_opt`/`geo_ternary_anneal` specifically (submitted
before `submission.json` existed, so genuinely undocumented) was the
user's own call, not something independently verified.

Local-only complement: `inbox/_processed/<timestamp>_<name>/` archive
folders (matching the format `scripts/process_inbox.py` produces for a
real submission) were created for all ten pre-existing baselines too, so
every registered encoding — however it actually arrived historically —
has the same uniform local record.

## Shared "lessons learned" memory, ECDSA-style

Noticed while looking into this: `geo_ternary_opt.py`, `geo_ternary_anneal.py`,
and `geo_ternary_anneal_ensemble.py` all reference `solution/memory/max_weight_search.md`
/ `solution/memory/total_weight_search.md` in their docstrings, as if those
files exist. They don't — `solution/memory/` in this repo is empty (just a
`.gitkeep`). Whatever was actually tried building those three was local to
wherever they were generated and never became part of the shared repo;
only the docstring narrative survived. **Still unresolved** — the content
was never sent to us, so it can't be reconstructed without fabricating
it. If the original files ever turn up, add them by hand to
`baselines/geo_ternary_opt.memory/` / `baselines/geo_ternary_anneal.memory/`
the same way the registry backfill above was done for other metadata.

ecdsa.fail's own answer to "how do future contestants learn from past
attempts" (confirmed from their README): `src/point_add/memory/` is
shared, git-tracked, and accumulating — contributors add notes as they
iterate, committed as real repo history, with an explicit caveat:
*"memory and source files may come from different agents. Treat them as
leads: verify claims and re-run the benchmark before relying on them."*

Adapted rather than copied exactly, since the structural fit differs:
ECDSA has one continuously-evolving solution with one shared memory pool;
this repo has many independently-authored, permanently-named baselines.
So memory here is scoped **per baseline** — an optional `memory/` folder
in a submission (`inbox/README.md`), carried by `scripts/process_inbox.py`
into `baselines/<name>.memory/` on acceptance (purely additive; doesn't
touch `verify()`/`check_at_size`/registration at all) — rather than one
shared pool, but keeps ECDSA's actual properties: committed, permanent,
optional, and explicitly "leads not proven fact."

Discoverability without cluttering `LEADERBOARD.md`'s cells (an explicit
prior preference — see the earlier `generated_by` note): a separate
generated `MEMORY.md`, written by `scripts/update_leaderboard.py`
alongside the score tables, listing only baselines that actually have a
`.memory/` folder — nothing for the rest, no "no notes" filler rows.

## Table III was investigated and abandoned; the graph challenge targets Table II instead

An earlier design of the graph challenge targeted arXiv 2504.21636's
**Table III** (`\label{tab:stab}`, ancillas allowed, `D = ReHop + ImHop`
only, a "JW + 10 ancillas" reference row). Investigating whether
`harness/verify.py` correctly checks stabilizers (it doesn't implement
checks 2-4 at all -- see below) turned up something more fundamental:
Table III's own numbers come from a construction (`sec:constantancillas`
in their LaTeX source) that multiplies individual Hamiltonian *terms* by a
per-edge-independently-chosen factor ("Option 1" vs "Option 2", picked per
edge to minimize weight) -- this is not expressible as one fixed Majorana
generator per mode, which is what `mapping["majoranas"]` requires. No
submission, however good, could ever reach parity with those numbers in
our current submission format. Went as far as scoping a genuinely
stabilizer-based redesign (targeting Derby-Klassen arXiv 2003.06939 and
Verstraete-Cirac J. Stat. Mech. 2005 P09012 instead, which do use real
stabilizer codes) before deciding it added too much complexity for now.
Decision: drop ancillas from this challenge entirely, and target Table II
instead, which needs no schema change at all.

Also confirmed while investigating: `harness/verify.py` only implements
checks 0 (well-formed) and 1 (Majorana algebra) -- checks 2-4 (stabilizers
abelian / compatible / codespace dimension), fully specified in `PLAN.md`
§1.5 since Stage 1, were never written (deferred back then because nothing
used ancillas yet). `mapping["stabilizers"]` is hard-coded `[]` everywhere
in the repo. This remains true and unexercised -- nothing in the graph
challenge (ancilla-free, as of this decision) needs it.

## Table II verification (graph challenge)

arXiv 2504.21636's **Table II** (`\label{tab:graphs}` in the LaTeX source)
is the reference for `LEADERBOARD_GRAPHS.md`. Verified directly against
the LaTeX (not paraphrased): caption is "Total Pauli weight
$(\mathcal{D} = \text{Num} + \text{ReHop} + \text{ImHop} + \text{Inter})$
for fermionic systems of various Hamiltonian graphs with 64 vertices using
the optimized fermionic label ordering for the Jordan–Wigner and Ternary
Tree transformations" -- the same metric already used for the
square-lattice challenge, ancilla-free. Full numbers:

```
                        JW     TT
Hex-Lattice            7564   5489
Tri-Lattice            2384   2478
Periodic Hex-Lattice   8584   4794
Periodic Tri-Lattice   2704   2356
Random 3-Regular       2888   2245
Margulis Gabber Galil 11784   6543
Chordal Cycle          6976   4431
```

Only the first four (genuine lattice types) are implemented
(`harness/graphs.py`) — the last three are specific graph *instances* from
the paper's own generation (a particular random seed, a particular
expander construction), not reproducible without their released code
([`github.com/cameton/QCE_QubitAssignment`](https://github.com/cameton/QCE_QubitAssignment)).

**Reproducibility caveat, confirmed empirically, not just anticipated**:
our own JW baseline on `harness/graphs.py`'s hex/triangular lattices at
M=64 lands in the same ballpark as the paper's numbers (thousands) but
doesn't match exactly -- e.g. hexagonal at the pinned `CANONICAL_SHAPE`
`(8, 4)`: our JW total=2416/max=16, vs. the paper's JW=7564. The paper's
caption only says "64-mode system graph"; it doesn't state the exact
`(Lx, Ly)` shape or aspect ratio used, and our canonical ordering
(row-major over unit cells) isn't necessarily theirs either. Not treated
as a bug -- `PAPER_TABLE2` in `scripts/update_leaderboard.py` is included
as a fixed reference row alongside our own submissions, same pattern as
`PAPER_TOTAL`/`PAPER_MAX`, not as something our own construction is
expected to reproduce exactly.

### Aspect-ratio gaming and the `CANONICAL_SHAPE` fix

Unlike square lattices, `M` does **not** determine the graph for these
lattice types -- e.g. hex-lattice `Lx=8,Ly=4` and `Lx=16,Ly=2` both give
`M=64` but have different edge counts/boundary structure, hence different
achievable weight. Gating the "vs. Table II" comparison on "M=64" alone
would let a submission pick whichever aspect ratio happens to be easiest
to encode well while still nominally qualifying as "the 64-mode
benchmark" -- a comparison-integrity gap, not a verifier-security one (a
submission can't alter which edges exist; it can only choose which shape
to report against the paper).

Fixed by: (1) `submission.json`'s `sizes` field, for graph-type
submissions, is an explicit comma-separated list of `LxxLy` pairs
(`"8x4,15x15"`), not a single swept integer -- see `parse_shapes`/
`validate_shapes` in `scripts/submission_lib.py`; (2) each graph type gets
exactly one `(Lx, Ly)` pinned as `CANONICAL_SHAPE` in `harness/graphs.py`
(`hexagonal`/`periodic_hexagonal`: `(8, 4)`; `triangular`/
`periodic_triangular`: `(8, 8)` -- chosen only to hit `M=64` exactly, not
verified to match the paper's own undisclosed split -- these values
carried over unchanged from the Table III design, since they were never
about matching a specific paper table, just about hitting M=64); (3) a
submission's score only shows up next to the paper's `[1]` rows when its
shape is an *exact* match to `CANONICAL_SHAPE` -- any other shape a
submission claims still scores and appears, just in a separate "Other
shapes" table, not lined up against the paper. The same `is_showcased()`
rule also now governs the square-lattice challenge's own table (see
below), so both challenges share one mechanism for "scored and cached
always, shown only if showcased."

**Redesign history, briefly (each superseded the last -- this is not the
current layout, see the next paragraph for that):** `LEADERBOARD_GRAPHS.md`
originally rendered one small table per graph type (four separate
sections, each with its own "vs. Table II"/"Other shapes" sub-tables).
First consolidated into one pair of rank-based tables with the four
lattice types as *columns* (mirroring `LEADERBOARD.md`'s shape, but
columns = graph type instead of size). That in turn was replaced by the
sweep-based design below, once it became clear a size *sweep* per lattice
type (not a single canonical-shape column) was wanted, matching
`LEADERBOARD.md` far more closely.

**Current layout: one pair of ranked tables (total, max) per swept graph
type** (Tri-Lattice 3x3..8x8, Hex-Lattice 3x3..8x8 --
`GRAPH_SWEEP_SIZES` in `scripts/update_leaderboard.py`; both capped at the
same numeric value, deliberately, not a qubit-count-matched one -- see
"Sweep range capped at 8x8" below for why -- so hexagonal's top qubit
count, 128 (`M = 2*Lx*Ly`, two sites per unit cell), ends up double
triangular's, 64), columns = that type's own `Lx = Ly` sizes, built via
`graph_sweep_entries`/`graph_paper_entries`/`graph_sweep_column_labels`
feeding the same `render_ranked_table` the square-lattice challenge uses.
Periodic Hex-Lattice/Periodic Tri-Lattice have no sweep defined -- not
shown in a table, though still fully submittable/scored/cached, same as
any other `is_showcased()`-excluded shape; any shape claimed for them
lands in the shared "Other shapes" table (`graph_other_shapes`) alongside
off-square/out-of-range shapes for the two swept types.

Because Hex-Lattice has two sites per unit cell (`M = 2*Lx*Ly`), its own
paper-comparison shape `(8, 4)` is never `Lx = Ly` -- it has no column in
an `Lx = Ly`-only sweep. Tri-Lattice's `(8, 8)` (`M = Lx*Ly`, same
formula as the square lattice) *is* `Lx = Ly`, and lands exactly at
column `L=8`. So: Tri-Lattice's tables get a real `[1]`-linked Table II
reference row; Hex-Lattice's don't (`graph_paper_entries` returns `[]`
when the canonical shape isn't `Lx = Ly` or falls outside the sweep --
not a fabricated placement). This is also why the progress-over-time
chart (`write_graph_progress_chart`, `assets/progress_triangular_weight.png`)
is Tri-Lattice only, at `target_size=8`: it's the one graph type where
"our own JW" and "the paper's own number" sit at the same, real column,
mirroring the square-lattice chart's own JW-vs-Table-I comparison
exactly. Reference baselines `jw_triangular`/`tt_triangular`/
`jw_hexagonal`/`tt_hexagonal` (thin `from baselines.jw/ternary import
encode` re-exports, registered via `scripts/submit_baseline.py` --
deliberately *not* hand-edited into `registry.json`, per this project's
own rule) give each sweep table real, ranked content from the start,
exactly like `jw`/`parity`/`bk`/`ternary` already do for the square
challenge -- no custom `order()`: `harness.graphs.build_spec` falls back
to each lattice type's own canonical default when none is declared,
which is `jw.py`/`ternary.py`'s own square-specific `order()` would in
fact be the *wrong length* for hexagonal (`M = 2*Lx*Ly`, not `Lx*Ly`) if
imported directly -- see `baselines/jw_hexagonal.py`'s docstring.

**Sweep range capped at 8x8 (both types), superseding an earlier
15x15/10x10 split.** The sweep initially went to Tri-Lattice 3x3..15x15,
Hex-Lattice 3x3..10x10 -- chosen to keep top qubit counts "roughly
comparable" (225 vs. 200) given hexagonal's `M = 2*Lx*Ly` grows twice as
fast as triangular's `M = Lx*Ly`. Revisited because, unlike the
square-lattice sweep (whose top size, 15x15/225 qubits, only ever runs
against the harness's own fixed baselines), a graph-challenge submission's
`encode()` can do real optimization work of unknown cost -- nothing bounds
how expensive verifying the largest swept shape gets. Capped both types
down to a uniform 3x3..8x8 instead: deliberately the *same* numeric cap,
not a re-balanced qubit-count-matched pair (that would just reproduce the
same problem at smaller numbers) -- accepted the resulting asymmetry
(Hex-Lattice reaches 128 qubits at `8x8`, double Tri-Lattice's 64) for how
much simpler "both sweep 3x3..8x8" is to state and explain than two
different numbers. `CANONICAL_SHAPE` (the paper-comparison point gating
`[1]` rows) is untouched by this -- still `(8, 4)` for hexagonal/
periodic_hexagonal and `(8, 8)` for triangular/periodic_triangular, and
still the only shape gated against Table II.

Two real bugs found and fixed while building this (both by actually
rendering the chart and looking at the PNG, not just eyeballing the
code): (1) `scripts/submit_baseline.py` never stamped a `submitted_at`
timestamp (unlike `scripts/process_inbox.py`), so the four reference
baselines above initially had `submitted_at: None` and silently vanished
from the chart's reference-line lookup (`graph_dated_totals` correctly
skips undated entries -- a chart can't place one -- but that meant the
red "JW" line just never appeared, no error, nothing to notice unless you
looked at the actual image). Fixed by stamping `submitted_at` in
`submit_baseline.py` too, then re-registering with `--force`. (2)
`render_progress_chart` (`scripts/progress_chart.py`) rendered a
nonsensical, backwards-reading date axis when `points` was empty (no
registered graph-challenge baseline yet) -- matplotlib's date-axis
autoscale has no real domain to anchor to with nothing plotted on it.
Fixed by skipping the date-locator/formatter entirely and showing a plain
"No submissions yet" placeholder axis (centered vertically, to avoid
landing on top of whichever reference line happens to sit near the
middle of the y-range) when `points` is empty, leaving the reference
lines (which draw regardless of `points`) as the only real content.

## Rectangular submissions for the square-lattice challenge

The square-lattice challenge's `sizes` grammar (`validate_mixed_sizes` in
`scripts/submission_lib.py`) now also accepts explicit `LxxLy` rectangle
pairs mixed in with its original plain-integer/range syntax (`"3-15,8x12"`)
-- a submission can claim an off-square shape, which gets verified,
scored, and cached exactly like any other, but doesn't appear in
`LEADERBOARD.md`'s ranked tables (a strict `Lx = Ly`, `3..15` grid,
unchanged). Whether a given `(graph, Lx, Ly)` shows up anywhere is decided
by one function, `is_showcased()` in `scripts/update_leaderboard.py` --
the single place to add a new showcased shape later without touching how
scoring/caching works. Backward compatibility was the binding constraint:
an all-integer `sizes` string parses identically to before
(`validate_mixed_sizes("3-15") == validate_sizes("3-15")`, tested
directly), so registry.json's pre-existing plain-int entries, and their
score-cache hits, are completely unaffected.

## The ancilla/stabilizer challenge (LEADERBOARD_ANCILLAS.md)

Built on top of the `harness/v2` extension (stabilizer verification,
certified stabilizer-dressed scoring -- see the git history for the
extension's own phased build-out; CLAUDE.md's "The ancilla/stabilizer
challenge" section has the durable rules). This section covers the
design decisions specific to turning that harness extension into an
actual player-facing challenge with its own leaderboard.

**The challenge is deliberately the opposite framing from Challenge A/B in
the original extension-planning doc** (which proposed "minimize ancillas
at fixed weight" as one of *two* possible challenges, the other being
"minimize weight at a fixed ancilla budget" -- see
`harness/v2/challenges.py`, which still implements both generically). Only
the first is actually surfaced as a real challenge with a leaderboard: fix
`max_weight <= 3` (the smallest weight Derby-Klassen's own paper achieves,
and a natural, meaningful target rather than an arbitrary number), minimize
`n_ancillas`. `scripts/run_challenge.py`'s `weights` subcommand and
`run_min_weight_challenge()` still exist and work, just aren't wired into
any leaderboard yet -- a natural extension if a second track is wanted
later.

**Sizes: each lattice type reuses its own existing challenge's range**,
not a new number invented for this challenge -- square sweeps `3x3..15x15`
(`LEADERBOARD.md`'s own `SIZES`), hexagonal (once it has a working
reference -- see below) would sweep `3x3..8x8`
(`GRAPH_SWEEP_SIZES["hexagonal"]` from the graph challenge). Simpler to
state and justify than inventing a third number, and consistent with how
this repo has always picked sweep ranges (see the graph challenge's own
"both capped at 8x8" reasoning in CLAUDE.md).

### Derby-Klassen, square lattice: reconstructed from the actual paper

`harness/v2/baselines/dk.py` was built by fetching and reading arXiv
2003.06939's PDF directly (including Figures 1-3), not from memory or a
lossy text extraction -- per CLAUDE.md's rule against reconstructing a
paper's construction from prose alone when the primary source is
checkable. The module's own docstring has the full breakdown of what's
paper-sourced (Eq. 7-9, the checkerboard face coloring, the corner-Majorana
rule, Table I's weight claims) versus this implementation's own completion
(the concrete row/column-uniform edge-orientation rule, and the L-shaped
spanning path used to build one global Majorana per vertex from the
paper's edge operators). Empirically verified against the harness itself
at every tested "case I" size (Supplementary Material's term for when the
full `M`-mode Fock space is represented, not a restricted or extended
one -- requires `Lx`, `Ly` not both even): `verify_extended` passes,
qubit count stays under the paper's claimed `1.5x`-per-mode bound
(reaching `1.44x` at `15x15`), and `represent()` reproduces Table I's
*exact* claimed weights (`max_rehop=3`, `max_imhop=3`, `max_num=1`,
`max_int=2`) via closed-form identities derived from the paper's own
relations (`gammabar_j = i*gamma_j*Z_j`, itself following from
`V_j := -i*gamma_j*gammabar_j = Z_j`), not search. Both-even sizes are
rejected with a clear, documented error rather than silently
misrepresenting a different Hilbert space as the full one.

Registered at exactly the odd sizes it can actually claim (`3,5,7,9,11,
13,15` -- every even `L` gives `Lx=Ly=L` both even, hence case II/III),
so `LEADERBOARD_ANCILLAS.md`'s square table has real gaps at even columns
until some other submission fills them in -- same "a size-scoped
submission just doesn't appear for sizes it doesn't claim" handling
`render_ranked_table` already has everywhere else.

### Hexagonal Derby-Klassen: investigated and not yet solved

Attempted a `harness/v2/baselines/dk_hexagonal.py` analogous to the square
one, using the paper's own Supplementary Material section ("HEXAGONAL
LATTICE MAPPING", read directly from the PDF including its Figure 2): a
qubit at *every* face (no even/odd split -- "there are no trivial cycles"
for hexagons, unlike the square lattice), edges oriented "clockwise on
even columns of faces, counterclockwise on odd", with the bottom edge of
each hexagon carrying a `Y_f` face factor and its two cycle-neighbours
carrying `X_f`.

Derived the face structure combinatorially from `harness.graphs.hex_lattice`'s
own stated bond directions (confirmed correct: the hexagonal face anchored
at unit cell `(x, y)` is the 6-cycle `A(x,y)-B(x,y)-A(x,y+1)-B(x-1,y+1)-
A(x-1,y+1)-B(x-1,y)`, verified edge-by-edge), and built an explicit pixel
embedding (`A(x,y)` at `(2x, y)`, `B(x,y)` at `(2x+1, y)`) to determine
genuine clockwise/counterclockwise via the shoelace formula, rather than
guessing.

**The actual obstacle**: for the square lattice, only one of the two faces
neighbouring any given edge is ever "even" (the checkerboard-odd one
contributes nothing), so only one face's orientation choice ever actually
mattered for that edge -- the delicate part of that construction (see
`harness/v2/baselines/dk.py`'s own docstring) never had to reconcile two
independent votes. Hexagonal gives *every* face a real stabilizer, so
*both* neighbours of a shared edge "vote" on its orientation via their own
column-parity rule. Two faces sharing an edge, each genuinely tracing its
own boundary clockwise, always induce *opposite* raw directions on that
edge (confirmed via the pixel embedding) -- for two *vertically-stacked*
faces (same column, hence the *same* clockwise/counterclockwise choice
under the paper's own column-based rule), reversing both of two already-
opposite votes by the same amount never reconciles them. Confirmed
empirically: `verify_extended` reported a genuine, unconditional edge
orientation conflict (`face(1,0)`'s and `face(1,1)`'s independent
assignments of the shared edge `A(1,1)-B(0,1)` always disagreed,
regardless of which column-parity convention was tried).

A simplified fallback (orient every edge uniformly from its `A`-endpoint
to its `B`-endpoint, sidestepping the whole column-parity question) is
*not* a valid substitute, and this is the more important finding: unlike
the square lattice, where the algebra backbone construction is somewhat
forgiving (any fixed, self-consistent choice works, since the delicate
part is entirely in the stabilizers), orientation for hexagonal directly
determines whether the *Majorana anticommutation algebra itself* holds --
the naive uniform rule produced 336 check-1 violations at `3x3`. At every
degree-3 vertex, by pigeonhole, at least two of its three incident edges
must share the same tail/head role there; for those two to still
anticommute (Eq. 4-5's requirement), the face-qubit factors have to pick
up the slack -- exactly the kind of three-way vertex/edge/face interaction
the paper's careful column-alternating rule is presumably designed to get
right, and which isn't a free choice the way it looked for the square
lattice.

**What would actually resolve this**: either recovering the paper's true
geometric intent for "column" in a way that reconciles vertically-stacked
faces (most likely: the correspondence between `harness.graphs.hex_lattice`'s
`(x, y, sublattice)` labels and the paper's own drawn geometry isn't the
one assumed here), or a genuine per-vertex constraint-satisfaction
derivation of edge roles from Eq. 4-5 directly, rather than trying to
reverse-engineer "clockwise on even columns" as a shortcut to it. Given
the depth of the obstacle, this was deliberately not pursued further for
now -- see CLAUDE.md's own pointer for what adding it later would involve
(a new baseline module, registered the same way, plus a hexagonal
table/chart in `scripts/update_leaderboard_ancillas.py` -- no
rearchitecture needed once the construction itself is right).

### The weight cap became a submission choice, with per-cap boards

The challenge originally hard-coded `max_weight <= 3` (`ANCILLA_MAX_WEIGHT`).
That was wrong in an interesting way: the object worth studying here is the
*locality/ancilla trade-off curve*, and a fixed cap only ever shows one point
on it. The cap is now `"max_weight"` in `submission.json`, any positive
integer, defaulting to 3 so every manifest and registry entry written before
the field existed keeps its exact meaning.

**Boards rank on the ACHIEVED weight, not the claimed cap** -- the one design
decision here worth stating explicitly, because the obvious alternative
(bucket each entry onto the board matching what it claimed) is subtly wrong.
An encoding reaching weight 3 everywhere belongs on the weight-4 board too:
"how few ancillas if you're allowed weight 4" is only answered honestly if
weight-3 constructions count. So the claimed cap is purely an *acceptance
gate* (checked at every claimed size, no partial credit), while board
membership is recomputed from what the encoding actually achieved. A
consequence worth keeping: claiming a generous cap can never cost an entry a
place on a tighter board it would otherwise have earned.

That's also why the per-size score cache stores the achieved weight next to
`n_ancillas`. Cache entries written before per-track ranking existed have
only `n_ancillas`, and are deliberately treated as a *miss* and recomputed --
inferring the weight from the claimed cap would silently mis-file a tight
encoding onto only the loose board, which no test would catch because the
number itself would look plausible.

Currently showcased: caps 3 and 4 (`ANCILLA_SHOWCASED_MAX_WEIGHTS`). Derby-
Klassen anchors both. It's a genuinely open target on the weight-4 board,
not a formality: per the DK paper's own Table I, the published weight-4
constructions ([10,11] at `2L^2` qubits, [15] at `2L(L-1)`, [14] at `3L^2`)
all use *more* qubits than DK's `1.5L^2 - L` at weight 3, so nothing in the
literature yet exploits the looser cap to spend fewer ancillas.
