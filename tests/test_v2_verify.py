"""Tests for harness.v2.verify.verify_extended -- the stabilizer checks
(2-4) layered on top of harness.verify.verify's checks 0-1.

Fixtures are hand-built at M=1 (2 Majoranas: gamma0, gammabar0) rather than
using a real baseline encoding, so every commutation relation below can be
checked by hand:

    gamma0    = "XI"   gammabar0 = "ZI"     (qubit 0: X,Z anticommute --
                                              check 1 requires this)
    valid stabilizer   S_ok   = "IZ"   (Z on the ancilla qubit only --
                                         I on qubit 0 means it commutes
                                         with both gamma0 and gammabar0,
                                         satisfying this module's strong
                                         check-3 condition)
    constant-signature   S_Y = "YI"   (Y anticommutes with BOTH X and Z on
                                        the same qubit, so S_Y anticommutes
                                        with gamma0 AND gammabar0 -- a
                                        constant signature of 1. This passes
                                        PLAN.md Sec 1.5's weaker condition
                                        but must be REJECTED here, since
                                        this module requires commuting with
                                        every individual Majorana -- see
                                        harness/v2/verify.py's docstring.)
"""

import numpy as np

from harness.v2.verify import verify_extended

_M1_MAJORANAS = ["XI", "ZI"]  # gamma0, gammabar0; anticommute on qubit 0
_SPEC_M1 = {"M": 1}


def _mapping(n_qubits, stabilizers, majoranas=None):
    return {
        "n_qubits": n_qubits,
        "majoranas": majoranas or _M1_MAJORANAS,
        "stabilizers": stabilizers,
    }


def test_ancilla_free_mapping_passes_vacuously():
    mapping = _mapping(1, [], majoranas=["X", "Z"])
    result = verify_extended(_SPEC_M1, mapping)
    assert result["passed"]
    assert result["checks"]["codespace_dimension"]["n_ancillas"] == 0


def test_valid_ancilla_and_stabilizer_passes():
    mapping = _mapping(2, ["IZ"])
    result = verify_extended(_SPEC_M1, mapping)
    assert result["passed"], result["checks"]
    dim = result["checks"]["codespace_dimension"]
    assert dim == {"passed": True, "n_stabilizers": 1, "rank": 1, "n_ancillas": 1}


def test_constant_but_nonzero_signature_is_rejected_by_the_strong_condition():
    # S_Y="YI" has a CONSTANT commutation signature (anticommutes with both
    # gamma0 and gammabar0) -- PLAN.md's own weaker condition would accept
    # this; this module's stricter one must not.
    mapping = _mapping(2, ["YI"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert result["checks"]["stabilizers_compatible"]["passed"] is False


def test_stabilizer_anticommuting_with_only_some_majoranas_is_rejected():
    # "XI" anticommutes with gammabar0="ZI" but commutes with gamma0="XI" --
    # not even a constant signature, so both the weak and strong conditions
    # reject it.
    mapping = _mapping(2, ["XI"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert result["checks"]["stabilizers_compatible"]["passed"] is False


def test_anticommuting_stabilizer_pair_rejected_by_abelian_check():
    # "IX" and "IZ" both commute with gamma0/gammabar0 individually (check 3
    # would pass for each alone), but anticommute with EACH OTHER on the
    # ancilla qubit -- check 2 must catch this even though check 3 wouldn't.
    mapping = _mapping(2, ["IX", "IZ"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert result["checks"]["stabilizers_abelian"]["passed"] is False


def test_redundant_stabilizer_list_rejected_by_dimension_check():
    # Same generator submitted twice: rank stays 1, but len(stabilizers)==2.
    mapping = _mapping(2, ["IZ", "IZ"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    dim = result["checks"]["codespace_dimension"]
    assert dim["passed"] is False
    assert dim["n_stabilizers"] == 2
    assert dim["rank"] == 1


def test_too_few_stabilizers_for_the_ancilla_count_rejected():
    # 2 ancillas (n_qubits=3) but only 1 independent stabilizer supplied.
    mapping = _mapping(3, ["IIZ"], majoranas=["XII", "ZII"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    dim = result["checks"]["codespace_dimension"]
    assert dim["n_ancillas"] == 2
    assert dim["rank"] == 1


def test_malformed_stabilizer_length_rejected_before_algebra_checks():
    mapping = _mapping(2, ["Z"])  # length 1, should be length 2
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert result["checks"]["stabilizers_well_formed"]["passed"] is False


def test_malformed_stabilizer_characters_rejected():
    mapping = _mapping(2, ["IA"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert result["checks"]["stabilizers_well_formed"]["passed"] is False


def test_legacy_majorana_algebra_failure_still_caught_first():
    # A corrupted Majorana pair (both "XI", which commute) must fail at the
    # legacy check-1 stage, before stabilizer checks ever run.
    mapping = _mapping(2, ["IZ"], majoranas=["XI", "XI"])
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert "majorana_algebra" in result["checks"]
    assert "stabilizers_abelian" not in result["checks"]


def test_missing_stabilizers_key_defaults_to_empty_list():
    mapping = {"n_qubits": 1, "majoranas": ["X", "Z"]}  # no "stabilizers" key
    result = verify_extended(_SPEC_M1, mapping)
    assert result["passed"]


def test_never_raises_on_garbage_stabilizers_field():
    mapping = _mapping(2, "not-a-list")
    result = verify_extended(_SPEC_M1, mapping)
    assert not result["passed"]
    assert result["checks"]["stabilizers_well_formed"]["passed"] is False


def test_result_shape_matches_legacy_checks_plus_new_ones():
    mapping = _mapping(2, ["IZ"])
    result = verify_extended(_SPEC_M1, mapping)
    for key in ("well_formed", "majorana_algebra", "stabilizers_well_formed",
                "stabilizers_abelian", "stabilizers_compatible", "codespace_dimension"):
        assert key in result["checks"]
