"""Test a single candidate ancilla/stabilizer encoding by hand and, if it
passes at every size it claims (verify_extended + max_weight <= the
ancilla challenge's fixed cap), promote it into harness/v2/baselines/ and
register it in harness/v2/baselines/registry.json.

    python3 scripts/submit_ancilla_baseline.py --file harness/v2/baselines/dk.py \
        --name dk --graph square --sizes 3-15 --label "Derby-Klassen"

The ancilla-challenge analogue of scripts/submit_baseline.py -- same
manual, one-file-at-a-time role, sharing its actual pass/fail logic via
scripts/submission_lib.py's check_ancilla_at_size, but writing to
harness/v2/baselines/registry.json instead of baselines/registry.json.
For a batch of submissions sitting in inbox/, see scripts/process_inbox.py
instead (dispatches on submission.json's "challenge": "ancillas" field).

Does NOT regenerate LEADERBOARD_ANCILLAS.md itself -- run
scripts/update_leaderboard_ancillas.py afterward.
"""

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import submission_lib  # noqa: E402
from scripts.submission_lib import (  # noqa: E402
    ANCILLA_DEFAULT_MAX_WEIGHT,
    ANCILLA_GRAPH_TYPES,
    MAX_SIZE,
    MIN_SIZE,
    SubmissionRejected,
    ancilla_registry_entry,
    check_ancilla_at_size,
    load_ancilla_registry,
    save_ancilla_registry,
    validate_mixed_sizes,
    validate_shapes,
)

from harness.v2.loading import load_submission_extended


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="path to the candidate encode.py (may also define represent())")
    parser.add_argument("--name", required=True)
    parser.add_argument("--graph", default="square", choices=sorted(ANCILLA_GRAPH_TYPES))
    parser.add_argument("--sizes", required=True, help="square: e.g. '3-15'; hexagonal: explicit 'LxxLy' pairs")
    parser.add_argument("--label", default=None)
    parser.add_argument(
        "--max-weight", type=int, default=ANCILLA_DEFAULT_MAX_WEIGHT,
        help=f"the max Pauli weight cap this encoding claims to satisfy (default {ANCILLA_DEFAULT_MAX_WEIGHT})",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.max_weight < 1:
        raise SystemExit(f"--max-weight must be a positive integer, got {args.max_weight}")

    try:
        sizes = validate_mixed_sizes(args.sizes) if args.graph == "square" else validate_shapes(args.sizes)
    except SubmissionRejected as e:
        raise SystemExit(str(e))

    registry = load_ancilla_registry()
    if args.name in registry and not args.force:
        raise SystemExit(f"'{args.name}' is already registered -- pass --force to overwrite it")

    encode_fn, order_fn, represent_fn = load_submission_extended(args.file)

    print(f"testing '{args.name}' at sizes {sizes} (graph={args.graph!r}, max_weight<={args.max_weight}) ...")
    try:
        for s in sizes:
            lx, ly = (s, s) if isinstance(s, int) else s
            n_ancillas, max_weight, total_weight = check_ancilla_at_size(
                encode_fn, represent_fn, order_fn, lx, ly, graph=args.graph, max_weight=args.max_weight,
            )
            print(f"  {lx}x{ly}: n_ancillas={n_ancillas} max_weight={max_weight} total_weight={total_weight}")
    except SubmissionRejected as e:
        raise SystemExit(str(e))

    dest = submission_lib.ANCILLA_BASELINES_DIR / f"{args.name}.py"
    if Path(args.file).resolve() != dest.resolve():
        shutil.copy(args.file, dest)

    submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    registry[args.name] = ancilla_registry_entry(
        args.name, sizes, args.label or args.name, args.graph, represent_fn is not None,
        max_weight=args.max_weight, submitted_at=submitted_at,
    )
    save_ancilla_registry(registry)

    print(f"\nPASSED at every claimed size.")
    print(f"Added harness/v2/baselines/{args.name}.py and updated registry.json, labelled {registry[args.name]['label']!r}.")
    print("Now run: python3 scripts/update_leaderboard_ancillas.py")


if __name__ == "__main__":
    main()
