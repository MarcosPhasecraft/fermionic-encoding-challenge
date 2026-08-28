"""Fully automated submission pipeline -- no manual flags, no AI judgment
calls. Run it after dropping one or more submission folders into inbox/:

    python3 scripts/process_inbox.py

For every immediate subdirectory of inbox/ (skipping hidden/junk entries
like .DS_Store), in sorted order:

  1. Validate inbox/<dir>/submission.json against the documented schema
     (see inbox/README.md) -- name/label/sizes required, generated_by
     optional.
  2. Validate inbox/<dir>/encode.py by parsing it (not executing it) and
     rejecting any file that doesn't define exactly one top-level
     encode(), or that defines any top-level function name more than
     once -- the guard against a file with a previous submission's code
     left in it.
  3. Reject a --name already present in baselines/registry.json.
  4. Run the exact same verify() gate scripts/submit_baseline.py uses,
     at every size the manifest claims (scripts/submission_lib.py's
     check_at_size -- shared, not reimplemented). Progress prints live,
     one line per size, as each one finishes -- a submission whose own
     encode() does something expensive (a local search, an ensemble of
     several restarts) can legitimately take minutes per size; this is
     what tells you it's still working rather than stuck.

A submission that fails any step is reported with a concrete reason and
left untouched in inbox/ -- it's automatically retried the next run once
fixed, no separate rejected-folder bookkeeping. One submission's
unexpected crash doesn't stop the others in the same run.

A submission that passes gets copied to baselines/<name>.py, registered
in registry.json (with an acceptance timestamp stamped here, from this
machine's clock -- never taken from the submission itself -- and
generated_by copied through if given), and its inbox folder is moved to
inbox/_processed/<timestamp>_<name>/ (e.g. 20260828-144437_alice_bk/) --
sortable by acceptance order, a local record of exactly what was
submitted.

If anything was newly accepted this run: LEADERBOARD.md is regenerated
(scripts/update_leaderboard.py, run as a fresh subprocess so it reads the
just-written registry.json with no stale-import risk), the full test
suite is re-run as a sanity check, a summary is printed, and -- the only
place this script asks you anything -- you're prompted right here on the
terminal whether to push to GitHub, commit locally only, or do neither.
No AI is involved in that decision or in carrying it out.
"""

import argparse
import json
import subprocess
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, so `scripts` resolves as a package
# Imported as scripts.submission_lib (not bare `submission_lib`) so this is
# the exact same module object whether this script is run directly or
# imported as scripts.process_inbox elsewhere (e.g. tests monkeypatching
# scripts.submission_lib.BASELINES_DIR/REGISTRY_PATH for isolation) -- a
# bare `import submission_lib` would give tests a second, disconnected
# copy of this module that monkeypatching wouldn't reach.
from scripts import submission_lib  # noqa: E402
from scripts.submission_lib import (  # noqa: E402
    REPO_ROOT,
    SubmissionRejected,
    check_at_size,
    load_registry,
    registry_entry,
    save_registry,
    validate_encode_source,
    validate_manifest,
)
# submission_lib.BASELINES_DIR is read via the module (not `from`-imported)
# at the point of use, not here -- so a test can monkeypatch
# submission_lib.BASELINES_DIR and have this script's writes follow it.

from harness.loading import load_submission

INBOX = REPO_ROOT / "inbox"
PROCESSED = INBOX / "_processed"
_IGNORED_DIR_NAMES = {"_processed", "__pycache__"}


def _pending_submission_dirs() -> list[Path]:
    if not INBOX.is_dir():
        return []
    return sorted(
        p for p in INBOX.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in _IGNORED_DIR_NAMES
    )


def _process_one(folder: Path, registry: dict) -> dict:
    """Returns {"name": ..., "accepted": bool, "reason"/"scores": ...}.
    Raises nothing -- every failure mode is caught and reported."""
    try:
        manifest_path = folder / "submission.json"
        encode_path = folder / "encode.py"
        if not manifest_path.is_file():
            raise SubmissionRejected("missing submission.json")
        if not encode_path.is_file():
            raise SubmissionRejected("missing encode.py")

        try:
            raw_manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            raise SubmissionRejected(f"submission.json is not valid JSON: {e}")
        manifest = validate_manifest(raw_manifest)

        name = manifest["name"]
        if name in registry:
            raise SubmissionRejected(f"'{name}' is already registered -- choose a different name")

        validate_encode_source(encode_path.read_text())

        encode_fn, order_fn = load_submission(str(encode_path))
        print(f"\ntesting {folder.name!r} ('{manifest['name']}') at sizes {manifest['sizes']} ...", flush=True)
        scores = {}
        for l in manifest["sizes"]:
            total, max_weight = check_at_size(encode_fn, order_fn, l)
            scores[l] = {"total": total, "max": max_weight}
            print(f"  {l}x{l}: total={total} max={max_weight}", flush=True)

        dest = submission_lib.BASELINES_DIR / f"{name}.py"
        shutil.copy(encode_path, dest)
        now = datetime.now(timezone.utc)
        submitted_at = now.isoformat(timespec="seconds")
        registry[name] = registry_entry(
            name, manifest["sizes"], manifest["label"],
            generated_by=manifest.get("generated_by"), submitted_at=submitted_at,
        )
        save_registry(registry)

        # Archived under <timestamp>_<name> -- sortable by acceptance
        # order, and name alone (already a clean identifier by
        # validate_manifest's pattern) is informative without needing to
        # sanitize free-text label/generated_by into a filename; both stay
        # readable in the archived submission.json itself.
        PROCESSED.mkdir(parents=True, exist_ok=True)
        archived_name = f"{now.strftime('%Y%m%d-%H%M%S')}_{name}"
        shutil.move(str(folder), str(PROCESSED / archived_name))

        return {"name": name, "label": manifest["label"], "accepted": True,
                "scores": scores, "submitted_at": submitted_at,
                "generated_by": manifest.get("generated_by")}

    except SubmissionRejected as e:
        return {"name": folder.name, "accepted": False, "reason": str(e)}
    except Exception as e:  # noqa: BLE001 -- one submission's bug must not kill the batch
        return {"name": folder.name, "accepted": False, "reason": f"{type(e).__name__}: {e}"}


def _print_summary(results: list[dict]) -> None:
    accepted = [r for r in results if r["accepted"]]
    rejected = [r for r in results if not r["accepted"]]

    print("\n" + "=" * 60)
    print(f"{len(accepted)} accepted, {len(rejected)} rejected")
    print("=" * 60)

    for r in accepted:
        print(f"\n[ACCEPTED] {r['name']!r} -- {r['label']}")
        print(f"  submitted_at: {r['submitted_at']}")
        if r["generated_by"]:
            print(f"  generated_by: {r['generated_by']}")
        for l, s in sorted(r["scores"].items()):
            print(f"  {l}x{l}: total={s['total']} max={s['max']}")

    for r in rejected:
        print(f"\n[REJECTED] {r['name']!r}: {r['reason']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true", help="skip the post-acceptance pytest run (faster; used by this project's own test suite)")
    parser.add_argument("--skip-leaderboard", action="store_true", help="skip regenerating LEADERBOARD.md (faster dry runs; used by this project's own test suite)")
    args = parser.parse_args()

    pending = _pending_submission_dirs()
    if not pending:
        print("inbox/ has nothing pending.")
        return
    print(f"{len(pending)} pending: {', '.join(p.name for p in pending)}")

    registry = load_registry()
    results = [_process_one(folder, registry) for folder in pending]
    _print_summary(results)

    accepted = [r for r in results if r["accepted"]]
    if not accepted:
        return

    if not args.skip_leaderboard:
        print("\nRegenerating LEADERBOARD.md ...")
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "update_leaderboard.py")], check=True, cwd=REPO_ROOT)

    if not args.skip_tests:
        print("\nRunning the test suite ...")
        test_result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=REPO_ROOT)
        if test_result.returncode != 0:
            print("\n*** TEST SUITE FAILED -- review before committing. ***")

    touched = ["baselines/registry.json", "LEADERBOARD.md"] + [f"baselines/{r['name']}.py" for r in accepted]
    print("\nFiles touched this run:")
    for f in touched:
        print(f"  {f}")

    answer = input("\nPush to GitHub, commit locally only, or do neither? [push/commit/none]: ").strip().lower()
    if answer not in ("push", "commit"):
        print("Leaving changes uncommitted.")
        return

    subprocess.run(["git", "add", *touched], check=True, cwd=REPO_ROOT)
    names = ", ".join(r["name"] for r in accepted)
    message = f"Add submission(s) via scripts/process_inbox.py: {names}"
    subprocess.run(["git", "commit", "-m", message], check=True, cwd=REPO_ROOT)
    print("Committed locally.")

    if answer == "push":
        subprocess.run(["git", "push"], check=True, cwd=REPO_ROOT)
        print("Pushed.")


if __name__ == "__main__":
    main()
