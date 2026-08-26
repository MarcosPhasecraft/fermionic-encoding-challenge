"""Rejection tests for harness.verify -- PLAN.md Sec 1.7 Test 2.

Fixtures are hand-built here rather than sourced from baselines/lattice, so
a bug in those modules can't mask or fake a verify() result.

Only checks 0 (well-formed) and 1 (Majorana algebra) exist so far. The
"too few qubits" and "S = ZZII stabilizer" rejection cases from PLAN.md
Sec 1.5 need checks 4 and 3 respectively -- add them once those exist.
"""

from harness.verify import verify

SPEC = {"name": "test-M3", "M": 3}

# Jordan-Wigner Majoranas for M=3 (gamma_j = Z^j X, gammabar_j = Z^j Y).
GOOD_MAJORANAS = ["XII", "YII", "ZXI", "ZYI", "ZZX", "ZZY"]


def _mapping(majoranas, n_qubits=3):
    return {"n_qubits": n_qubits, "majoranas": majoranas, "stabilizers": []}


def test_valid_mapping_passes():
    assert verify(SPEC, _mapping(GOOD_MAJORANAS))["passed"]


def test_corrupted_majorana_fails_algebra_check():
    # Drop the Z prefix on gamma_1: "ZXI" -> "XXI".
    corrupted = list(GOOD_MAJORANAS)
    corrupted[2] = "XXI"
    result = verify(SPEC, _mapping(corrupted))

    assert not result["passed"]
    assert result["checks"]["well_formed"]["passed"]  # still a valid Pauli string
    algebra = result["checks"]["majorana_algebra"]
    assert not algebra["passed"]
    assert algebra["n_violations"] > 0
    assert (0, 2) in algebra["violations"]


def test_wrong_string_length_fails_well_formed():
    malformed = list(GOOD_MAJORANAS)
    malformed[2] = "ZX"  # dropped a character
    result = verify(SPEC, _mapping(malformed))

    assert not result["passed"]
    assert not result["checks"]["well_formed"]["passed"]
    assert "majorana_algebra" not in result["checks"]  # never reached


def test_wrong_number_of_strings_fails_well_formed():
    result = verify(SPEC, _mapping(GOOD_MAJORANAS[:-1]))  # 5 instead of 6
    assert not result["passed"]
    assert not result["checks"]["well_formed"]["passed"]


def test_illegal_characters_fail_well_formed():
    malformed = list(GOOD_MAJORANAS)
    malformed[0] = "AII"  # 'A' is not a valid Pauli character
    result = verify(SPEC, _mapping(malformed))

    assert not result["passed"]
    assert not result["checks"]["well_formed"]["passed"]


def test_non_dict_spec_reports_issue_instead_of_raising():
    result = verify(None, _mapping(GOOD_MAJORANAS))
    assert not result["passed"]
    assert not result["checks"]["well_formed"]["passed"]


def test_non_dict_mapping_reports_issue_instead_of_raising():
    result = verify(SPEC, None)
    assert not result["passed"]
    assert not result["checks"]["well_formed"]["passed"]


def test_missing_m_in_spec_reports_issue_instead_of_raising():
    result = verify({}, _mapping(GOOD_MAJORANAS))
    assert not result["passed"]
    assert not result["checks"]["well_formed"]["passed"]
