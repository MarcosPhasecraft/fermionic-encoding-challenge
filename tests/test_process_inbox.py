"""Light end-to-end test for scripts/process_inbox.py -- runs the real
pipeline logic (real verify(), real registry read/write) against a fully
isolated temp inbox/registry/baselines/leaderboard-cache directory via
monkeypatching, so it never touches this repo's actual inbox/, baselines/,
registry.json, or .leaderboard_cache.json (the last of these was caught
leaking real entries while first adding _prewarm_leaderboard_cache, before
_isolate() below monkeypatched CACHE_PATH too). Feeds "none" to the git
prompt so no git command ever runs, and passes --skip-tests
--skip-leaderboard so it doesn't spawn a nested pytest run or an expensive
leaderboard regen.
"""

import json

import scripts.process_inbox as process_inbox
import scripts.submission_lib as submission_lib


def _write_submission(inbox_dir, folder_name, name, label, sizes="3", encode_source=None, memory_files=None):
    folder = inbox_dir / folder_name
    folder.mkdir(parents=True)
    (folder / "encode.py").write_text(encode_source or "from baselines.jw import encode\n")
    (folder / "submission.json").write_text(json.dumps({"name": name, "label": label, "sizes": sizes}))
    if memory_files:
        memory_dir = folder / "memory"
        memory_dir.mkdir()
        for filename, content in memory_files.items():
            (memory_dir / filename).write_text(content)
    return folder


def _isolate(tmp_path, monkeypatch):
    baselines_dir = tmp_path / "baselines"
    baselines_dir.mkdir()
    registry_path = baselines_dir / "registry.json"
    registry_path.write_text("{}\n")
    monkeypatch.setattr(submission_lib, "BASELINES_DIR", baselines_dir)
    monkeypatch.setattr(submission_lib, "REGISTRY_PATH", registry_path)
    # Isolate the leaderboard score cache too -- _process_one's acceptance
    # path calls _prewarm_leaderboard_cache, which reads/writes it. Without
    # this, every accepted-submission test here would leak an entry into
    # this repo's real .leaderboard_cache.json (caught happening for real
    # while adding this fix).
    monkeypatch.setattr(submission_lib, "CACHE_PATH", tmp_path / "leaderboard_cache.json")

    inbox_dir = tmp_path / "inbox"
    monkeypatch.setattr(process_inbox, "INBOX", inbox_dir)
    monkeypatch.setattr(process_inbox, "PROCESSED", inbox_dir / "_processed")

    monkeypatch.setattr("builtins.input", lambda _: "none")
    monkeypatch.setattr(
        "sys.argv", ["process_inbox.py", "--skip-tests", "--skip-leaderboard"]
    )
    return baselines_dir, registry_path, inbox_dir


def test_accepted_submission_lands_in_baselines(tmp_path, monkeypatch):
    baselines_dir, registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_submission(inbox_dir, "sub_1", "pytest_smoke_jw", "Pytest Smoke (JW copy)")

    process_inbox.main()

    assert (baselines_dir / "pytest_smoke_jw.py").is_file()
    registry = json.loads(registry_path.read_text())
    assert registry["pytest_smoke_jw"]["label"] == "Pytest Smoke (JW copy)"
    assert registry["pytest_smoke_jw"]["module"] == "baselines.pytest_smoke_jw"
    assert "submitted_at" in registry["pytest_smoke_jw"]
    assert not (inbox_dir / "sub_1").exists()
    # Archived as <timestamp>_<name>, not just <name> -- sortable by
    # acceptance order (scripts/process_inbox.py's archived_name).
    archived = list((inbox_dir / "_processed").iterdir())
    assert len(archived) == 1
    assert archived[0].name.endswith("_pytest_smoke_jw")
    assert (archived[0] / "submission.json").is_file()


def test_name_collision_rejected_and_not_registered(tmp_path, monkeypatch):
    baselines_dir, registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    registry_path.write_text(json.dumps({"jw": {"module": "baselines.jw", "sizes": [3], "label": "JW"}}))
    _write_submission(inbox_dir, "sub_1", "jw", "A Duplicate")

    process_inbox.main()

    registry = json.loads(registry_path.read_text())
    assert registry["jw"]["label"] == "JW"  # untouched, not overwritten
    assert not (baselines_dir / "jw.py").exists()
    assert (inbox_dir / "sub_1").exists()  # left in place, not moved


def test_duplicate_encode_definition_rejected(tmp_path, monkeypatch):
    baselines_dir, registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    bad_source = (
        "def encode(spec):\n    return {'old': True}\n\n"
        "def encode(spec):\n    return {'new': True}\n"
    )
    _write_submission(inbox_dir, "sub_1", "dupe", "Dupe", encode_source=bad_source)

    process_inbox.main()

    registry = json.loads(registry_path.read_text())
    assert "dupe" not in registry
    assert not (baselines_dir / "dupe.py").exists()
    assert (inbox_dir / "sub_1").exists()


def test_empty_inbox_is_a_noop(tmp_path, monkeypatch, capsys):
    _isolate(tmp_path, monkeypatch)
    process_inbox.main()
    assert "nothing pending" in capsys.readouterr().out


def test_accepted_submission_with_memory_folder_carries_it_into_baselines(tmp_path, monkeypatch):
    baselines_dir, registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_submission(
        inbox_dir, "sub_1", "pytest_smoke_memory", "Pytest Smoke (with memory)",
        memory_files={"notes.md": "# what I tried\n"},
    )

    process_inbox.main()

    memory_dir = baselines_dir / "pytest_smoke_memory.memory"
    assert memory_dir.is_dir()
    assert (memory_dir / "notes.md").read_text() == "# what I tried\n"


def test_accepted_submission_without_memory_folder_creates_none(tmp_path, monkeypatch):
    baselines_dir, registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_submission(inbox_dir, "sub_1", "pytest_smoke_no_memory", "Pytest Smoke (no memory)")

    process_inbox.main()

    # The optional path must be a true no-op, not an empty dir everywhere.
    assert not (baselines_dir / "pytest_smoke_no_memory.memory").exists()


# --- _files_touched: none of the "none"-answer tests above ever exercise
# the git-add path, so this is unit tested directly -- a memory folder
# missing from this list would silently stay untracked even after
# answering "commit".


def test_files_touched_includes_memory_folder_when_present():
    accepted = [{"name": "alice", "has_memory": True}]
    touched = process_inbox._files_touched(accepted, skip_leaderboard=False)
    assert "baselines/alice.memory" in touched
    assert "baselines/alice.py" in touched


def test_files_touched_omits_memory_folder_when_absent():
    accepted = [{"name": "bob", "has_memory": False}]
    touched = process_inbox._files_touched(accepted, skip_leaderboard=False)
    assert "baselines/bob.memory" not in touched
    assert "baselines/bob.py" in touched


def test_files_touched_omits_leaderboard_and_memory_index_when_skipped():
    accepted = [{"name": "alice", "has_memory": False}]
    touched = process_inbox._files_touched(accepted, skip_leaderboard=True)
    assert "LEADERBOARD.md" not in touched
    assert "MEMORY.md" not in touched
    assert "assets/progress_total_weight.png" not in touched


def test_files_touched_includes_progress_chart_when_not_skipped():
    accepted = [{"name": "alice", "has_memory": False}]
    touched = process_inbox._files_touched(accepted, skip_leaderboard=False)
    assert "assets/progress_total_weight.png" in touched


# --- _prewarm_leaderboard_cache: without this, a brand-new submission's
# scores -- already computed once here to decide pass/fail -- would be
# recomputed a second time when update_leaderboard.py runs moments later
# as a separate subprocess with no memory of what this process just did.


def test_prewarm_writes_a_valid_entry_when_harness_fingerprint_matches(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    real_fp = submission_lib.harness_fingerprint()  # not mocked -- the real, current one
    cache_path.write_text(json.dumps({"_harness_fingerprint": real_fp, "entries": {}}))
    monkeypatch.setattr(submission_lib, "CACHE_PATH", cache_path)

    dest = tmp_path / "alice.py"
    dest.write_text("from baselines.jw import encode\n")

    process_inbox._prewarm_leaderboard_cache("alice", dest, {3: {"total": 201, "max": 4}})

    cache = json.loads(cache_path.read_text())
    assert cache["entries"]["alice"]["fingerprint"] == submission_lib.hash_file(dest)
    assert cache["entries"]["alice"]["scores"]["3"] == {"total": 201, "max": 4}


def test_prewarm_is_a_noop_when_harness_fingerprint_does_not_match(tmp_path, monkeypatch):
    # The cache is about to be wiped wholesale by update_leaderboard.py's
    # own harness-fingerprint check anyway -- pre-populating one entry
    # into it would accomplish nothing.
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"_harness_fingerprint": "stale-fingerprint", "entries": {}}))
    monkeypatch.setattr(submission_lib, "CACHE_PATH", cache_path)

    dest = tmp_path / "alice.py"
    dest.write_text("from baselines.jw import encode\n")

    process_inbox._prewarm_leaderboard_cache("alice", dest, {3: {"total": 201, "max": 4}})

    cache = json.loads(cache_path.read_text())
    assert cache["entries"] == {}


def test_accepted_submission_prewarms_the_cache_end_to_end(tmp_path, monkeypatch):
    baselines_dir, registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    # Seed the isolated cache as already valid (matching the real current
    # harness fingerprint) -- otherwise this test can't distinguish
    # "correctly pre-warmed" from "correctly skipped because stale",
    # both of which leave the assertion-relevant entries dict looking
    # different, but only one of which is the scenario under test here.
    real_fp = submission_lib.harness_fingerprint()
    submission_lib.CACHE_PATH.write_text(json.dumps({"_harness_fingerprint": real_fp, "entries": {}}))

    _write_submission(inbox_dir, "sub_1", "pytest_smoke_prewarm", "Pytest Smoke (prewarm)")

    process_inbox.main()

    cache = json.loads(submission_lib.CACHE_PATH.read_text())
    entry = cache["entries"]["pytest_smoke_prewarm"]
    assert entry["fingerprint"] == submission_lib.hash_file(baselines_dir / "pytest_smoke_prewarm.py")
    assert entry["scores"]["3"] == {"total": 201, "max": 4}  # JW at 3x3, from the baselines.jw re-export
