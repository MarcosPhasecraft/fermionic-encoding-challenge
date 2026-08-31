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

Square-lattice challenge (the default -- `graph` omitted):

```json
{
  "name": "alice_bk_variant",
  "label": "Alice's BK Variant",
  "sizes": "3-15",
  "generated_by": "Claude Opus 4.5"
}
```

Graph challenge (non-square lattices -- note `sizes`' different grammar, and the added `"graph"` field):

```json
{
  "name": "alice_tri_variant",
  "label": "Alice's Tri-Lattice Variant",
  "sizes": "3x3,4x4,5x5,6x6,7x7,8x8",
  "graph": "triangular",
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

  **How `LEADERBOARD_GRAPHS.md` is laid out.** Same shape as
  `LEADERBOARD.md`, per graph type: a pair of rank-based tables (total
  weight, max weight), row 1 is whoever wins, not a fixed encoding,
  columns are `Lx = Ly` sizes exactly like `LEADERBOARD.md`'s own —
  swept `3x3..8x8` for both `triangular` and `hexagonal` (the same
  numeric cap for both, deliberately, even though hexagonal has two sites
  per unit cell and so reaches double triangular's qubit count at the
  same `L` — 128 vs. 64 at `8x8`). `periodic_hexagonal`/
  `periodic_triangular` are valid `"graph"` values and get fully
  verified/scored/cached, but aren't swept/shown in a table yet. There's
  also a progress-over-time chart at the top, like `LEADERBOARD.md`'s,
  but for Tri-Lattice only at `8x8` — see below for why.

  **Which shapes/sizes actually get shown.** A submission can claim any
  valid shape for its challenge, but only some are rendered: for
  `graph="square"`, exactly the integer sizes `3..15` (`Lx = Ly`, arXiv
  2504.21636 Table I's own sweep); for `triangular`/`hexagonal`, exactly
  the `Lx = Ly` sizes within that type's own sweep range above. Anything
  else — an off-square rectangle, an out-of-range size, or any shape at
  all for the periodic variants — is still verified, scored, and cached,
  just shown (for the graph challenge) in a separate "Other shapes" table
  instead of a ranked one, or (for the square challenge) not shown
  anywhere yet. This decision lives in one place, `is_showcased()` in
  `scripts/update_leaderboard.py`, so it can gain new showcased
  shapes/sizes/graph types later without a rendering rewrite.

  **Only Tri-Lattice's tables carry a `[1]`-linked Table II reference
  row.** Table II's own comparison shape for triangular, `(8, 8)`, is
  `Lx = Ly` (triangular's mode count `M = Lx·Ly` matches the square
  lattice's own formula), so it lands exactly on Tri-Lattice's `L=8`
  column. Hexagonal's comparison shape, `(8, 4)`, is *not* `Lx = Ly`
  (hexagonal has two sites per unit cell, so `M = 2·Lx·Ly` needs `Lx !=
  Ly` to hit the paper's `M=64`) — it has no column in an `Lx = Ly`-only
  sweep, so Hex-Lattice's tables have no paper reference row at all. Its
  own `jw`/`tt` reference entries are still real, ranked rows, just
  without a paper number to line up against. Include `8x8` in your
  `sizes` string for a `triangular` submission if you want to compete
  directly against `[1]`.

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

If anything was accepted, the script regenerates `LEADERBOARD.md`,
`LEADERBOARD_GRAPHS.md`, and `MEMORY.md`, re-runs the test suite, prints a
summary, and only then asks you — on the terminal, not through an AI —
whether to push, commit locally, or do neither.
