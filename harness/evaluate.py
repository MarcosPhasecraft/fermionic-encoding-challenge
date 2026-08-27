"""Frozen combinator: encode_fn -> verify -> score. See PLAN.md "Making the
transition free" -- this is Stage 2's thin wrapper, but nothing about it
requires an untrusted encode_fn, so it's used from Stage 1 too.

Never call encode_fn's output straight into score() without going through
here -- verify() must gate scoring unconditionally, even for a trusted
baseline, so that an accidental encode_fn bug shows up as a failed check
instead of a silently wrong score.
"""

from harness.score import score_majorana
from harness.verify import verify


def evaluate(spec: dict, encode_fn, terms: list[tuple[int, ...]]) -> dict:
    try:
        mapping = encode_fn(spec)
    except Exception as e:
        # A crashing encode_fn is not a harness bug (see CONTEXT.md Sec 5:
        # assume the submission first) -- report it the same structured,
        # never-raise way verify() reports a malformed mapping, rather than
        # letting the traceback propagate. The empty solution/encode.py
        # stub raises NotImplementedError, and this is what makes running
        # it as-is fail cleanly instead of crashing run.py evaluate.
        return {"passed": False, "error": f"encode(spec) raised {type(e).__name__}: {e}"}

    v = verify(spec, mapping)
    if not v["passed"]:
        return v
    return {**v, **score_majorana(spec, mapping, terms)}
