# Mixed data-driven anneal

Same base pipeline as `geo_ternary_deep_refine` (placement anneal, greedy
tree-axis descent, exhaustive two-qubit Sp(4,2) descent, support-axis
descent, multi-pass postselection), reused via import rather than copied.
The one change is the anneal's own proposal distribution.

## What changed

`geo_ternary_deep_refine`'s own memory (`deep_refinement.md`, "Not tried,
worth trying next") flags that data-driven support axes (weight 3/4, read
off a term's current support -- the only axes that can cancel existing
structure) are only used in a separate descent stage run between anneal
passes. The anneal itself -- the stage that actually escapes local optima
-- only ever proposed random-pair, weight-2 structural moves.

This mixes both into one proposal distribution: each anneal step, with
probability `_MIX_PROB = 0.25`, propose a data-driven support axis
(regenerated periodically as supports drift) instead of a random-pair
transvection; otherwise fall back to the original move. Both are cap-
respecting, Metropolis-accepted identically -- a fixed axis of any weight
is still a legal Sp(2M,2) transvection, so validity is untouched.

`_MIX_PROB` and the axis-regeneration interval came from a sweep at 7x7
(mix probability 0.05-0.7, regen interval 2000-50000 steps against a 200k-
step anneal) showing a clear interior optimum. Not swept per-size -- a
fixed fraction is taken over a size-keyed table on principle, per this
repo's "one uniform rule" for `encode()`.

## Evidence

Full-pipeline `run.py evaluate` results, this submission vs. the current
`geo_ternary_deep_refine` champion (row-major ordering, `full` model):

| size | champion (total) | mixed anneal (total) | delta |
|---|---|---|---|
| 3x3  | 201  | 201  | tie |
| 5x5  | 773  | 773  | tie |
| 7x7  | 1803 | 1800 | -3  |
| 9x9  | 3287 | 3277 | -10 |
| 11x11 | 5336 | 5288 | -48 |
| 13x13 | 7833 | 7797 | -36 |

Never a regression across these six sizes, spanning small to large; ties
at the two smallest sizes (where the search space is small enough that
the base pipeline was likely already at or near the true optimum) and a
consistent, growing improvement from 7x7 up.

## Not done this round

14x14 and 15x15 were not validated -- a 15x15 run was still going after
~80 minutes of wall time (longer than the pool-size scaling from smaller
sizes predicted) and was killed rather than waited out. `submission.json`
deliberately claims only the six validated odd sizes above, not `3-15`,
so `process_inbox.py`'s own re-verification doesn't end up re-running the
same expensive untested sizes. Worth submitting a follow-up once 14x14/
15x15 (and the untested even sizes) are actually validated.
