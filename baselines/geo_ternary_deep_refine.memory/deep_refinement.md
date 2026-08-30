# Deep Clifford refinement — what carried, what didn't

Context: `baselines/ternary_multistage_refinement.py` (Codex GPT-5.6 Sol,
registered 2026-08-29) took the total-weight lead at **all thirteen sizes**,
beating `geo_ternary_clifford_anneal` by between 0.6% (14x14) and 7.6% (6x6)
and breaking the 5x5 record we had just set (819 -> 773). This is the
investigation into why, and the attempt to take it back.

Method note: their code is in the repo, so this started by reading it rather
than their `approach.md` — per `CLAUDE.md`, a baseline's memory notes are
unverified prose and its actual behaviour is the ground truth. Their prose
turned out to be accurate, but the *reasons* their pipeline works are not
the ones it emphasises.

## Reproducing them first, so that "better" means something

Their five refinement stages were run from our own placement at 7x7:

| stage | total | time |
|---|---|---|
| greedy tree-axis Clifford descent | 1864 | 0.2s |
| + width-64 depth-12 barrier beam | 1844 | 3.9s |
| + exhaustive `Sp(4,2)` blocks, tree distance <= 2 | 1838 | 0.1s |
| + radius-3 Majorana swaps (beam 200) | 1834 | 6.3s |
| + weight-4 logical transvections | 1834 | 0.2s |
| + 16x100k transvection anneal | **1809** | 88.1s |

Two things fall out immediately. The final anneal does more than the other
four stages combined, and it costs ~90% of the runtime. Everything below
follows from taking that seriously.

## The finding: their anneal budget doesn't scale, and that is the whole gap

Their anneal proposes a random qubit *pair* and a random axis, 100k steps per
run. The move space is `9 * M(M-1)/2`. So the number of sweeps of that space
collapses as the lattice grows:

| L | M | move space | sweeps in 100k steps |
|---|---|---|---|
| 7 | 49 | 10.6k | 9.4 |
| 13 | 169 | 128k | 0.78 |
| 15 | 225 | 227k | 0.44 |

Measured consequence at 13x13, from an identical starting state:

| budget | total |
|---|---|
| 4 x 100k (their scale) | 8265 — **no change at all** |
| 4 x 400k | 8204 |
| 8 x 800k | 8200 |

At 7x7 the same comparison shows the shape of it: 16x400k (1808) beats
64x100k (1813) at four times the *same* total step count. Longer runs, not
more of them — the anneal is undercooled, not unlucky.

This is exactly where our deficit was largest (11x11 +201, 12x12 +203,
13x13 +283), and it is the single change worth the most.

## What is genuinely new: axes read off the data

Every axis set anyone has used in this benchmark is *structural* —
tree-adjacent qubit pairs (theirs and ours), lattice-adjacent pairs (tried,
worse), random pairs (their anneal). But a transvection can only lower the
score by **cancelling support a term already has**. So the axes worth trying
are readable off the current state: take a term product, restrict it to a
subset of its own support, and you get an axis that annihilates exactly that
part of it.

Enumerating those subsets at sizes 2, 3 and 4 over all terms gives ~47k
candidate axes at 13x13 and ~66k at 15x15 — small enough to score
exhaustively in about two seconds, and cheap because mean support is only
~3.6 qubits, so the combinatorics never blow up.

Measured at 13x13, from a state **proven optimal against the entire
two-qubit neighborhood** (see below):

| axis subset size | axes | improving | best single move |
|---|---|---|---|
| 2 | 6358 | 0 | — |
| 3 | 15365 | 1 | **-10** |
| 4 | 25209 | 0 | — |

A single weight-3 axis worth -10 where every two-qubit move in existence was
worth nothing. Iterated to a fixed point it is worth -13 there. It is not a
large number, but it is reach no pair-based move set has at all.

## Exhaustive two-qubit descent — and the negative result that made it useful

All `M(M-1)/2` qubit pairs, against all ten distinct two-qubit support
actions of `Sp(4,2)`, scored at once. Affordable because the score change of
a block move depends on the term products only through the *histogram* of
their local two-qubit patterns: all `M^2` histograms are 16 matrix products
of indicator matrices, and since a move rewrites only two qubit columns the
tensor updates in `O(M*T)` rather than `O(M^2*T)`.

The result was a **negative** one, and it is the most useful thing measured
here: after their restricted stages, exhaustive search over the whole
two-qubit neighborhood finds **one** improving move at 13x13. Their
tree-distance-<=2 restriction is not costing them anything — the far pairs
genuinely have nothing to offer.

That reframes the problem. The neighborhood is not the bottleneck; **escaping
local optima is**, and only uphill moves do that. Which is why the budget
finding above is the lever and not this one. Exhaustive descent stays in the
pipeline because it is nearly free and cleanly certifies a fixed point
between anneal passes.

## Ruled out, with numbers

- **Restricting the anneal's pair pool.** Predicted (from
  `clifford_transvections.md`, where tree-adjacent axes beat everything for
  *greedy descent*) that biasing the anneal toward tree-local pairs would beat
  uniform sampling. Wrong at both sizes tested. 7x7: all-pairs 1813 vs tree-2
  1831, tree-3 1821, tree-4 1811. 13x13: all-pairs 8204 vs tree-4 8257,
  co-occurrence-weighted 8251. Once earlier stages have reshaped supports away
  from root-to-leaf paths, "tree-adjacent" no longer describes where the
  useful axes are. The greedy-descent result does not transfer to annealing.

- **Relaxing the maximum-weight cap.** 7x7, full pipeline: cap+0 -> 1809
  (max 8), cap+1 -> 1804 (max 9), cap+2 -> 1803 (max 10), cap+3 -> 1800
  (max 10). About -5 total per +1 of maximum weight — a bad trade on a ~1810
  baseline, and it would be optimizing one leaderboard metric by quietly
  spending the other. Not taken. It is a one-line change if it is ever wanted.

- **Ancillas (`N = c*M` local encodings).** Dismissed by arithmetic before
  writing anything: the best ancilla-free average weight per term is already
  ~3.5 (11202 over 3165 terms at 15x15), which is at or below what O(1)-weight
  local encodings deliver. Spending qubits cannot win *total* weight here even
  though it would crush *maximum* weight.

- **Random weight-3 transvections.** 60k random triple-axis probes from a
  two-qubit local optimum: zero improving moves. The space is 21M at 13x13 and
  random sampling of it is hopeless — which is precisely why the axes have to
  come from the data instead.

- **Round-robin over their cheap stages alone.** Converges after one round
  (1834, unchanged) at 7x7. Without the anneal there is nothing to re-descend.

- **Their barrier / Majorana-swap / weight-4-logical stages, ablated.** Kept
  or dropped, the pipeline lands in the same place once the anneal passes run:
  13x13 with them 7904, without them 7911, both still falling. Dropped, for a
  much smaller module — but the margin is thin enough that this is a judgement
  call, not a proven equivalence.

## Budget allocation: depth beats breadth, decisively

The refiner iterates `anneal -> exhaustive two-qubit descent -> data-driven
descent` as a *pass*, restarting each anneal from the incumbent best. Given a
roughly fixed compute budget there are three places to spend it — anneals per
pass, number of passes, number of finalists — and they are not close.

Measured on the only two sizes where the first full sweep lost (rival: 11x11
5366, 12x12 6623):

| allocation | 11x11 | 12x12 | time (11x11) |
|---|---|---|---|
| 5 runs, 6 passes, 2 finalists | 5399 | 6641 | 325s |
| 5 runs, 8 passes, **4 finalists**, 6 seeds | 5442 | 6432 | 296s |
| 5 runs, 12 passes, 2 finalists | 5360 | 6432 | 548s |
| **3 runs, 20 passes**, 2 finalists | **5336** | **6429** | 293s |
| 2 runs, 32 passes, 2 finalists | 5304 | 6453 | 310s |

Trading anneals-per-pass for passes is worth ~-90 at 11x11 and ~-210 at
12x12 *and finishes sooner*. Spending the same budget on more finalists made
11x11 worse. Below about 3 runs the two sizes disagree by more than the
effect size, so 3/20 was taken as the setting rather than pushing further —
past that point this is fitting noise.

The one thing that must **not** be traded away is the length of an individual
anneal. Halving `_ANNEAL_STEPS_PER_PAIR` to 60 and doubling passes to 40 is
much worse (11x11 5457, 12x12 6651) despite the same nominal budget — the
same undercooling effect the size-scaled budget exists to avoid, now
reintroduced from the other direction.

Run-to-run spread at a fixed setting is roughly +-25 at these sizes, which is
why the two sizes rank the last two rows differently and why the first
sweep's two losses (+33, +18) were variance sitting on top of a pipeline that
was already competitive, not a structural deficit.

## Candidate postselection matters more than any refinement at large sizes

At 13x13 the twelve candidates in the placement family span **8040 to 8964** —
an 11% spread, far larger than anything refinement recovers. Their pipeline
generates that family and then deep-refines exactly **one** of them, which sits
oddly against their own (correct) observation that refinement is not monotonic
in the pre-refinement score. `clifford_transvections.md` measured the same
thing independently at 15x15: a candidate starting 134 points behind finished
73 ahead. So more than one finalist is carried through here and the choice is
made on the final score.

## Don't stop the pass loop on one bad pass

The pass loop originally stopped the first time a pass failed to improve.
That is wrong for the same reason the rest of this is: a pass is a
*stochastic* probe, so one finding nothing is weak evidence of a fixed point.
It cost real points — 14x14 halted after 361s at 9645 (a loss against their
9619) where letting it run to a patience of 3 consecutive empty passes reaches
**9404**, a 215-point win. 13x13 likewise improved 7898 -> 7833. This was the
single largest remaining bug-shaped loss, and it looked like a tuning
parameter rather than a defect, which is why it survived a whole sweep.

## Result

Full sweep, every number produced by the submitted `encode.py` itself and
verified end-to-end through the frozen harness (`passed: True`, zero Majorana
violations, `n_qubits = M` at every size). `encode` is deterministic —
re-running it gives byte-identical Pauli strings, checked explicitly, so these
numbers reproduce when the pipeline re-runs them.

Against `ternary_multistage_refinement`, which held rank 1 at all thirteen
sizes when this started:

| L | this | rival | delta | vs our previous submission |
|---|---|---|---|---|
| 3 | 201 | 201 | tie | -3 |
| 4 | **436** | 438 | -0.46% | -30 |
| 5 | 773 | 773 | tie | -46 |
| 6 | **1230** | 1231 | -0.08% | -95 |
| 7 | **1803** | 1810 | -0.39% | -101 |
| 8 | **2576** | 2630 | -2.05% | -127 |
| 9 | **3287** | 3430 | -4.17% | -172 |
| 10 | **4186** | 4363 | -4.06% | -271 |
| 11 | **5336** | 5366 | -0.56% | -231 |
| 12 | **6422** | 6623 | -3.04% | -404 |
| 13 | **7833** | 8006 | -2.16% | -456 |
| 14 | **9404** | 9619 | -2.24% | -275 |
| 15 | **10749** | 11202 | -4.04% | -623 |

Eleven wins, two ties, no losses. The 3x3 tie is not a shortfall: 201 is
proven globally optimal there by exhaustive search over all 9! orderings
(`NOTES.md`). 5x5 at 773 looks similar in character — three different budget
settings, up to 24 passes, all land on exactly 773.

**Cost.** Roughly PLACEHOLDERMINS minutes for the full 3x3-15x15 sweep run
sequentially, against ~52 minutes for the submission it beats. Most of it is
the anneal, and most of *that* is at 14x14 and 15x15. The budget constants
(`_PASSES`, `_ANNEAL_RUNS`, `_ANNEAL_STEPS_PER_PAIR`) are all in one block at
the top of the driver if a cheaper operating point is wanted; halving
`_PASSES` costs roughly 1-2% of total weight and still beats the rival at
most sizes.

**Maximum weight is a mixed result and is not claimed.** Sometimes better than
theirs (9x9 9 vs 12, 15x15 16 vs 17), sometimes worse (8x8 11 vs 9, 13x13 15
vs 13) — it follows whichever candidate's cap the postselection lands on.
`geo_ternary_multitree` is far better than either on that metric (10 at
15x15) and remains the encoding to beat there.

## Not tried, worth trying next

- **Data-driven axes inside the anneal.** They are currently only used in
  descent, at fixed points. Letting the anneal *propose* weight-3 and weight-4
  support-derived axes would combine the escape mechanism with the wider
  reach, instead of alternating them.
- **Weight-5+ support subsets.** Stopped at 4 because mean support is ~3.6, so
  larger subsets exist for few terms — but those few are the highest-weight
  terms, which is where the remaining cost is concentrated.
- **Three-qubit `Sp(6,2)` blocks**, by the same histogram trick — the natural
  completion of the exhaustive two-qubit descent, and the tensor is only
  `M^3 * 64`, which is still tractable at these sizes if restricted to triples
  that actually co-occur in some support.
