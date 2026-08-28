"""Tests for baselines/__init__.py's registry loading."""

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


def test_existing_entries_predate_submission_metadata():
    # None of the baselines registered before scripts/process_inbox.py
    # existed have submitted_at/generated_by in registry.json -- confirms
    # the .get() default (not a KeyError) is what's actually exercised for
    # registry.json entries missing these keys.
    for entry in BASELINES.values():
        assert entry["submitted_at"] is None
        assert entry["generated_by"] is None
