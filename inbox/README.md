# Submission inbox

Ask whoever's submitting to hand you the **whole folder, already built**,
in this exact shape:

```
<any-folder-name>/
  encode.py         # def encode(spec) -> mapping; optional def order(Lx, Ly) -> perm
  submission.json   # {"name": "...", "label": "...", "sizes": "3-15"}
  memory/           # OPTIONAL -- notes on what was tried (see below)
    <any-name>.md
```

Then it's two steps on your end: drop that folder straight into `inbox/`
(so it's `inbox/<their-folder-name>/encode.py` and
`inbox/<their-folder-name>/submission.json`), and run the pipeline (below).
No repackaging, no copy-pasting individual files — take the folder they
gave you as-is.

The folder name itself doesn't matter — `scripts/process_inbox.py` reads
the real identity from `submission.json`, not the folder — so whatever
they called it is fine to keep. Several pending submissions can sit in
`inbox/` at once; one run of the pipeline handles all of them.

## `submission.json`

```json
{
  "name": "alice_bk_variant",
  "label": "Alice's BK Variant",
  "sizes": "3-15",
  "generated_by": "Claude Opus 4.5"
}
```

- **`name`** (required) — the registry key and filename:
  `baselines/<name>.py`. Must match `^[a-z][a-z0-9_]*$` (lowercase, starts
  with a letter, only letters/digits/underscore). Rejected outright if it
  doesn't match that pattern, or if it's already registered. Keep it
  descriptive of the approach (`geo_ternary_anneal`, not `submission_3`).
- **`label`** (required) — the human-readable name shown on the
  leaderboard instead of the raw `name` slug.
- **`sizes`** (required) — which sizes/shapes this submission claims to be
  valid for. **The grammar depends on `graph` (below):**
  - Square-lattice challenge (`graph` omitted or `"square"`): a range
    (`"3-15"`), a single size (`"8"`), or a list (`"8,10,12"`), each an
    integer grid side length `L` (so `Lx = Ly = L`) — exactly as always.
    You can *also* mix in explicit `Lx x Ly` rectangle pairs in the same
    string, e.g. `"3-15,8x12"`, to additionally claim an off-square shape.
    Every dimension (plain or paired) must be within `3..15`.
  - Graph challenge (`graph` set to one of the four lattice types below):
    a comma-separated list of explicit `Lx x Ly` pairs, e.g.
    `"8x4,15x15,3x3"` — **no plain-integer/range syntax**, since `Lx` and
    `Ly` vary independently and a range over pairs would be ambiguous, and
    (unlike the square case) there's no natural "Lx=Ly" default: mode
    count `M` alone does **not** determine the graph for these lattice
    types — e.g. hex-lattice `Lx=8,Ly=4` and `Lx=16,Ly=2` both give `M=64`
    but are structurally different graphs (different edge counts/boundary
    structure), so the shape always has to be named explicitly. Each of
    `Lx`, `Ly` must be within `3..15`.

  Every claimed size/shape is checked, scored, and recorded in
  `baselines/registry.json` and the local score cache — none are optional
  or best-effort — **but not every claimed size/shape necessarily shows up
  on a leaderboard.** See "which shapes actually get shown" below.
- **`generated_by`** (optional) — free text: a model name, `"human"`, or
  omit it entirely if unknown/undisclosed. Never shown on the leaderboard;
  it's recorded in `baselines/registry.json` for later lookup only.
- **`graph`** (optional) — omit for the default square-lattice challenge
  (`LEADERBOARD.md`). Set to one of `hexagonal`, `periodic_hexagonal`,
  `triangular`, `periodic_triangular` to submit to the separate graph
  challenge instead (`LEADERBOARD_GRAPHS.md`, arXiv 2504.21636 Table II's
  benchmark) — see `harness/graphs.py` for each type's canonical default
  ordering and exact construction. Scored under the exact same
  `D = Num + ReHop + ImHop + Inter` metric as the square-lattice
  challenge — only the graphs differ, not the metric.

  **Which shapes/sizes actually get shown on a leaderboard.** A submission
  can claim any valid shape for its challenge, but only some are rendered:
  for `graph="square"`, exactly the integer sizes `3..15` (`Lx = Ly`,
  arXiv 2504.21636 Table I's own sweep) show up in `LEADERBOARD.md`; an
  off-square rectangle or an out-of-range size is still verified, scored,
  and cached, just not shown anywhere yet. For every other graph type,
  exactly one `(Lx, Ly)` pinned as that type's `CANONICAL_SHAPE`
  (`harness/graphs.py`) shows up in `LEADERBOARD_GRAPHS.md`'s "vs. Table
  II" section, next to the paper's own published numbers — gated on the
  *exact* shape, not just matching `M`, since (as above) comparing by `M`
  alone would let a submission pick whichever aspect ratio is easiest to
  encode well while still nominally "matching" the paper. A submission at
  any other shape for that graph type is still scored and shown, in the
  "Other shapes" section of the same table, just not lined up against
  `[1]`. This decision lives in one place, `is_showcased()` in
  `scripts/update_leaderboard.py`, so it can gain new showcased
  shapes/sizes later without a rendering rewrite. Include the showcased
  shape/size in your `sizes` string if you want your submission to appear
  in the headline comparison.

The acceptance date is *not* a field you provide — `process_inbox.py`
stamps it itself, from its own clock, the moment a submission actually
passes. A self-reported date can't be trusted; a locally-stamped one can.

## `encode.py`

One file, self-contained: exactly one top-level `def encode(spec) ->
mapping`, at most one top-level `def order(Lx, Ly) -> perm`, and no other
top-level function name defined more than once. That last rule exists
specifically to catch a file that's had an earlier submission's code
pasted in alongside the new one — `scripts/process_inbox.py` parses the
file (without running it) and rejects anything that looks like that,
before ever executing a line of it.

See the top-level `README.md`'s "How to play" section for the full
`encode(spec)`/`order(Lx, Ly)` contract.

## `memory/` (optional)

A folder of markdown notes on what was tried and why — what worked, what
plateaued, what a parameter tuned out to be. Entirely optional, and not
part of what gets verified: `verify()`/`check_at_size` never look at it.
If present, it's carried into the committed record alongside the code,
at `baselines/<name>.memory/`, and indexed in the top-level `MEMORY.md` so
future contestants can read what's already been tried before starting
their own attempt — the same thing ecdsa.fail's own shared
`src/point_add/memory/` notes are for. Same caveat as theirs, though:
this is unverified prose a submitter chose to write, not code the harness
runs — treat it as leads, not proven fact.

If it's not included, nothing happens — no empty folder, no entry in
`MEMORY.md`.

## Running the pipeline

```bash
python3 scripts/process_inbox.py
```

Processes every folder here, in one pass, with no manual flags and no AI
involvement: validates the manifest, validates the file's structure, runs
the exact same `verify()` gate every other baseline has gone through, and
if a submission passes, registers it and moves its folder to
`_processed/<timestamp>_<name>/` (e.g. `_processed/20260828-144437_alice_bk/`
— sortable by acceptance order; the original `submission.json` and
`encode.py` are archived there unchanged). A submission that fails is left
exactly where it is — fix it and run the command again.

If anything was accepted, the script regenerates `LEADERBOARD.md` and
`MEMORY.md`, re-runs the test suite, prints a summary, and only then asks
you — on the terminal, not through an AI — whether to push, commit
locally, or do neither.
