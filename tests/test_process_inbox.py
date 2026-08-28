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


def _write_submission(inbox_dir, folder_name, name, label, sizes="3", encode_source=None):
    folder = inbox_dir / folder_name
    folder.mkdir(parents=True)
    (folder / "encode.py").write_text(encode_source or "from baselines.jw import encode\n")
    (folder / "submission.json").write_text(json.dumps({"name": name, "label": label, "sizes": sizes}))
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
