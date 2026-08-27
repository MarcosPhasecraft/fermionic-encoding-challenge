# Your submission goes here

See the repo's top-level `README.md` for the full explanation ("How to
play"). Quick reference:

```python
# solution/encode.py
def encode(spec) -> mapping
```

Signature exactly `f(spec)` — no extra arguments, no closing over lattice
data (`Lx`, `Ly`, `edges`, `coords` are all already in `spec`). One uniform
rule: no branching on `spec["M"]`, `Lx`, or `Ly`, no size-keyed lookup
tables — this is enforced by evaluating on held-out sizes, not by review.

Test it with `python3 run.py evaluate --lx 3 --ly 3 --note "what I tried"`
from the repo root (or `--solution path/to/file.py` to test something
else, e.g. a baseline).

`memory/` is yours too, for running notes across attempts.
