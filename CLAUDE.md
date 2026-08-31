# encoding-bench

Read `CONTEXT.md` (problem/background) and `PLAN.md` (staged implementation
plan) before doing any work here. This file is durable guidance that doesn't
change as the code does — it does not restate what's already in those two.
`NOTES.md` is a third document, an investigation log (findings, ruled-out
hypotheses, corrections) — check it before re-deriving something that may
already be settled there, but don't move plan content into it or log
content back out of it; the split is deliberate (see below).

## Docs organization — keep the split

Three markdown files, three different jobs. Don't blur them:

- `PLAN.md` — the staged plan: what to build, in what order, the specs and
  contracts. Should stay short enough to scan. If you're about to add a
  paragraph documenting a finding, a ruled-out hypothesis, or a bug you just
  fixed, it goes in `NOTES.md` instead, with only a one-line pointer left in
  `PLAN.md`. (`PLAN.md` grew to 545 lines once before by not doing this —
  half of it was an accumulated investigation log crowding out the actual
  plan. Split back out into `NOTES.md`; don't let it happen again.)
- `NOTES.md` — the investigation log. Free to grow. Organize by topic, not
  strictly chronologically, and prefer a clean/deduplicated writeup of what
  was found over a blow-by-blow "first I thought X, then Y" transcript —
  that history already exists in conversation logs if it's ever needed.
- `CLAUDE.md` (this file) — durable rules that should shape behavior in
  *every* future session: traps, conventions, frozen/editable boundaries.
  Not findings, not a plan — just the load-bearing rules a finding produced.

## Frozen vs editable

- `harness/` and `baselines/` are **frozen** once Stage 1 is signed off. Do
  not modify them to make a submission pass — that defeats the point of a
  trusted referee. One exception within `baselines/`: a `<name>.memory/`
  folder (an accepted submission's optional notes on what was tried,
  ECDSA-style shared memory — see `NOTES.md`) is committed alongside its
  baseline but isn't part of the "frozen, trusted" property everything
  else there has. It's unverified prose a submitter chose to write, not
  code the harness runs or `verify()` ever looks at — don't trust a
  baseline's memory notes over its own actual behavior.
- `solution/` is the only editable directory, and only from Stage 2 onward.
- `inbox/` is a maintainer-facing staging area for external submissions
  (gitignored except `inbox/README.md`) — not part of the frozen/editable
  contract a challenge player interacts with. It only changes via
  `scripts/process_inbox.py`, which never writes to it or to `baselines/`
  unless a submission already passes `verify()` at every size it claims.
- If a change to `harness/` or `baselines/` seems necessary, stop and flag it
  explicitly rather than making it quietly — it means either a real bug in
  the referee (rare, high-stakes) or a submission trying to game it (assume
  this first, per `CONTEXT.md` §5 "verifier-gaming is real, not hypothetical").

## Stage gating

Stage 2 (agent-written `solution/encode.py`) does not begin until Stage 1's
four tests (`tests/test_chain_analytic.py`, `test_rejection.py`,
`test_ordering.py`, `test_table1.py`) all pass. Test 4 (Table I reproduction)
is the gate — it's checked last because it's the most expensive and the
least self-contained (depends on `github.com/cameton/QCE_QubitAssignment`).

Within Stage 1, tests run in order 1 → 2 → 3 → 4. Test 1 (analytic 1D chain)
failing means the symplectic machinery itself is broken — fix that before
looking at anything else.

## Traps (see PLAN.md for detail)

1. **XOR, never OR**, for combining Pauli bit-vectors into a product. OR
   silently makes Jordan–Wigner look much worse than it is.
2. **Stabilizer compatibility (check 3) is "signature constant over all
   Majoranas"**, not "anticommutes with an even number of them" — the latter
   is strictly weaker and passes invalid stabilizers (counterexample in
   PLAN.md §1.5).
3. **Don't reconstruct the paper's (2504.21636) cost model from prose alone
   — but their released code isn't automatically ground truth either.**
   Their code's `Cre`/`Ciu` (in `map_cost`, `hexaly_quadratic_assignment.py`)
   do not actually match their own published equations (verified against the
   arXiv LaTeX source directly) — for JW this happens not to matter, because
   a JW-specific symmetry makes the code's buggy grouping and the paper's
   correct grouping sum to the same number, but don't assume that holds for
   other encodings. When in doubt, pull the LaTeX source and read the actual
   equations (`NOTES.md` has the full derivation) rather than trusting
   either the prose or the code alone.
4. **Vectorize the commutation check** (`G @ Lambda @ G.T mod 2`). The O(M²)
   Python double loop is a real bottleneck once search starts.
5. A 1D chain is a unit test, not a benchmark — Jordan–Wigner is already
   optimal there.
6. **Total Pauli weight doesn't deduplicate identical Pauli strings across
   term categories.** A vertex of degree `k` has its number-term operator
   counted `k+1` times (once explicitly, once more inside each incident
   edge's interaction-term expansion) — that's the metric's definition, not
   a bug. Don't "fix" it when implementing scoring for a new encoding.
7. **A single edge's hopping term is 2 terms at the fermionic-operator level
   but up to 4 at the Pauli-string level** (2 if the hopping coefficient is
   purely real or purely imaginary, 4 if genuinely complex) — substituting
   `A_i = (gamma_i + i*gammabar_i)/2` turns each of the 2 operator-level
   terms into a 2-term sum, and combining them via the Majorana
   anticommutation relations collapses the naive 4+4=8 back down to 4, not
   8. Number and interaction terms stay real-only and need no such split —
   `A_i^dag A_i` and `A_i^dag A_i A_j^dag A_j` are each Hermitian on their
   own, so Hermiticity forces their coefficients real.

## Submission shape (Stage 2+)

`encode(spec) -> mapping` must be one uniform rule — no branching on `M`,
`Lx`, `Ly`, no size-keyed tables. This is enforced by evaluating on held-out
sizes, not by code review, so don't rely on a submission "looking" uniform.

The same constraint applies to the optional companion `order(Lx, Ly) ->
perm` (a submission's declared mode ordering — see `harness/lattice.py`'s
`build_spec`, and NOTES.md's "Submissions declare their own ordering" for
why the harness stopped searching orderings itself). It must be a genuine
formula in `Lx, Ly`, like the three built-in orderings it can be built
from (`row_major_perm`/`snake_perm`/`diagonal_perm`) — not a lookup table
keyed to specific sizes the submitter happens to know are tested.

**Same rule for the graph challenge** (`LEADERBOARD_GRAPHS.md`, non-square
graphs — see `harness/graphs.py`): each graph type ships exactly one
canonical default ordering, and the harness performs no search over
orderings there either. A submission's own declared `order()` must be a
genuine formula, not a table keyed to specific sizes, same as the
square-lattice challenge. Both challenges score the identical
`D = Num + ReHop + ImHop + Inter` metric — the graph challenge is not a
different metric, just different graphs.

**The graph challenge's `sizes` grammar needs explicit `LxxLy` pairs; the
square-lattice challenge's optionally accepts them too, mixed with its
original plain-integer syntax.** Square-lattice `sizes` (`validate_mixed_sizes`
in `scripts/submission_lib.py`) still accepts a plain integer or range
(`"3-15"`, meaning `Lx = Ly`) as it always has, and can *additionally* mix
in explicit `"LxxLy"` pairs in the same comma-separated string (`"3-15,8x12"`)
for an off-square rectangle. Graph-challenge `sizes` (`validate_shapes`) is
always explicit `LxxLy` pairs, no plain-integer shorthand, because for
these lattice types **mode count `M` does not determine the graph** —
e.g. hex-lattice `Lx=8,Ly=4` and `Lx=16,Ly=2` both give `M=64` but are
structurally different graphs (different edge counts/boundary structure).

**Every claimed shape/size, for either challenge, is verified, scored, and
cached — whether or not it ever appears in a rendered table.** What's
*shown* is decided by exactly one function, `is_showcased(graph, lx, ly)`
in `scripts/update_leaderboard.py`: for `"square"`, an exact `Lx == Ly`
within the leaderboard's `SIZES` range (today's 3x3..15x15, arXiv
2504.21636 Table I); for every other graph type, an exact match to that
type's `CANONICAL_SHAPE` (`harness/graphs.py`, arXiv 2504.21636 Table II's
64-mode instances). Gated on the *exact* shape, not on matching `M`, for
the graph types: gating on `M` alone would let a submission pick whichever
aspect ratio is easiest to encode well while still nominally "matching"
the paper at the same mode count. A submission at any other shape/size
still gets scored and cached, and (on the graph-challenge side) shown in
a separate "Other shapes" table below the ranked ones — just never lined
up against `[1]`, and (on the square-lattice side) not shown anywhere
yet. This is the single place to touch when showcasing a new shape later
(a wider square range, a second canonical hex shape, a new graph type) —
not a rendering rewrite.

`LEADERBOARD_GRAPHS.md` mirrors `LEADERBOARD.md`'s own layout (rank-based
rows, `render_ranked_table`), just with columns = the four lattice types
(at each one's `CANONICAL_SHAPE`) instead of columns = lattice sizes —
one shared function, not a second table-rendering implementation.

## Conventions

- Python, `numpy` for the harness. `pytest` for tests. `openfermion` is a
  Stage-1+ dependency for differential testing only (deferred until the small-
  `M` spectrum check is added — see PLAN.md "Deferred, deliberately").
- The verifier (`harness/verify.py`) **never raises** on malformed input; it
  returns a structured result dict describing what failed.
- Report metrics as a vector (`total_weight`, `max_weight`, `avg_weight`,
  `n_qubits`); never collapse them into one scalar (e.g. `N × weight`) — see
  PLAN.md §1.6 for why.
- Every new `baselines/*.py` module needs an entry in `baselines/registry.json`
  (`{"name": {"module": ..., "sizes": [...], "label": ...}}`, read by
  `baselines/__init__.py` into `BASELINES`) so cross-encoding comparisons
  (Test 4, the leaderboard, and any future sweep) can loop over all
  baselines by name instead of importing each module by hand. Never
  hand-edit `registry.json` directly — `scripts/submit_baseline.py` (one
  file, by hand) and `scripts/process_inbox.py` (a batch from `inbox/`,
  fully automated) both write it only after confirming a submission passes
  `verify()` at every size it claims, via the shared logic in
  `scripts/submission_lib.py`.
- `run.py evaluate --solution ... --lx ... --ly ...` is the actual
  contributor-facing entry point (modeled on `ecdsafail run --note`) — it
  loads an `encode(spec)` from any file path, runs it through `evaluate()`,
  and appends a row to `results.tsv`. Don't re-invent this ad hoc in a
  script; extend it if it's missing a flag you need. `run.py verify` is the
  separate raw-JSON debug path, unrelated to scoring a submission.
