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
    mapping = encode_fn(spec)
    v = verify(spec, mapping)
    if not v["passed"]:
        return v
    return {**v, **score_majorana(spec, mapping, terms)}
