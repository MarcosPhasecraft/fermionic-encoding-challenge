"""Test a candidate submission and, if it passes at every size it claims,
promote it into baselines/ and register it in registry.json.

    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --sizes 8
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --sizes 3-15
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname   # sizes default to 3-15

Never touches baselines/ or registry.json unless the submission passes
verify() at every claimed size, under all three of the harness's built-in
orderings (row_major, snake, diagonal). Sizes are restricted to 3..15,
the leaderboard's current range.

Does NOT regenerate LEADERBOARD.md itself -- run scripts/update_leaderboard.py
afterward. Kept separate since that script re-evaluates every registered
baseline (increasingly expensive as more get added), not just the new one.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle
from harness.loading import load_encode_fn

ORDERINGS = ("row_major", "snake", "diagonal")
REGISTRY_PATH = REPO_ROOT / "baselines" / "registry.json"
MIN_SIZE, MAX_SIZE = 3, 15


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


def check_at_size(encode_fn, l: int) -> tuple[int, int]:
    """Best (total, max) over the three orderings at size l x l. Raises
    with a specific size/ordering/reason if verify() fails anywhere --
    never silently accepts a partially-working submission.
    """
    best_total = best_max = None
    for ordering in ORDERINGS:
        spec = rectangle(l, l, ordering=ordering)
        terms = hamiltonian(spec, model="full")
        result = evaluate(spec, encode_fn, terms)
        if not result["passed"]:
            raise SystemExit(f"FAILED at {l}x{l}, ordering={ordering}: {summarize_failure(result)}")
        if best_total is None or result["total_weight"] < best_total:
            best_total = result["total_weight"]
        if best_max is None or result["max_weight"] < best_max:
            best_max = result["max_weight"]
    return best_total, best_max


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="path to the candidate encode.py")
    parser.add_argument("--name", required=True, help="registry name, e.g. 'my_solution'")
    parser.add_argument("--sizes", default=f"{MIN_SIZE}-{MAX_SIZE}", help="e.g. '8' or '3-15' or '8,10,12'")
    parser.add_argument("--force", action="store_true", help="overwrite an existing registry entry with this name")
    args = parser.parse_args()

    sizes = parse_sizes(args.sizes)
    if not all(MIN_SIZE <= l <= MAX_SIZE for l in sizes):
        raise SystemExit(f"sizes must be between {MIN_SIZE} and {MAX_SIZE} (the leaderboard's current range)")

    with open(REGISTRY_PATH) as f:
        registry = json.load(f)
    if args.name in registry and not args.force:
        raise SystemExit(f"'{args.name}' is already registered -- pass --force to overwrite it")

    encode_fn = load_encode_fn(args.file)

    print(f"testing '{args.name}' at sizes {sizes} ...")
    for l in sizes:
        total, max_weight = check_at_size(encode_fn, l)
        print(f"  {l}x{l}: total={total} max={max_weight}")

    dest = REPO_ROOT / "baselines" / f"{args.name}.py"
    shutil.copy(args.file, dest)
    registry[args.name] = {"module": f"baselines.{args.name}", "sizes": sizes}
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    print(f"\nPASSED at every claimed size.")
    print(f"Added baselines/{args.name}.py and updated registry.json.")
    print("Now run: python3 scripts/update_leaderboard.py")


if __name__ == "__main__":
    main()
