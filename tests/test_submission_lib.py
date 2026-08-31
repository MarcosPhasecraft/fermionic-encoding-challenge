"""Tests for scripts/submission_lib.py -- the validation logic shared by
scripts/submit_baseline.py and scripts/process_inbox.py, and the
leaderboard score-cache primitives shared by scripts/process_inbox.py and
scripts/update_leaderboard.py. Pure functions, no verify()/evaluate()
calls, so these stay in the sub-second range.
"""

import pytest

import scripts.submission_lib as submission_lib
from scripts.submission_lib import (
    SubmissionRejected,
    parse_shapes,
    validate_encode_source,
    validate_manifest,
    validate_mixed_sizes,
    validate_shapes,
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


def test_manifest_graph_defaults_to_square():
    result = validate_manifest(_manifest())
    assert result["graph"] == "square"


def test_manifest_graph_accepts_a_known_graph_type():
    result = validate_manifest(_manifest(graph="hexagonal", sizes="8x4"))
    assert result["graph"] == "hexagonal"


def test_manifest_graph_rejects_an_unknown_value():
    with pytest.raises(SubmissionRejected, match="graph"):
        validate_manifest(_manifest(graph="kagome"))


def test_manifest_graph_type_parses_sizes_as_shape_pairs():
    result = validate_manifest(_manifest(graph="hexagonal", sizes="8x4,15x15,3x3"))
    assert result["sizes"] == [(8, 4), (15, 15), (3, 3)]


def test_manifest_graph_type_rejects_square_lattice_sizes_syntax():
    # A graph-type submission must use "LxxLy" pairs, not the square
    # challenge's plain-int/range grammar -- "3-5" has no "x" in any part.
    with pytest.raises(SubmissionRejected):
        validate_manifest(_manifest(graph="hexagonal", sizes="3-5"))


def test_manifest_square_also_accepts_a_rectangle_shape():
    # The square-lattice challenge's sizes grammar also accepts explicit
    # LxxLy pairs now (a submission can claim an off-square rectangle,
    # computed/stored, shown only if is_showcased -- see
    # scripts/update_leaderboard.py).
    result = validate_manifest(_manifest(sizes="8x12"))
    assert result["sizes"] == [(8, 12)]


def test_manifest_square_accepts_a_mix_of_plain_sizes_and_shapes():
    result = validate_manifest(_manifest(sizes="3-5,8x12"))
    assert result["sizes"] == [3, 4, 5, (8, 12)]


# --- validate_sizes ---


def test_validate_sizes_range():
    assert validate_sizes("3-5") == [3, 4, 5]


def test_validate_sizes_rejects_out_of_range():
    with pytest.raises(SubmissionRejected):
        validate_sizes("2-4")


# --- validate_mixed_sizes ---


def test_validate_mixed_sizes_plain_only_matches_validate_sizes():
    # Backward compatibility, made explicit: an all-integer input parses
    # identically whichever validator is used -- existing manifests (and
    # registry.json's 17 existing plain-int entries) are unaffected.
    assert validate_mixed_sizes("3-15") == validate_sizes("3-15")


def test_validate_mixed_sizes_shape_only():
    assert validate_mixed_sizes("8x12") == [(8, 12)]


def test_validate_mixed_sizes_mix():
    assert validate_mixed_sizes("3-5,8x12,10") == [3, 4, 5, 10, (8, 12)]


def test_validate_mixed_sizes_rejects_out_of_range_plain_part():
    with pytest.raises(SubmissionRejected):
        validate_mixed_sizes("1-20")


def test_validate_mixed_sizes_rejects_out_of_range_shape_part():
    with pytest.raises(SubmissionRejected):
        validate_mixed_sizes("8x20")


def test_validate_mixed_sizes_rejects_empty():
    with pytest.raises(SubmissionRejected):
        validate_mixed_sizes("")


# --- parse_shapes / validate_shapes ---


def test_parse_shapes_basic():
    assert parse_shapes("8x4,15x15,3x3") == [(8, 4), (15, 15), (3, 3)]


def test_parse_shapes_rejects_missing_x():
    with pytest.raises(SubmissionRejected):
        parse_shapes("8,4")


def test_parse_shapes_rejects_non_integer_dimension():
    with pytest.raises(SubmissionRejected):
        parse_shapes("8xN")


def test_validate_shapes_rejects_empty():
    with pytest.raises(SubmissionRejected):
        validate_shapes("")


def test_validate_shapes_rejects_out_of_range_dimension():
    with pytest.raises(SubmissionRejected):
        validate_shapes("8x20")


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


# --- hash_file ---


def test_hash_file_same_content_same_hash(tmp_path):
    f1, f2 = tmp_path / "a.py", tmp_path / "b.py"
    f1.write_text("x = 1\n")
    f2.write_text("x = 1\n")
    assert submission_lib.hash_file(f1) == submission_lib.hash_file(f2)


def test_hash_file_different_content_different_hash(tmp_path):
    f1, f2 = tmp_path / "a.py", tmp_path / "b.py"
    f1.write_text("x = 1\n")
    f2.write_text("x = 2\n")
    assert submission_lib.hash_file(f1) != submission_lib.hash_file(f2)


# --- harness_fingerprint ---


def test_harness_fingerprint_is_deterministic():
    assert submission_lib.harness_fingerprint() == submission_lib.harness_fingerprint()


def test_harness_fingerprint_changes_when_a_harness_file_changes(tmp_path, monkeypatch):
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir()
    (harness_dir / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(submission_lib, "REPO_ROOT", tmp_path)

    fp1 = submission_lib.harness_fingerprint()
    (harness_dir / "a.py").write_text("x = 2\n")
    fp2 = submission_lib.harness_fingerprint()

    assert fp1 != fp2


# --- load_score_cache / save_score_cache ---


def test_load_score_cache_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(submission_lib, "CACHE_PATH", tmp_path / "nope.json")
    assert submission_lib.load_score_cache() == {}


def test_load_score_cache_corrupt_json_returns_empty_dict(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text("not json{{{")
    monkeypatch.setattr(submission_lib, "CACHE_PATH", path)
    assert submission_lib.load_score_cache() == {}


def test_save_and_load_score_cache_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    monkeypatch.setattr(submission_lib, "CACHE_PATH", path)
    data = {"_harness_fingerprint": "abc", "entries": {"jw": {"fingerprint": "x", "scores": {}}}}
    submission_lib.save_score_cache(data)
    assert submission_lib.load_score_cache() == data


# --- registry_entry ---


def test_registry_entry_omits_graph_for_square():
    entry = submission_lib.registry_entry("alice", [3, 4], "Alice", graph="square")
    assert "graph" not in entry


def test_registry_entry_omits_graph_when_not_given():
    entry = submission_lib.registry_entry("alice", [3, 4], "Alice")
    assert "graph" not in entry


def test_registry_entry_includes_graph_for_a_named_graph_type():
    entry = submission_lib.registry_entry("alice", [3, 4], "Alice", graph="hexagonal")
    assert entry["graph"] == "hexagonal"


# --- check_at_size: spec_builder/model parametrization ---


def test_check_at_size_defaults_match_square_lattice_challenge():
    from baselines.jw import encode as jw_encode

    # Square lattice, model="full" -- today's exact existing behavior,
    # unchanged by adding the new (defaulted) parameters.
    total, max_weight = submission_lib.check_at_size(jw_encode, None, 3)
    assert (total, max_weight) == (201, 4)  # arXiv 2504.21636's own published JW row at 3x3


def test_check_at_size_uses_a_custom_spec_builder_and_model():
    from baselines.jw import encode as jw_encode
    from harness.graphs import build_spec as build_graph_spec

    def hex_spec_builder(Lx, Ly, order_fn):
        return build_graph_spec("hexagonal", Lx, Ly, order_fn)

    total, max_weight = submission_lib.check_at_size(
        jw_encode, None, 3, spec_builder=hex_spec_builder, model="hopping",
    )
    # Sanity: hopping-only weight on an 18-mode hex lattice, not the
    # square-lattice 3x3 numbers above -- proves the parameters actually
    # changed which spec/model got scored, not just accepted syntactically.
    assert total > 0 and max_weight > 0
    assert (total, max_weight) != (201, 4)


def test_check_at_size_accepts_independent_lx_ly():
    from baselines.jw import encode as jw_encode
    from harness.graphs import hex_lattice

    calls = []

    def recording_spec_builder(Lx, Ly, order_fn):
        calls.append((Lx, Ly))
        return hex_lattice(Lx, Ly)

    # 8x2 and 2x8 both give M=32 (mode count alone doesn't pin the shape),
    # but must be threaded through as the exact (lx, ly) pair passed in --
    # proves lx/ly aren't collapsed to a single l the way the old
    # single-argument call forced lx == ly.
    submission_lib.check_at_size(jw_encode, None, 8, 2, spec_builder=recording_spec_builder, model="hopping")
    assert calls == [(8, 2)]
