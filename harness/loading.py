"""Shared utility for loading a submission from an arbitrary file path --
used by both run.py (evaluate a submission) and scripts/submit_baseline.py
(test a candidate before promoting it).
"""

import importlib.util
from pathlib import Path


def load_submission(path: str):
    """Returns (encode_fn, order_fn_or_None). order_fn is the submission's
    own optional order(Lx, Ly) -> perm; None if it declares none, in which
    case callers fall back to row_major (see harness.lattice.build_spec).
    """
    if not Path(path).is_file():
        raise SystemExit(f"no such file: {path!r}")
    module_spec = importlib.util.spec_from_file_location("submission", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if not hasattr(module, "encode"):
        raise SystemExit(f"{path} has no encode(spec) function")
    return module.encode, getattr(module, "order", None)
