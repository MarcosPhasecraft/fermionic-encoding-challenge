# Submission inbox

Drop each new submission in its own folder here, in this exact shape:

```
inbox/
  <any-folder-name>/
    encode.py         # def encode(spec) -> mapping; optional def order(Lx, Ly) -> perm
    submission.json   # {"name": "...", "label": "...", "sizes": "3-15"}
```

The folder name itself doesn't matter — `scripts/process_inbox.py` reads
the real identity from `submission.json`, not the folder. Number them
however's convenient (`submission_4`, `submission_5`, ...).

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
- **`sizes`** (required) — which square-grid sizes this submission claims
  to be valid for: a range (`"3-15"`), a single size (`"8"`), or a list
  (`"8,10,12"`). Must be within `3..15`. Every claimed size is checked;
  none are optional or best-effort.
- **`generated_by`** (optional) — free text: a model name, `"human"`, or
  omit it entirely if unknown/undisclosed. Never shown on the leaderboard;
  it's recorded in `baselines/registry.json` for later lookup only.

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

## Running the pipeline

```bash
python3 scripts/process_inbox.py
```

Processes every folder here, in one pass, with no manual flags and no AI
involvement: validates the manifest, validates the file's structure, runs
the exact same `verify()` gate every other baseline has gone through, and
if a submission passes, registers it and moves its folder to
`_processed/<name>/`. A submission that fails is left exactly where it
is — fix it and run the command again.

If anything was accepted, the script regenerates `LEADERBOARD.md`, re-runs
the test suite, prints a summary, and only then asks you — on the
terminal, not through an AI — whether to push, commit locally, or do
neither.
