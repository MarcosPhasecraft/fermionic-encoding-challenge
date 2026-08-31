"""Light end-to-end test for scripts/process_inbox.py's ancilla-challenge
dispatch ("challenge": "ancillas" in submission.json) -- same isolation
approach as tests/test_process_inbox.py (real pipeline logic, fully
isolated temp inbox/registry/baselines-dir via monkeypatching), extended
to also isolate harness/v2/baselines/registry.json and
.leaderboard_cache_ancillas.json so this never touches the real repo state.

Submitted sizes must be >= MIN_SIZE (3), so M = Lx*Ly is at least 9 here --
no hand-built tiny M=1 fixture like harness/v2's own unit tests use.
Instead these reuse the real, already-verified harness.v2.baselines.dk
module for the "should be accepted" cases, and a "JW plus one spectator
ancilla qubit" wrapper (generic in M, same trick as test_v2_challenges.py's
own _jw_plus_spectator) for cases that need to be valid but exceed the
weight cap.
"""

import json

import scripts.process_inbox as process_inbox
import scripts.submission_lib as submission_lib

_DK_SOURCE = "from harness.v2.baselines.dk import encode, represent\n"

# Valid stabilizer structure (1 ancilla, rank 1) but no represent() hook --
# JW's own raw weight (>3 at any real size) is what gets scored, reliably
# failing the ancilla challenge's fixed max_weight <= 3 cap.
_JW_PLUS_SPECTATOR_SOURCE = """
from baselines.jw import encode as jw_encode

def encode(spec):
    mapping = jw_encode(spec)
    m = mapping["n_qubits"]
    return {
        "n_qubits": m + 1,
        "majoranas": [s + "I" for s in mapping["majoranas"]],
        "stabilizers": ["I" * m + "Z"],
    }
"""

# 2 ancillas (n_qubits = M + 2) but only 1 independent stabilizer -- fails
# the codespace_dimension check (len(stabilizers) == rank == n_ancillas).
_TOO_FEW_STABILIZERS_SOURCE = """
from baselines.jw import encode as jw_encode

def encode(spec):
    mapping = jw_encode(spec)
    m = mapping["n_qubits"]
    return {
        "n_qubits": m + 2,
        "majoranas": [s + "II" for s in mapping["majoranas"]],
        "stabilizers": ["I" * m + "ZI"],
    }
"""


def _write_ancilla_submission(inbox_dir, folder_name, name, label, sizes="3", encode_source=None, graph=None, memory_files=None):
    folder = inbox_dir / folder_name
    folder.mkdir(parents=True)
    (folder / "encode.py").write_text(encode_source or _DK_SOURCE)
    manifest = {"name": name, "label": label, "sizes": sizes, "challenge": "ancillas"}
    if graph is not None:
        manifest["graph"] = graph
    (folder / "submission.json").write_text(json.dumps(manifest))
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
    monkeypatch.setattr(submission_lib, "CACHE_PATH", tmp_path / "leaderboard_cache.json")

    ancilla_baselines_dir = tmp_path / "harness_v2_baselines"
    ancilla_baselines_dir.mkdir()
    ancilla_registry_path = ancilla_baselines_dir / "registry.json"
    ancilla_registry_path.write_text("{}\n")
    monkeypatch.setattr(submission_lib, "ANCILLA_BASELINES_DIR", ancilla_baselines_dir)
    monkeypatch.setattr(submission_lib, "ANCILLA_REGISTRY_PATH", ancilla_registry_path)
    monkeypatch.setattr(submission_lib, "ANCILLA_CACHE_PATH", tmp_path / "leaderboard_cache_ancillas.json")

    inbox_dir = tmp_path / "inbox"
    monkeypatch.setattr(process_inbox, "INBOX", inbox_dir)
    monkeypatch.setattr(process_inbox, "PROCESSED", inbox_dir / "_processed")

    monkeypatch.setattr("builtins.input", lambda _: "none")
    monkeypatch.setattr("sys.argv", ["process_inbox.py", "--skip-tests", "--skip-leaderboard"])
    return ancilla_baselines_dir, ancilla_registry_path, inbox_dir


def test_valid_ancilla_submission_is_accepted_and_registered(tmp_path, monkeypatch):
    ancilla_baselines_dir, ancilla_registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_ancilla_submission(inbox_dir, "alice", "alice_ancilla", "Alice's Ancilla Encoding")

    process_inbox.main()

    registry = json.loads(ancilla_registry_path.read_text())
    assert "alice_ancilla" in registry
    assert registry["alice_ancilla"]["label"] == "Alice's Ancilla Encoding"
    assert registry["alice_ancilla"]["graph"] == "square"
    assert registry["alice_ancilla"]["has_represent"] is True
    assert (ancilla_baselines_dir / "alice_ancilla.py").is_file()
    assert not (inbox_dir / "alice").exists()  # moved into _processed


def test_ancilla_submission_never_touches_the_ancilla_free_registry(tmp_path, monkeypatch):
    _, ancilla_registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_ancilla_submission(inbox_dir, "alice", "alice_ancilla", "Alice's Ancilla Encoding")

    process_inbox.main()

    weight_registry = json.loads(submission_lib.REGISTRY_PATH.read_text())
    assert weight_registry == {}  # untouched -- this went through the ancilla pipeline only


def test_exceeding_max_weight_is_rejected(tmp_path, monkeypatch):
    _, ancilla_registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_ancilla_submission(inbox_dir, "bob", "bob_bad", "Bob's Bad Encoding", encode_source=_JW_PLUS_SPECTATOR_SOURCE)

    process_inbox.main()

    registry = json.loads(ancilla_registry_path.read_text())
    assert "bob_bad" not in registry
    assert (inbox_dir / "bob").exists()  # left in place, not archived


def test_invalid_stabilizer_dimension_is_rejected(tmp_path, monkeypatch):
    _, ancilla_registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_ancilla_submission(inbox_dir, "carol", "carol_bad", "Carol's Bad Encoding", encode_source=_TOO_FEW_STABILIZERS_SOURCE)

    process_inbox.main()

    registry = json.loads(ancilla_registry_path.read_text())
    assert "carol_bad" not in registry


def test_duplicate_name_across_pipelines_is_allowed(tmp_path, monkeypatch):
    # The two registries are independent -- a name already used in the
    # ancilla-free registry doesn't block the same name in the ancilla one
    # (and vice versa), since they're disjoint namespaces/files.
    _, ancilla_registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    submission_lib.REGISTRY_PATH.write_text(json.dumps({"shared_name": {"module": "baselines.shared_name", "sizes": [3], "label": "x"}}))
    _write_ancilla_submission(inbox_dir, "dave", "shared_name", "Dave's Ancilla Encoding")

    process_inbox.main()

    registry = json.loads(ancilla_registry_path.read_text())
    assert "shared_name" in registry


def test_ancilla_and_ancilla_free_submissions_in_the_same_run(tmp_path, monkeypatch):
    _, ancilla_registry_path, inbox_dir = _isolate(tmp_path, monkeypatch)
    _write_ancilla_submission(inbox_dir, "alice", "alice_ancilla", "Alice's Ancilla Encoding")
    weight_folder = inbox_dir / "erin"
    weight_folder.mkdir(parents=True)
    (weight_folder / "encode.py").write_text("from baselines.jw import encode\n")
    (weight_folder / "submission.json").write_text(json.dumps({"name": "erin_jw", "label": "Erin's JW", "sizes": "3"}))

    process_inbox.main()

    ancilla_registry = json.loads(ancilla_registry_path.read_text())
    weight_registry = json.loads(submission_lib.REGISTRY_PATH.read_text())
    assert "alice_ancilla" in ancilla_registry
    assert "erin_jw" in weight_registry


def test_missing_challenge_key_defaults_to_the_ancilla_free_pipeline(tmp_path, monkeypatch):
    # No "challenge" key at all -- must dispatch to the ordinary pipeline,
    # not silently be treated as an ancilla submission.
    _isolate(tmp_path, monkeypatch)
    inbox_dir = process_inbox.INBOX
    folder = inbox_dir / "frank"
    folder.mkdir(parents=True)
    (folder / "encode.py").write_text("from baselines.jw import encode\n")
    (folder / "submission.json").write_text(json.dumps({"name": "frank_jw", "label": "Frank's JW", "sizes": "3"}))

    process_inbox.main()

    weight_registry = json.loads(submission_lib.REGISTRY_PATH.read_text())
    assert "frank_jw" in weight_registry
