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
from harness.graphs import GRAPH_TYPES
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


def registry_entry(
    name: str, sizes: list[int | tuple[int, int]], label: str,
    generated_by=None, submitted_at=None, graph=None,
) -> dict:
    """Builds one registry.json value -- doesn't read or write the file
    itself, so a caller registering several submissions in one run can
    load_registry() once, build/merge several entries, and save_registry()
    once at the end (or after each, for crash-safety -- caller's choice).

    graph is omitted entirely (not written as "square") when it's the
    square-lattice default -- keeps every square-lattice entry in
    registry.json exactly as lean as it's always been; baselines/__init__.py
    already treats a missing "graph" key as "square" via .get(), so this
    changes nothing about how existing or future square entries are read.
    """
    entry = {"module": f"baselines.{name}", "sizes": sizes, "label": label}
    if generated_by is not None:
        entry["generated_by"] = generated_by
    if submitted_at is not None:
        entry["submitted_at"] = submitted_at
    if graph is not None and graph != "square":
        entry["graph"] = graph
    return entry


def parse_sizes(spec: str) -> list[int]:
    sizes = set()
    for part in spec.split(","):
        part = part.strip()
        try:
            if "-" in part:
                lo, hi = part.split("-")
                sizes.update(range(int(lo), int(hi) + 1))
            else:
                sizes.add(int(part))
        except ValueError:
            raise SubmissionRejected(f"'sizes' entries must be an integer or 'lo-hi' range, got {part!r}")
    return sorted(sizes)


def validate_sizes(sizes_str: str) -> list[int]:
    sizes = parse_sizes(sizes_str)
    if not sizes:
        raise SubmissionRejected("'sizes' is empty")
    if not all(MIN_SIZE <= l <= MAX_SIZE for l in sizes):
        raise SubmissionRejected(f"sizes must be between {MIN_SIZE} and {MAX_SIZE} (the leaderboard's current range)")
    return sizes


def shape_key(lx: int, ly: int) -> str:
    """'8x4' -- the shared shape-string key: it's the manifest sizes-grammar
    syntax for an explicit (Lx, Ly) pair (parse_shapes/validate_mixed_sizes),
    and it's also used as-is as the leaderboard score-cache key for any such
    pair, so a shape written in submission.json is exactly the string that
    shows up in the cache and (for showcased shapes) on the leaderboard --
    no separate re-encoding to keep in sync between the two.
    """
    return f"{lx}x{ly}"


def parse_shapes(spec: str) -> list[tuple[int, int]]:
    """'8x4,15x15,3x3' -> [(8, 4), (15, 15), (3, 3)] -- the graph
    challenge's sizes grammar. Unlike parse_sizes, no range syntax:
    Lx and Ly are independent and a range over pairs is ambiguous, so
    every shape is spelled out explicitly.
    """
    shapes = []
    for part in spec.split(","):
        part = part.strip()
        if "x" not in part:
            raise SubmissionRejected(f"'sizes' entries must look like 'LxxLy' (e.g. '8x4'), got {part!r}")
        lx_str, _, ly_str = part.partition("x")
        try:
            shapes.append((int(lx_str), int(ly_str)))
        except ValueError:
            raise SubmissionRejected(f"'sizes' entries must look like 'LxxLy' (e.g. '8x4'), got {part!r}")
    return shapes


def validate_shapes(sizes_str: str) -> list[tuple[int, int]]:
    shapes = parse_shapes(sizes_str)
    if not shapes:
        raise SubmissionRejected("'sizes' is empty")
    for lx, ly in shapes:
        if not (MIN_SIZE <= lx <= MAX_SIZE and MIN_SIZE <= ly <= MAX_SIZE):
            raise SubmissionRejected(
                f"each of Lx, Ly must be between {MIN_SIZE} and {MAX_SIZE}, got ({lx}, {ly})"
            )
    return shapes


def validate_mixed_sizes(sizes_str: str) -> list[int | tuple[int, int]]:
    """'3-15,8x12' -> [3, 4, ..., 15, (8, 12)] -- the square-lattice
    challenge's sizes grammar, extended to also accept explicit "LxxLy"
    rectangle pairs alongside its existing integer/range syntax, mixed in
    the same comma-separated string. A submission can claim off-square
    (Lx != Ly) shapes this way; every claimed shape still gets verified,
    scored, and cached (see scripts/update_leaderboard.py's is_showcased),
    it just won't necessarily appear in LEADERBOARD.md's 3x3..15x15 grid.

    Splits the comma-separated parts by whether they contain "x", then
    reuses validate_sizes/validate_shapes for their respective halves --
    so an all-integer input validates to exactly the same list[int] as
    plain validate_sizes (existing manifests are unaffected), and bounds/
    rejection messages stay identical to each half's own validator.
    """
    plain_parts, shape_parts = [], []
    for part in sizes_str.split(","):
        part = part.strip()
        (shape_parts if "x" in part else plain_parts).append(part)

    sizes: list[int | tuple[int, int]] = []
    if plain_parts:
        sizes += validate_sizes(",".join(plain_parts))
    if shape_parts:
        sizes += validate_shapes(",".join(shape_parts))
    if not sizes:
        raise SubmissionRejected("'sizes' is empty")
    return sizes


def validate_manifest(manifest: dict) -> dict:
    """Checks a parsed submission.json dict. Returns it back with "sizes"
    replaced by the parsed value if valid: for the square-lattice challenge
    a list mixing plain ints (Lx=Ly) and explicit (Lx, Ly) pairs (see
    validate_mixed_sizes); for the graph challenge (hexagonal/triangular/
    periodic variants -- see "graph" below) always a list of explicit
    (Lx, Ly) pairs (see validate_shapes). Raises SubmissionRejected with a
    specific reason if anything is invalid.
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

    generated_by = manifest.get("generated_by")
    if generated_by is not None and not isinstance(generated_by, str):
        raise SubmissionRejected(f"'generated_by' must be a string if given, got {generated_by!r}")

    graph = manifest.get("graph", "square")
    if graph != "square" and graph not in GRAPH_TYPES:
        raise SubmissionRejected(
            f"'graph' must be 'square' or one of {sorted(GRAPH_TYPES)} if given, got {graph!r}"
        )

    if not isinstance(manifest["sizes"], str):
        raise SubmissionRejected(f"'sizes' must be a string, got {manifest['sizes']!r}")
    if graph == "square":
        sizes = validate_mixed_sizes(manifest["sizes"])
    else:
        sizes = validate_shapes(manifest["sizes"])

    return {**manifest, "sizes": sizes, "graph": graph}


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


def check_at_size(
    encode_fn, order_fn, lx: int, ly: int | None = None, spec_builder=build_spec, model: str = "full"
) -> tuple[int, int]:
    """(total, max) at shape lx * ly, under the submission's own declared
    ordering (row_major -- or whatever spec_builder's own canonical default
    is -- if it declares none). Raises SubmissionRejected with a specific
    shape/reason if verify() fails -- never silently accepts a
    partially-working submission.

    ly defaults to lx -- every existing (square-lattice) caller passes a
    single size and keeps its exact current behavior unchanged. The graph
    challenge passes lx and ly independently (see harness.graphs.CANONICAL_SHAPE),
    since mode count alone doesn't pin down the graph there.

    spec_builder/model default to the square-lattice challenge's own
    harness.lattice.build_spec and the general-complex "full" Hamiltonian --
    every existing caller keeps its exact current behavior unchanged. The
    graph challenge (hexagonal/triangular/periodic lattices) passes a
    spec_builder that closes over which named graph to build (see
    harness.graphs.build_spec), keeping the same "full" model -- both
    challenges score D = Num + ReHop + ImHop + Inter, so model never
    actually needs overriding today, just spec_builder.
    """
    if ly is None:
        ly = lx
    spec = spec_builder(lx, ly, order_fn)
    terms = hamiltonian(spec, model=model)
    result = evaluate(spec, encode_fn, terms)
    if not result["passed"]:
        raise SubmissionRejected(f"FAILED at {lx}x{ly}: {summarize_failure(result)}")
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

    Path.glob("*.py") is non-recursive, so harness/v2/ (the ancilla/
    stabilizer extension) is invisible to this -- deliberately: it lives
    in its own subpackage specifically so its existence, or any change to
    it, never invalidates this cache. See harness_v2_fingerprint() below
    for its own, separate analogue.
    """
    hasher = hashlib.sha256()
    for path in sorted((REPO_ROOT / "harness").glob("*.py")):
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Ancilla/stabilizer challenge (harness.v2) -- additive to everything above.
# A submission here declares "challenge": "ancillas" in submission.json (see
# inbox/README.md); scripts/process_inbox.py dispatches on that field before
# ever touching the functions above, so an ordinary square/graph submission's
# path through this module is completely unchanged.
# ---------------------------------------------------------------------------

# The weight cap a submission is held to is CHOSEN BY THE SUBMISSION
# ("max_weight" in submission.json), not fixed by the challenge -- the whole
# point of this challenge is the ancilla-count/locality trade-off curve, and
# pinning one cap would only ever show one point on it. A submission omitting
# the field means 3 (the tightest cap any published construction reaches, and
# what every entry registered before the field existed was held to), so
# existing manifests and registry entries keep their exact meaning.
#
# Which caps get a rendered leaderboard table/chart is a separate, purely
# presentational decision, and lives in scripts/update_leaderboard_ancillas.py
# (ANCILLA_SHOWCASED_MAX_WEIGHTS) -- same "verified, scored, and cached
# always; shown only if showcased" split as is_showcased() draws for shapes
# in the ancilla-free challenges.
ANCILLA_DEFAULT_MAX_WEIGHT = 3
ANCILLA_GRAPH_TYPES = {"square", "hexagonal"}
ANCILLA_BASELINES_DIR = REPO_ROOT / "harness" / "v2" / "baselines"
ANCILLA_REGISTRY_PATH = ANCILLA_BASELINES_DIR / "registry.json"
ANCILLA_CACHE_PATH = REPO_ROOT / ".leaderboard_cache_ancillas.json"


def harness_v2_fingerprint() -> str:
    """The ancilla challenge's own analogue of harness_fingerprint(): hashes
    harness/v2/*.py (non-recursive, so harness/v2/baselines/ -- the
    ancilla-challenge equivalent of baselines/, individually hashed per
    submission the same way baselines/*.py already are -- is excluded, same
    split as harness/ vs baselines/ proper). Gates .leaderboard_cache_ancillas.json.
    """
    hasher = hashlib.sha256()
    for path in sorted((REPO_ROOT / "harness" / "v2").glob("*.py")):
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def load_ancilla_registry() -> dict:
    if not ANCILLA_REGISTRY_PATH.is_file():
        return {}
    return json.loads(ANCILLA_REGISTRY_PATH.read_text())


def save_ancilla_registry(registry: dict) -> None:
    ANCILLA_BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    ANCILLA_REGISTRY_PATH.write_text(json.dumps(registry, indent=2) + "\n")


def ancilla_registry_entry(
    name: str, sizes: list, label: str, graph: str, has_represent: bool,
    max_weight: int = ANCILLA_DEFAULT_MAX_WEIGHT, generated_by=None, submitted_at=None,
) -> dict:
    entry = {
        "module": f"harness.v2.baselines.{name}", "sizes": sizes, "label": label,
        "graph": graph, "has_represent": has_represent, "max_weight": max_weight,
    }
    if generated_by is not None:
        entry["generated_by"] = generated_by
    if submitted_at is not None:
        entry["submitted_at"] = submitted_at
    return entry


def validate_ancilla_manifest(manifest: dict) -> dict:
    """Like validate_manifest, but for a "challenge": "ancillas" submission
    -- a separate function, not a branch inside validate_manifest, since the
    allowed graph choices (square/hexagonal only, no triangular or periodic
    variants -- see NOTES.md) and the extra "max_weight" field differ from
    the ancilla-free challenges' own manifest shape.

    Returns the manifest with "sizes" parsed, "graph" defaulted to "square",
    and "max_weight" defaulted to ANCILLA_DEFAULT_MAX_WEIGHT.
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

    generated_by = manifest.get("generated_by")
    if generated_by is not None and not isinstance(generated_by, str):
        raise SubmissionRejected(f"'generated_by' must be a string if given, got {generated_by!r}")

    graph = manifest.get("graph", "square")
    if graph not in ANCILLA_GRAPH_TYPES:
        raise SubmissionRejected(
            f"'graph' must be one of {sorted(ANCILLA_GRAPH_TYPES)} for the ancilla challenge, got {graph!r}"
        )

    # The weight cap this submission claims to satisfy. Any positive integer
    # -- the challenge doesn't pick one for you (see ANCILLA_DEFAULT_MAX_WEIGHT
    # above). A bool is rejected explicitly: isinstance(True, int) is True in
    # Python, and silently reading "max_weight": true as a cap of 1 would be a
    # baffling rejection message downstream.
    max_weight = manifest.get("max_weight", ANCILLA_DEFAULT_MAX_WEIGHT)
    if isinstance(max_weight, bool) or not isinstance(max_weight, int) or max_weight < 1:
        raise SubmissionRejected(f"'max_weight' must be a positive integer if given, got {max_weight!r}")

    if not isinstance(manifest["sizes"], str):
        raise SubmissionRejected(f"'sizes' must be a string, got {manifest['sizes']!r}")
    sizes = validate_mixed_sizes(manifest["sizes"]) if graph == "square" else validate_shapes(manifest["sizes"])

    return {**manifest, "sizes": sizes, "graph": graph, "max_weight": max_weight}


def check_ancilla_at_size(
    encode_fn, represent_fn, order_fn, lx: int, ly: int | None = None,
    graph: str = "square", max_weight: int = ANCILLA_DEFAULT_MAX_WEIGHT,
) -> tuple[int, int, int]:
    """(n_ancillas, achieved_max_weight, total_weight) at shape lx * ly for
    the ancilla challenge. Raises SubmissionRejected if verification fails OR
    if the achieved max weight exceeds `max_weight` -- the cap the submission
    itself claimed. A submission must back that claim at every size it
    claims, exactly like the ancilla-free challenges' own check_at_size never
    silently accepts a partial pass.

    Note the returned max weight is what the encoding ACHIEVED, not the cap
    it claimed -- an encoding claiming <= 4 that actually reaches 3
    everywhere qualifies for the weight-3 leaderboard too, and
    scripts/update_leaderboard_ancillas.py ranks on the achieved value for
    exactly that reason.
    """
    from harness.graphs import build_spec as build_graph_spec
    from harness.v2.evaluate import evaluate_extended
    from harness.v2.hamiltonian_terms import hamiltonian_terms

    if ly is None:
        ly = lx
    spec = build_spec(lx, ly, order_fn) if graph == "square" else build_graph_spec(graph, lx, ly, order_fn)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, encode_fn, terms, represent_fn)
    if not result["passed"]:
        raise SubmissionRejected(f"FAILED at {lx}x{ly}: {summarize_ancilla_failure(result)}")
    if result["max_weight"] > max_weight:
        raise SubmissionRejected(
            f"FAILED at {lx}x{ly}: max_weight {result['max_weight']} exceeds the "
            f"cap of {max_weight} this submission claims"
        )
    return result["n_ancillas"], result["max_weight"], result["total_weight"]


def summarize_ancilla_failure(result: dict) -> str:
    """summarize_failure()'s analogue for an evaluate_extended() result --
    also has to handle the stabilizer checks (2-4) evaluate_extended adds,
    which summarize_failure's legacy-only check dict doesn't know about.
    """
    if "error" in result:
        return result["error"]
    checks = result["checks"]
    for name in ("well_formed", "majorana_algebra", "stabilizers_well_formed", "stabilizers_abelian", "stabilizers_compatible", "codespace_dimension"):
        check = checks.get(name)
        if check is not None and not check["passed"]:
            if name == "majorana_algebra":
                examples = ", ".join(str(v) for v in check["violations"][:5])
                more = f" (+{check['n_violations'] - 5} more)" if check["n_violations"] > 5 else ""
                return f"{check['n_violations']} Majorana pairs fail to anticommute, e.g. {examples}{more}"
            if name == "well_formed":
                return "malformed mapping: " + "; ".join(check["issues"])
            if name == "stabilizers_well_formed":
                return "malformed stabilizers: " + "; ".join(check["issues"])
            return f"check {name!r} failed: {check}"
    return "unknown failure"


def load_score_cache() -> dict:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def save_score_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")
