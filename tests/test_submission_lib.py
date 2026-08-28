"""Tests for scripts/submission_lib.py -- the validation logic shared by
scripts/submit_baseline.py and scripts/process_inbox.py. Pure functions,
no verify()/evaluate() calls, so these stay in the sub-second range.
"""

import pytest

from scripts.submission_lib import (
    SubmissionRejected,
    validate_encode_source,
    validate_manifest,
    validate_sizes,
)


def _manifest(**overrides):
    base = {"name": "alice_bk", "label": "Alice's BK", "sizes": "3-5"}
    base.update(overrides)
    return base


# --- validate_manifest ---


def test_valid_manifest_passes():
    result = validate_manifest(_manifest())
    assert result["sizes"] == [3, 4, 5]


def test_valid_manifest_with_generated_by():
    result = validate_manifest(_manifest(generated_by="Claude Opus 4.5"))
    assert result["generated_by"] == "Claude Opus 4.5"


def test_generated_by_is_optional():
    result = validate_manifest(_manifest())
    assert result.get("generated_by") is None


@pytest.mark.parametrize("missing", ["name", "label", "sizes"])
def test_missing_required_key_rejected(missing):
    manifest = _manifest()
    del manifest[missing]
    with pytest.raises(SubmissionRejected, match=missing):
        validate_manifest(manifest)


@pytest.mark.parametrize("bad_name", ["Alice_BK", "1bk", "bk-variant", "", "bk variant"])
def test_bad_name_pattern_rejected(bad_name):
    with pytest.raises(SubmissionRejected):
        validate_manifest(_manifest(name=bad_name))


def test_empty_label_rejected():
    with pytest.raises(SubmissionRejected):
        validate_manifest(_manifest(label="   "))


def test_sizes_out_of_bounds_rejected():
    with pytest.raises(SubmissionRejected):
        validate_manifest(_manifest(sizes="1-20"))


def test_non_string_generated_by_rejected():
    with pytest.raises(SubmissionRejected):
        validate_manifest(_manifest(generated_by=123))


def test_non_dict_manifest_rejected():
    with pytest.raises(SubmissionRejected):
        validate_manifest(["not", "a", "dict"])


# --- validate_sizes ---


def test_validate_sizes_range():
    assert validate_sizes("3-5") == [3, 4, 5]


def test_validate_sizes_rejects_out_of_range():
    with pytest.raises(SubmissionRejected):
        validate_sizes("2-4")


# --- validate_encode_source ---


def test_clean_file_passes():
    validate_encode_source("def encode(spec):\n    return {}\n")


def test_clean_file_with_order_passes():
    validate_encode_source(
        "def order(Lx, Ly):\n    return list(range(Lx * Ly))\n\n"
        "def encode(spec):\n    return {}\n"
    )


def test_missing_encode_rejected():
    with pytest.raises(SubmissionRejected, match="encode"):
        validate_encode_source("def not_encode(spec):\n    return {}\n")


def test_duplicate_encode_rejected():
    source = (
        "def encode(spec):\n    return {'old': True}\n\n"
        "def encode(spec):\n    return {'new': True}\n"
    )
    with pytest.raises(SubmissionRejected, match="more than once"):
        validate_encode_source(source)


def test_duplicate_order_rejected():
    source = (
        "def order(Lx, Ly):\n    return list(range(Lx * Ly))\n\n"
        "def order(Lx, Ly):\n    return list(range(Lx * Ly))[::-1]\n\n"
        "def encode(spec):\n    return {}\n"
    )
    with pytest.raises(SubmissionRejected, match="more than once"):
        validate_encode_source(source)


def test_duplicate_helper_function_rejected():
    # The concrete scenario this guard exists for: a leftover helper from
    # an earlier submission pasted in alongside the new encode().
    source = (
        "def _helper():\n    return 1\n\n"
        "def _helper():\n    return 2\n\n"
        "def encode(spec):\n    return {}\n"
    )
    with pytest.raises(SubmissionRejected, match="more than once"):
        validate_encode_source(source)


def test_syntax_error_rejected():
    with pytest.raises(SubmissionRejected, match="syntax error"):
        validate_encode_source("def encode(spec:\n    return {}\n")
