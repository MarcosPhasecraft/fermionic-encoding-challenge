"""Test a single candidate file by hand and, if it passes at every size it
claims, promote it into baselines/ and register it in registry.json.

    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --sizes 8
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --sizes 3-15
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname   # sizes default to 3-15
    python3 scripts/submit_baseline.py --file their_encode.py --name theirname --label "Their BK variant"

--name is the tidy filesystem-safe registry key (becomes baselines/<name>.py);
--label is what actually shows on the leaderboard (defaults to --name if
omitted) -- kept separate so the leaderboard doesn't have to show a raw
slug like "alice_bk_v2" for an external submission.

Never touches baselines/ or registry.json unless the submission passes
verify() at every claimed size, under the submission's own declared
order(Lx, Ly) -> perm (row_major if it declares none -- see
harness.lattice.build_spec). Sizes are restricted to 3..15, the
leaderboard's current range.

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
    validate_sizes,
)

from harness.loading import load_submission


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="path to the candidate encode.py")
    parser.add_argument("--name", required=True, help="registry name, e.g. 'my_solution'")
    parser.add_argument("--sizes", default=f"{MIN_SIZE}-{MAX_SIZE}", help="e.g. '8' or '3-15' or '8,10,12'")
    parser.add_argument("--label", default=None, help="human-readable leaderboard display name (default: --name)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing registry entry with this name")
    args = parser.parse_args()

    try:
        sizes = validate_sizes(args.sizes)
    except SubmissionRejected as e:
        raise SystemExit(str(e))

    registry = load_registry()
    if args.name in registry and not args.force:
        raise SystemExit(f"'{args.name}' is already registered -- pass --force to overwrite it")

    encode_fn, order_fn = load_submission(args.file)

    print(f"testing '{args.name}' at sizes {sizes} ...")
    try:
        for l in sizes:
            total, max_weight = check_at_size(encode_fn, order_fn, l)
            print(f"  {l}x{l}: total={total} max={max_weight}")
    except SubmissionRejected as e:
        raise SystemExit(str(e))

    dest = submission_lib.BASELINES_DIR / f"{args.name}.py"
    shutil.copy(args.file, dest)
    registry[args.name] = registry_entry(args.name, sizes, args.label or args.name)
    save_registry(registry)

    print(f"\nPASSED at every claimed size.")
    print(f"Added baselines/{args.name}.py and updated registry.json, labelled {registry[args.name]['label']!r}.")
    print("Now run: python3 scripts/update_leaderboard.py")


if __name__ == "__main__":
    main()
