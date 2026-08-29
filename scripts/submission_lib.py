"""Shared logic for testing and registering a candidate encode(spec) ->
mapping against the harness -- used by both scripts/submit_baseline.py
(manual, one file at a time) and scripts/process_inbox.py (the fully
automated inbox pipeline), so "what counts as passing" has exactly one
implementation, not two that could drift.

Also holds scripts/update_leaderboard.py's score-cache primitives
(hash_file/harness_fingerprint/load_score_cache/save_score_cache), for the
same reason: scripts/process_inbox.py needs them too, to pre-warm the
cache with a just-accepted submission's scores (already computed once, to
gate acceptance) so the leaderboard regeneration step -- a separate
subprocess with no memory of what the parent just computed -- doesn't pay
for a potentially expensive encode() a second time in the same run.
"""

import ast
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from harness.evaluate import evaluate
from harness.lattice import build_spec, hamiltonian

BASELINES_DIR = REPO_ROOT / "baselines"
REGISTRY_PATH = BASELINES_DIR / "registry.json"
CACHE_PATH = REPO_ROOT / ".leaderboard_cache.json"
MIN_SIZE, MAX_SIZE = 3, 15
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SubmissionRejected(Exception):
    """A candidate failed some check before it could be registered --
    always carries a human-readable reason, never a bare traceback.
    """


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def save_registry(registry: dict) -> None:
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")


def registry_entry(name: str, sizes: list[int], label: str, generated_by=None, submitted_at=None) -> dict:
    """Builds one registry.json value -- doesn't read or write the file
    itself, so a caller registering several submissions in one run can
    load_registry() once, build/merge several entries, and save_registry()
    once at the end (or after each, for crash-safety -- caller's choice).
    """
    entry = {"module": f"baselines.{name}", "sizes": sizes, "label": label}
    if generated_by is not None:
        entry["generated_by"] = generated_by
    if submitted_at is not None:
        entry["submitted_at"] = submitted_at
    return entry


def parse_sizes(spec: str) -> list[int]:
    sizes = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            sizes.update(range(int(lo), int(hi) + 1))
        else:
            sizes.add(int(part))
    return sorted(sizes)


def validate_sizes(sizes_str: str) -> list[int]:
    sizes = parse_sizes(sizes_str)
    if not sizes:
        raise SubmissionRejected("'sizes' is empty")
    if not all(MIN_SIZE <= l <= MAX_SIZE for l in sizes):
        raise SubmissionRejected(f"sizes must be between {MIN_SIZE} and {MAX_SIZE} (the leaderboard's current range)")
    return sizes


def validate_manifest(manifest: dict) -> dict:
    """Checks a parsed submission.json dict. Returns it back with "sizes"
    replaced by the parsed list[int] if valid; raises SubmissionRejected
    with a specific reason otherwise.
    """
    if not isinstance(manifest, dict):
        raise SubmissionRejected(f"submission.json must be a JSON object, got {manifest!r}")

    for key in ("name", "label", "sizes"):
        if key not in manifest:
            raise SubmissionRejected(f"submission.json is missing required key {key!r}")

    name = manifest["name"]
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise SubmissionRejected(f"'name' must match {NAME_RE.pattern!r}, got {name!r}")

    label = manifest["label"]
    if not isinstance(label, str) or not label.strip():
        raise SubmissionRejected(f"'label' must be a non-empty string, got {label!r}")

    if not isinstance(manifest["sizes"], str):
        raise SubmissionRejected(f"'sizes' must be a string (e.g. '3-15'), got {manifest['sizes']!r}")
    sizes = validate_sizes(manifest["sizes"])

    generated_by = manifest.get("generated_by")
    if generated_by is not None and not isinstance(generated_by, str):
        raise SubmissionRejected(f"'generated_by' must be a string if given, got {generated_by!r}")

    return {**manifest, "sizes": sizes}


def _top_level_bound_names(tree: ast.Module) -> list[str]:
    """Every name bound at module top level -- function defs, imports
    (including `from x import encode`, the pattern baselines/*_snake.py
    already uses to reuse another module's encode() under a different
    order()), and plain assignments. Not scoped to encode()/order() only:
    the duplicate-binding check below applies to any of these.
    """
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names += [alias.asname or alias.name for alias in node.names]
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
    return names


def validate_encode_source(source: str) -> None:
    """Parses encode.py's source (without executing it) and rejects it if
    there's no top-level `encode` binding, or if any top-level name --
    encode, order, an imported name, or a helper function -- is bound more
    than once. That second check is the mechanical guard against a file
    that's had an earlier submission's code pasted in alongside the new
    one.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise SubmissionRejected(f"encode.py has a syntax error: {e}")

    names = _top_level_bound_names(tree)

    if "encode" not in names:
        raise SubmissionRejected("encode.py must define or import a top-level encode(spec) name")

    duplicates = sorted(n for n, c in Counter(names).items() if c > 1)
    if duplicates:
        raise SubmissionRejected(
            f"encode.py binds the same top-level name more than once: {duplicates} "
            "-- looks like leftover code from a previous submission pasted into this file"
        )


def summarize_failure(result: dict) -> str:
    """A short, human-readable reason -- never the raw result dict, which
    can carry thousands of violation pairs at larger M and is unreadable.
    """
    if "error" in result:
        return result["error"]
    well_formed = result["checks"]["well_formed"]
    if not well_formed["passed"]:
        return "malformed mapping: " + "; ".join(well_formed["issues"])
    algebra = result["checks"]["majorana_algebra"]
    examples = ", ".join(str(v) for v in algebra["violations"][:5])
    more = f" (+{algebra['n_violations'] - 5} more)" if algebra["n_violations"] > 5 else ""
    return f"{algebra['n_violations']} Majorana pairs fail to anticommute, e.g. {examples}{more}"


def check_at_size(encode_fn, order_fn, l: int) -> tuple[int, int]:
    """(total, max) at size l x l, under the submission's own declared
    ordering (row_major if it declares none). Raises SubmissionRejected
    with a specific size/reason if verify() fails -- never silently
    accepts a partially-working submission.
    """
    spec = build_spec(l, l, order_fn)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode_fn, terms)
    if not result["passed"]:
        raise SubmissionRejected(f"FAILED at {l}x{l}: {summarize_failure(result)}")
    return result["total_weight"], result["max_weight"]


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harness_fingerprint() -> str:
    """Hash of every harness/*.py file's content, sorted by filename for
    determinism. Gates the whole leaderboard score cache at once (see
    scripts/update_leaderboard.py's module docstring) -- a baseline's
    score can depend on any harness utility its encode()/order() calls
    into, not just the scoring functions proper, so there's no safe way
    to track "which files affect which baseline" per-entry.
    """
    hasher = hashlib.sha256()
    for path in sorted((REPO_ROOT / "harness").glob("*.py")):
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def load_score_cache() -> dict:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def save_score_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")
