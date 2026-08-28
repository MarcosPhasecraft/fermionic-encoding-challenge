"""Registry of baseline encode_fn's, by name, built from registry.json.

registry.json is the single source of truth for which baselines exist and
which lattice sizes each one claims to be valid for (a submission need not
cover the full 3x3..15x15 range -- see scripts/submit_baseline.py). Don't
hand-edit registry.json directly; scripts/submit_baseline.py writes it
after confirming a submission actually passes at every size it claims.

BASELINES[name] = {"encode": encode_fn, "sizes": [int, ...]}
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
        registry[name] = {"encode": module.encode, "sizes": entry["sizes"]}
    return registry


BASELINES = _load_registry()
