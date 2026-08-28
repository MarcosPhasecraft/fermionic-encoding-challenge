"""Registry of baseline encode_fn's, by name, built from registry.json.

registry.json is the single source of truth for which baselines exist and
which lattice sizes each one claims to be valid for (a submission need not
cover the full 3x3..15x15 range -- see scripts/submit_baseline.py). Don't
hand-edit registry.json directly; scripts/submit_baseline.py writes it
after confirming a submission actually passes at every size it claims.

BASELINES[name] = {"encode": encode_fn, "order": order_fn_or_None,
                    "sizes": [int, ...], "module": "baselines.name",
                    "label": "display name", "submitted_at": str_or_None,
                    "generated_by": str_or_None}

"order" is the module's own optional order(Lx, Ly) -> perm (None if it
declares none, in which case harness.lattice.build_spec falls back to
row_major). "module" is kept alongside "encode" so the leaderboard can link
to the file that actually declares a baseline's identity even when its
encode_fn is imported from elsewhere (see baselines/*_snake.py, which reuse
another baseline's encode() under a different declared ordering). "label"
is the human-readable leaderboard display name a submitter chose (falls
back to the registry name itself for entries registered before that option
existed). "submitted_at"/"generated_by" are set by
scripts/process_inbox.py for anything that came through the inbox
pipeline -- an ISO timestamp stamped locally at acceptance time (never
taken from the submission itself) and an optional free-text
model/author note; both None for entries that predate the pipeline or
came in through scripts/submit_baseline.py's manual path instead.
Neither is ever rendered on the leaderboard -- see scripts/submission_lib.py.
"""

import importlib
import json
from pathlib import Path

_REGISTRY_PATH = Path(__file__).parent / "registry.json"


def _load_registry() -> dict:
    with open(_REGISTRY_PATH) as f:
        raw = json.load(f)
    registry = {}
    for name, entry in raw.items():
        module = importlib.import_module(entry["module"])
        registry[name] = {
            "encode": module.encode,
            "order": getattr(module, "order", None),
            "sizes": entry["sizes"],
            "module": entry["module"],
            "label": entry.get("label", name),
            "submitted_at": entry.get("submitted_at"),
            "generated_by": entry.get("generated_by"),
        }
    return registry


BASELINES = _load_registry()
