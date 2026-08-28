"""Tests for baselines/__init__.py's registry loading."""

import json

import baselines
from baselines import BASELINES


def test_every_entry_has_the_full_shape():
    for entry in BASELINES.values():
        assert callable(entry["encode"])
        assert entry["order"] is None or callable(entry["order"])
        assert isinstance(entry["sizes"], list) and entry["sizes"]
        assert entry["module"].startswith("baselines.")
        assert isinstance(entry["label"], str) and entry["label"]
        assert entry["submitted_at"] is None or isinstance(entry["submitted_at"], str)
        assert entry["generated_by"] is None or isinstance(entry["generated_by"], str)


def test_submission_metadata_defaults_to_none_when_absent(monkeypatch, tmp_path):
    # A registry.json entry from before submitted_at/generated_by existed
    # (or one that just never set generated_by) has neither key at all --
    # confirms _load_registry()'s .get() default is what's actually
    # exercised, not a KeyError. Uses a synthetic registry, not the real
    # (ever-growing) one, since which real entries lack this metadata
    # changes over time as new submissions come in.
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"jw": {"module": "baselines.jw", "sizes": [3], "label": "JW"}}))
    monkeypatch.setattr(baselines, "_REGISTRY_PATH", registry_path)

    entry = baselines._load_registry()["jw"]
    assert entry["submitted_at"] is None
    assert entry["generated_by"] is None


def test_submission_metadata_carried_through_when_present(monkeypatch, tmp_path):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"jw": {
        "module": "baselines.jw", "sizes": [3], "label": "JW",
        "submitted_at": "2026-08-28T16:15:55+00:00", "generated_by": "Claude Sonnet 5",
    }}))
    monkeypatch.setattr(baselines, "_REGISTRY_PATH", registry_path)

    entry = baselines._load_registry()["jw"]
    assert entry["submitted_at"] == "2026-08-28T16:15:55+00:00"
    assert entry["generated_by"] == "Claude Sonnet 5"
