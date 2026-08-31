"""Extended submission loader: adds the optional represent() hook
(harness/v2/score.py) on top of harness.loading.load_submission's
(encode_fn, order_fn) pair.

A separate module rather than editing harness/loading.py in place, for the
same harness_fingerprint()-isolation reason as the rest of harness/v2/ (see
harness/v2/verify.py's docstring) -- and because harness.loading's existing
return signature is depended on by scripts/submit_baseline.py and run.py,
which this pass leaves untouched. The ~15 lines of module-loading logic
below are duplicated from harness/loading.py rather than shared, since
sharing would mean either importing from harness.loading (fine on its own,
but doesn't reduce the duplication enough to be worth a dependency) or
editing it to expose a shared helper (which would touch a frozen file for
no behavioral gain).
"""

import importlib.util
from pathlib import Path


def load_submission_extended(path: str):
    """Returns (encode_fn, order_fn_or_None, represent_fn_or_None).

    encode_fn/order_fn: see harness.loading.load_submission's docstring.
    represent_fn: the submission's optional
    represent(term, raw_pauli, spec, mapping) -> str hook for proposing a
    stabilizer-equivalent representative of a Hamiltonian term (see
    harness/v2/score.py); None if the submission declares none, in which
    case harness.v2.score.score_extended scores the raw Majorana product
    unchanged, exactly like the ancilla-free legacy path.
    """
    if not Path(path).is_file():
        raise SystemExit(f"no such file: {path!r}")
    module_spec = importlib.util.spec_from_file_location("submission", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if not hasattr(module, "encode"):
        raise SystemExit(f"{path} has no encode(spec) function")
    return module.encode, getattr(module, "order", None), getattr(module, "represent", None)
