"""Tests for harness.v2.score.score_extended / harness.v2.evaluate.evaluate_extended
-- certified stabilizer-dressed scoring and per-category maxima.

The dressing fixtures reuse test_v2_verify.py's hand-checkable M=1 setup:

    gamma0 = "XI", gammabar0 = "ZI"     (M=1, 1 ancilla qubit)
    num term (0, 1): raw product = XOR(XI, ZI) = "YI", weight 1
    stabilizer S_ok = "IZ"

    "YI" XOR "IZ" (symplectic) = "YZ" -- a valid, CERTIFIABLE representative
    of the same term (raw*S_ok), even though its weight (2) is higher than
    the raw product's (1). The point of this fixture isn't to demonstrate a
    weight *improvement* (Derby-Klassen-style dressing chooses S to lower
    weight, not raise it) -- it's to confirm the certification logic accepts
    any genuine raw*S representative and, critically, that the reported
    weight is computed from the dressed representative, not silently from
    the raw product.
"""

import pytest

from baselines.jw import encode as jw_encode
from harness.lattice import rectangle
from harness.v2.evaluate import evaluate_extended
from harness.v2.hamiltonian_terms import HamiltonianTerm, hamiltonian_terms
from harness.v2.score import RepresentativeRejected, score_extended

_SPEC_M1 = {"M": 1}
_NUM_TERM = [HamiltonianTerm((0, 1), "num", ("mode", 0))]


def _ancilla_mapping(stabilizers=("IZ",)):
    return {"n_qubits": 2, "majoranas": ["XI", "ZI"], "stabilizers": list(stabilizers)}


def _ancilla_free_mapping():
    return {"n_qubits": 1, "majoranas": ["X", "Z"], "stabilizers": []}


def test_no_represent_hook_scores_the_raw_product():
    result = score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=None)
    assert result["total_weight"] == 1
    assert result["max_num_weight"] == 1
    assert result["max_rehop_weight"] is None  # no hopping terms scored here
    assert result["n_ancillas"] == 1
    assert result["n_stabilizers"] == 1


def test_representative_identical_to_raw_is_accepted():
    result = score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: raw)
    assert result["total_weight"] == 1


def test_representative_equal_to_raw_times_stabilizer_is_accepted_and_scored_from_the_representative():
    # "YZ" = raw ("YI") * S_ok ("IZ") -- see module docstring for the
    # hand-checked symplectic arithmetic.
    result = score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: "YZ")
    assert result["total_weight"] == 2  # not 1 -- confirms scoring uses the representative, not the raw product
    assert result["max_num_weight"] == 2


def test_representative_not_differing_by_a_stabilizer_is_rejected():
    with pytest.raises(RepresentativeRejected):
        score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: "II")


def test_ancilla_free_mapping_cannot_change_the_representative():
    # Trivial stabilizer group ({0} only) -- only the raw product itself is certifiable.
    with pytest.raises(RepresentativeRejected):
        score_extended(_SPEC_M1, _ancilla_free_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: "X")


def test_ancilla_free_mapping_accepts_the_raw_product_as_its_own_representative():
    result = score_extended(_SPEC_M1, _ancilla_free_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: raw)
    assert result["total_weight"] == 1


def test_represent_hook_receives_the_correct_raw_pauli_and_term():
    seen = {}

    def represent(term, raw_pauli, spec, mapping):
        seen["term"] = term
        seen["raw_pauli"] = raw_pauli
        return raw_pauli

    score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=represent)
    assert seen["raw_pauli"] == "YI"
    assert seen["term"] is _NUM_TERM[0]


def test_malformed_representative_length_is_rejected():
    with pytest.raises(RepresentativeRejected):
        score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: "Y")


def test_non_string_representative_is_rejected():
    with pytest.raises(RepresentativeRejected):
        score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=lambda t, raw, s, m: None)


def test_crashing_represent_hook_is_rejected_not_propagated():
    def represent(term, raw_pauli, spec, mapping):
        raise ValueError("boom")

    with pytest.raises(RepresentativeRejected):
        score_extended(_SPEC_M1, _ancilla_mapping(), _NUM_TERM, represent_fn=represent)


def test_evaluate_extended_matches_legacy_score_for_an_ancilla_free_real_baseline():
    # JW on a tiny chain has no ancillas/stabilizers -- score_extended with
    # no represent() hook must reproduce the same total/max weight as the
    # legacy scorer.
    from harness.score import score_majorana

    spec = rectangle(4, 1)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, jw_encode, terms, represent_fn=None)
    assert result["passed"]

    legacy_terms = [t.majoranas for t in terms]
    mapping = jw_encode(spec)
    legacy = score_majorana(spec, mapping, legacy_terms)
    assert result["total_weight"] == legacy["total_weight"]
    assert result["max_weight"] == legacy["max_weight"]


def test_evaluate_extended_reports_encode_crash_as_a_failed_result_not_an_exception():
    def crashing_encode(spec):
        raise RuntimeError("nope")

    result = evaluate_extended(_SPEC_M1, crashing_encode, _NUM_TERM)
    assert result["passed"] is False
    assert "error" in result


def test_evaluate_extended_reports_representative_rejection_as_a_failed_result():
    def encode(spec):
        return _ancilla_mapping()

    result = evaluate_extended(_SPEC_M1, encode, _NUM_TERM, represent_fn=lambda t, raw, s, m: "II")
    assert result["passed"] is False
    assert "error" in result


def test_evaluate_extended_propagates_verification_failure():
    def encode(spec):
        return {"n_qubits": 2, "majoranas": ["XI", "XI"], "stabilizers": []}  # commuting, not anticommuting

    result = evaluate_extended(_SPEC_M1, encode, _NUM_TERM)
    assert result["passed"] is False
    assert "majorana_algebra" in result["checks"]
