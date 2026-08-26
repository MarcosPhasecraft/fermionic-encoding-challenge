# encoding-bench

Read `CONTEXT.md` (problem/background) and `PLAN.md` (staged implementation
plan) before doing any work here. This file is durable guidance that doesn't
change as the code does — it does not restate what's already in those two.

## Frozen vs editable

- `harness/` and `baselines/` are **frozen** once Stage 1 is signed off. Do
  not modify them to make a submission pass — that defeats the point of a
  trusted referee.
- `solution/` is the only editable directory, and only from Stage 2 onward.
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
3. **Never reconstruct the paper's (2504.21636) cost model from prose.** Use
   their released code as ground truth for Table I calibration.
4. **Vectorize the commutation check** (`G @ Lambda @ G.T mod 2`). The O(M²)
   Python double loop is a real bottleneck once search starts.
5. A 1D chain is a unit test, not a benchmark — Jordan–Wigner is already
   optimal there.

## Submission shape (Stage 2+)

`encode(spec) -> mapping` must be one uniform rule — no branching on `M`,
`Lx`, `Ly`, no size-keyed tables. This is enforced by evaluating on held-out
sizes, not by code review, so don't rely on a submission "looking" uniform.

## Conventions

- Python, `numpy` for the harness. `pytest` for tests. `openfermion` is a
  Stage-1+ dependency for differential testing only (deferred until the small-
  `M` spectrum check is added — see PLAN.md "Deferred, deliberately").
- The verifier (`harness/verify.py`) **never raises** on malformed input; it
  returns a structured result dict describing what failed.
- Report metrics as a vector (`total_weight`, `max_weight`, `avg_weight`,
  `n_qubits`); never collapse them into one scalar (e.g. `N × weight`) — see
  PLAN.md §1.6 for why.
