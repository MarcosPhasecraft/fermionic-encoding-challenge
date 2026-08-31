"""Test a single candidate file by hand and, if it passes at every size it
claims, promote it into baselines/ and register it in registry.json.

    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --sizes 8
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --sizes 3-15
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname   # sizes default to 3-15
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --label "Their BK variant"
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname_tri --graph triangular --sizes 3-15

--name is the tidy filesystem-safe registry key (becomes baselines/<name>.py);
--label is what actually shows on the leaderboard (defaults to --name if
omitted) -- kept separate so the leaderboard doesn't have to show a raw
slug like "alice_bk_v2" for an external submission. --graph defaults to
"square" (LEADERBOARD.md, plain integer/range sizes, or a mix with
explicit LxxLy pairs -- see submission_lib.validate_mixed_sizes); set it
to one of harness.graphs.GRAPH_TYPES for the graph challenge instead
(LEADERBOARD_GRAPHS.md, sizes must be explicit LxxLy pairs -- no default,
must be passed explicitly since there's no square-lattice-style "L means
Lx=Ly=L" shorthand across graph types with different canonical shapes).

Never touches baselines/ or registry.json unless the submission passes
verify() at every claimed size, under the submission's own declared
order(Lx, Ly) -> perm (row_major -- or that graph type's own canonical
default -- if it declares none). Sizes are restricted to 3..15 per
dimension, the leaderboard's current range.

This is the manual, one-file-at-a-time path -- for handling a batch of
submissions sitting in inbox/ with no manual intervention at all, see
scripts/process_inbox.py instead. Both share their actual pass/fail logic
via scripts/submission_lib.py.

Does NOT regenerate LEADERBOARD.md itself -- run scripts/update_leaderboard.py
afterward. Kept separate since that script re-evaluates every registered
baseline (increasingly expensive as more get added), not just the new one.
"""

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, so `scripts` resolves as a package
# Imported as scripts.submission_lib, not bare `submission_lib` -- see
# scripts/process_inbox.py's identical comment for why that distinction
# matters (module-identity, not just resolvability).
from scripts import submission_lib  # noqa: E402
from scripts.submission_lib import (  # noqa: E402
    MAX_SIZE,
    MIN_SIZE,
    SubmissionRejected,
    check_at_size,
    load_registry,
    registry_entry,
    save_registry,
    validate_mixed_sizes,
    validate_shapes,
)

from harness.graphs import GRAPH_TYPES, build_spec as build_graph_spec  # noqa: E402
from harness.loading import load_submission


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="path to the candidate encode.py")
    parser.add_argument("--name", required=True, help="registry name, e.g. 'my_solution'")
    parser.add_argument(
        "--graph", default="square",
        help="'square' (default, LEADERBOARD.md) or one of harness.graphs.GRAPH_TYPES (LEADERBOARD_GRAPHS.md)",
    )
    parser.add_argument(
        "--sizes", default=None,
        help="square: e.g. '8', '3-15', or '3-15,8x12' (default: '3-15'). "
             "graph types: explicit LxxLy pairs, e.g. '8x8,15x15' (required, no default)",
    )
    parser.add_argument("--label", default=None, help="human-readable leaderboard display name (default: --name)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing registry entry with this name")
    args = parser.parse_args()

    if args.graph != "square" and args.graph not in GRAPH_TYPES:
        raise SystemExit(f"--graph must be 'square' or one of {sorted(GRAPH_TYPES)}, got {args.graph!r}")

    try:
        if args.graph == "square":
            sizes = validate_mixed_sizes(args.sizes or f"{MIN_SIZE}-{MAX_SIZE}")
            spec_kwargs = {}
        else:
            if args.sizes is None:
                raise SystemExit(f"--sizes is required for --graph {args.graph!r} (e.g. '8x8,15x15')")
            sizes = validate_shapes(args.sizes)
            spec_builder = lambda Lx, Ly, order_fn, graph=args.graph: build_graph_spec(graph, Lx, Ly, order_fn)
            spec_kwargs = {"spec_builder": spec_builder}
    except SubmissionRejected as e:
        raise SystemExit(str(e))

    registry = load_registry()
    if args.name in registry and not args.force:
        raise SystemExit(f"'{args.name}' is already registered -- pass --force to overwrite it")

    encode_fn, order_fn = load_submission(args.file)

    print(f"testing '{args.name}' at sizes {sizes} (graph={args.graph!r}) ...")
    try:
        for s in sizes:
            lx, ly = (s, s) if isinstance(s, int) else s
            total, max_weight = check_at_size(encode_fn, order_fn, lx, ly, **spec_kwargs)
            print(f"  {lx}x{ly}: total={total} max={max_weight}")
    except SubmissionRejected as e:
        raise SystemExit(str(e))

    dest = submission_lib.BASELINES_DIR / f"{args.name}.py"
    if Path(args.file).resolve() != dest.resolve():
        shutil.copy(args.file, dest)
    # Stamped here, from this machine's clock -- never left unset -- so a
    # baseline registered this way still gets a real date for
    # scripts/progress_chart.py's staircase/reference-line lookups, same
    # as process_inbox.py's own submissions already do.
    submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    registry[args.name] = registry_entry(
        args.name, sizes, args.label or args.name, submitted_at=submitted_at, graph=args.graph,
    )
    save_registry(registry)

    print(f"\nPASSED at every claimed size.")
    print(f"Added baselines/{args.name}.py and updated registry.json, labelled {registry[args.name]['label']!r}.")
    print("Now run: python3 scripts/update_leaderboard.py")


if __name__ == "__main__":
    main()
