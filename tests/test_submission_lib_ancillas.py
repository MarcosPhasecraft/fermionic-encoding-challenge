"""Tests for scripts/submission_lib.py's ancilla-challenge additions --
validate_ancilla_manifest, check_ancilla_at_size, harness_v2_fingerprint,
ancilla_registry_entry. Mirrors tests/test_submission_lib.py's existing
style for the ancilla-free equivalents.
"""

import pytest

from scripts.submission_lib import (
    ANCILLA_MAX_WEIGHT,
    SubmissionRejected,
    ancilla_registry_entry,
    check_ancilla_at_size,
    harness_v2_fingerprint,
    validate_ancilla_manifest,
)


def _jw_plus_spectator(spec):
    from baselines.jw import encode as jw_encode
    mapping = jw_encode(spec)
    m = mapping["n_qubits"]
    return {
        "n_qubits": m + 1,
        "majoranas": [s + "I" for s in mapping["majoranas"]],
        "stabilizers": ["I" * m + "Z"],
    }


# ---- validate_ancilla_manifest ---------------------------------------------

def test_validate_ancilla_manifest_accepts_a_well_formed_square_submission():
    manifest = validate_ancilla_manifest({"name": "alice_dk", "label": "Alice's DK", "sizes": "3-9"})
    assert manifest["graph"] == "square"
    assert manifest["sizes"] == list(range(3, 10))


def test_validate_ancilla_manifest_accepts_hexagonal_with_explicit_shapes():
    manifest = validate_ancilla_manifest({"name": "alice_hex", "label": "x", "sizes": "3x3,4x4", "graph": "hexagonal"})
    assert manifest["sizes"] == [(3, 3), (4, 4)]


def test_validate_ancilla_manifest_rejects_triangular():
    # Only square/hexagonal are in scope for the ancilla challenge -- unlike
    # the ancilla-free graph challenge, which also allows triangular/periodic.
    with pytest.raises(SubmissionRejected, match="square.*hexagonal|hexagonal.*square"):
        validate_ancilla_manifest({"name": "x", "label": "x", "sizes": "3x3", "graph": "triangular"})


def test_validate_ancilla_manifest_rejects_missing_name():
    with pytest.raises(SubmissionRejected):
        validate_ancilla_manifest({"label": "x", "sizes": "3-9"})


def test_validate_ancilla_manifest_rejects_bad_name_pattern():
    with pytest.raises(SubmissionRejected):
        validate_ancilla_manifest({"name": "Alice-DK", "label": "x", "sizes": "3-9"})


def test_validate_ancilla_manifest_square_sizes_reject_hexagonal_shape_grammar_gap():
    # Square sizes below MIN_SIZE (3) are rejected, same bound as the
    # ancilla-free challenge.
    with pytest.raises(SubmissionRejected):
        validate_ancilla_manifest({"name": "x", "label": "x", "sizes": "1-2"})


# ---- check_ancilla_at_size ---------------------------------------------------

def test_check_ancilla_at_size_reports_ancilla_count_for_a_verifiably_valid_encoding():
    # JW plus one spectator ancilla is a genuinely valid encoding (passes
    # verify_extended) even though it exceeds the weight cap -- exercised
    # here via score_extended directly (bypassing the cap) just to confirm
    # n_ancillas/total_weight come back sensibly; the cap itself is
    # covered by the next test.
    from harness.v2.evaluate import evaluate_extended
    from harness.v2.hamiltonian_terms import hamiltonian_terms
    from harness.lattice import build_spec

    spec = build_spec(3, 3, None)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, _jw_plus_spectator, terms, None)
    assert result["passed"]
    assert result["n_ancillas"] == 1
    assert result["total_weight"] > 0


def test_check_ancilla_at_size_rejects_max_weight_over_the_cap():
    # JW's own raw max_weight at 3x3 is 4 (see README.md's own example) --
    # exceeds ANCILLA_MAX_WEIGHT (3), even though verification itself passes.
    with pytest.raises(SubmissionRejected, match="exceeds"):
        check_ancilla_at_size(_jw_plus_spectator, None, None, 3)


def test_check_ancilla_at_size_dk_passes_within_the_weight_cap():
    from harness.v2.baselines.dk import encode, represent
    n_ancillas, max_weight, total_weight = check_ancilla_at_size(encode, represent, None, 3)
    assert max_weight <= ANCILLA_MAX_WEIGHT
    assert n_ancillas == 2


def test_check_ancilla_at_size_rejects_broken_verification():
    def broken(spec):
        m = spec["M"]
        return {"n_qubits": m, "majoranas": ["X" * m] * (2 * m), "stabilizers": []}

    with pytest.raises(SubmissionRejected):
        check_ancilla_at_size(broken, None, None, 3)


def test_check_ancilla_at_size_threads_graph_through_to_the_right_spec_builder():
    # DK's square construction, fed a hexagonal spec (wrong "coords" shape,
    # no "Lx"/"Ly" keys) via graph="hexagonal", must fail rather than being
    # silently scored against the wrong geometry -- confirms graph= is
    # actually threaded through to harness.graphs.build_spec, not ignored.
    from harness.v2.baselines.dk import encode, represent
    with pytest.raises(SubmissionRejected):
        check_ancilla_at_size(encode, represent, None, 3, graph="hexagonal")


# ---- ancilla_registry_entry ---------------------------------------------------

def test_ancilla_registry_entry_shape():
    entry = ancilla_registry_entry("dk", [3, 5, 7], "Derby-Klassen", "square", True, submitted_at="2026-01-01T00:00:00+00:00")
    assert entry == {
        "module": "harness.v2.baselines.dk", "sizes": [3, 5, 7], "label": "Derby-Klassen",
        "graph": "square", "has_represent": True, "submitted_at": "2026-01-01T00:00:00+00:00",
    }


def test_ancilla_registry_entry_omits_optional_fields_when_absent():
    entry = ancilla_registry_entry("x", [3], "X", "hexagonal", False)
    assert "submitted_at" not in entry
    assert "generated_by" not in entry


# ---- harness_v2_fingerprint ---------------------------------------------------

def test_harness_v2_fingerprint_is_deterministic():
    assert harness_v2_fingerprint() == harness_v2_fingerprint()


def test_harness_v2_fingerprint_unaffected_by_baselines_subdir(tmp_path, monkeypatch):
    # harness/v2/baselines/*.py must be invisible to this (individually
    # hashed like baselines/*.py are for the ancilla-free cache) -- adding
    # a new file there should not change the fingerprint.
    import harness.v2 as v2_pkg
    from pathlib import Path

    before = harness_v2_fingerprint()
    scratch = Path(v2_pkg.__file__).parent / "baselines" / "_scratch_test_file.py"
    scratch.write_text("# scratch\n")
    try:
        after = harness_v2_fingerprint()
    finally:
        scratch.unlink()
    assert before == after
