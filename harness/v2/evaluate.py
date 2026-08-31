"""Extended combinator: encode_fn -> verify_extended -> score_extended.
Mirrors harness.evaluate.evaluate's shape and never-raise-past-here
convention, extended to also guard against a crashing or invalid
represent() hook -- see harness/v2/score.py's RepresentativeRejected.

Not an edit to harness/evaluate.py -- see harness/v2/verify.py's docstring
for why new functionality lives in harness/v2/ instead.
"""

from harness.v2.score import RepresentativeRejected, score_extended
from harness.v2.verify import verify_extended


def evaluate_extended(spec: dict, encode_fn, term_records: list, represent_fn=None) -> dict:
    try:
        mapping = encode_fn(spec)
    except Exception as e:
        return {"passed": False, "error": f"encode(spec) raised {type(e).__name__}: {e}"}

    v = verify_extended(spec, mapping)
    if not v["passed"]:
        return v

    try:
        scored = score_extended(spec, mapping, term_records, represent_fn)
    except RepresentativeRejected as e:
        return {"passed": False, "error": str(e)}

    return {**v, **scored}
