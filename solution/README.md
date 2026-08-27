# Your submission goes here

This directory is the only editable one — everything in `harness/` and
`baselines/` is frozen (see `CLAUDE.md`). It's empty right now because Stage
2 (see `PLAN.md`) hasn't formally started: the four Stage 1 tests need to
pass first.

When it does, the contract is one file:

```python
# solution/encode.py
def encode(spec) -> mapping
```

Signature exactly `f(spec)` — no extra arguments, no closing over lattice
data (`Lx`, `Ly`, `edges`, `coords` are all already in `spec`). One uniform
rule: no branching on `spec["M"]`, `Lx`, or `Ly`, no size-keyed lookup
tables — this is enforced by evaluating on held-out sizes, not by review.

## Testing it

```bash
python3 run.py evaluate --lx 3 --ly 3 --note "what I tried"
```

This imports `encode` from `solution/encode.py` (or pass `--solution
path/to/file.py` to test something else, e.g. a baseline), builds a `3×3`
spec, runs it through `verify()` then `score()` (only if verification
passed), prints the result, and appends a row to `../results.tsv`. See
`run.py --help` and `python3 run.py evaluate --help` for the full set of
flags (`--ordering`, `--model`, `--ly`, ...).

The first thing to actually try, per `PLAN.md`'s Stage 2 test: `cp
baselines/jw.py solution/encode.py` and confirm the score matches Stage 1's
known JW numbers exactly (it should — same code). If it doesn't, something
leaked outside the `f(spec)` contract.

`memory/` is yours too, for whatever running notes are useful across
attempts — see `github.com/ecdsafail/ecdsafail-challenge`'s
`src/point_add/memory/` for what this looks like in practice elsewhere.
