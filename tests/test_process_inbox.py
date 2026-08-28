"""Light end-to-end test for scripts/process_inbox.py -- runs the real
pipeline logic (real verify(), real registry read/write) against a fully
isolated temp inbox/registry/baselines directory via monkeypatching, so it
never touches this repo's actual inbox/, baselines/, or registry.json.
Feeds "none" to the git prompt so no git command ever runs, and passes
--skip-tests --skip-leaderboard so it doesn't spawn a nested pytest run or
an expensive leaderboard regen.
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
