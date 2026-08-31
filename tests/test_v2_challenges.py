"""Tests for harness.v2.challenges -- Challenge A (min ancillas at fixed
max weight), Challenge B (min weight at fixed ancilla budget), and Pareto
frontier utilities.

_jw_plus_spectator wraps any valid ancilla-free encoding with one trivial
"spectator" ancilla qubit (always in a fixed stabilizer eigenstate) --
n_ancillas is always exactly 1, regardless of M, so it's a convenient
always-valid encode_fn for exercising the engine across real, varying-size
square-lattice specs without needing a genuine ancilla-saving construction
to exist yet.
"""

import pytest

from baselines.jw import encode as jw_encode
from harness.v2.challenges import (
    ChallengeError,
    dominates,
    load_challenges,
    pareto_frontier,
    run_min_ancillas_challenge,
    run_min_weight_challenge,
    validate_challenge,
)


def _jw_plus_spectator(spec):
    mapping = jw_encode(spec)
    m = mapping["n_qubits"]
    return {
        "n_qubits": m + 1,
        "majoranas": [s + "I" for s in mapping["majoranas"]],
        "stabilizers": ["I" * m + "Z"],
    }


def _crashing_encode(spec):
    raise RuntimeError("nope")


# ---- validate_challenge / load_challenges ---------------------------------

def test_validate_challenge_accepts_a_well_formed_ancillas_config():
    validate_challenge({"name": "x", "type": "min_ancillas_at_weight", "max_weight": 3, "sizes": ["3x3"]})


def test_validate_challenge_accepts_a_well_formed_weights_config():
    validate_challenge({"name": "x", "type": "min_weight_at_ancillas", "shape": "6x6", "max_ancillas": 4})


def test_validate_challenge_rejects_unknown_type():
    with pytest.raises(ChallengeError):
        validate_challenge({"name": "x", "type": "bogus"})


def test_validate_challenge_rejects_unknown_graph():
    with pytest.raises(ChallengeError):
        validate_challenge({"name": "x", "type": "min_ancillas_at_weight", "graph": "bogus", "max_weight": 3, "sizes": ["3x3"]})


def test_validate_challenge_rejects_missing_sizes():
    with pytest.raises(ChallengeError):
        validate_challenge({"name": "x", "type": "min_ancillas_at_weight", "max_weight": 3})


def test_validate_challenge_rejects_missing_max_weight():
    with pytest.raises(ChallengeError):
        validate_challenge({"name": "x", "type": "min_ancillas_at_weight", "sizes": ["3x3"]})


def test_validate_challenge_rejects_missing_shape():
    with pytest.raises(ChallengeError):
        validate_challenge({"name": "x", "type": "min_weight_at_ancillas", "max_ancillas": 4})


def test_load_challenges_reads_the_shipped_official_config():
    challenges = load_challenges("challenges/official.json")
    names = {c["name"] for c in challenges}
    assert "square_full_w3" in names
    assert "square_6x6_a4" in names


# ---- run_min_ancillas_challenge (Challenge A) ------------------------------

def test_ancillas_challenge_reports_a_profile_not_a_scalar():
    cfg = {"name": "x", "type": "min_ancillas_at_weight", "max_weight": 1000, "sizes": ["3x3", "4x4", "5x5"]}
    results = run_min_ancillas_challenge(cfg, _jw_plus_spectator)
    assert set(results) == {"3x3", "4x4", "5x5"}
    for size, r in results.items():
        assert r["eligible"] is True
        assert r["n_ancillas"] == 1  # constant regardless of M -- see module docstring


def test_ancillas_challenge_marks_sizes_exceeding_the_weight_cap_ineligible():
    cfg = {"name": "x", "type": "min_ancillas_at_weight", "max_weight": 1, "sizes": ["3x3"]}
    results = run_min_ancillas_challenge(cfg, _jw_plus_spectator)
    r = results["3x3"]
    assert r["eligible"] is False
    assert "max_weight" in r["reason"]


def test_ancillas_challenge_reports_a_crashing_encoder_as_ineligible_not_a_crash():
    cfg = {"name": "x", "type": "min_ancillas_at_weight", "max_weight": 3, "sizes": ["3x3"]}
    results = run_min_ancillas_challenge(cfg, _crashing_encode)
    r = results["3x3"]
    assert r["passed"] is False
    assert r["eligible"] is False
    assert "error" in r


def test_ancillas_challenge_a_construction_can_win_at_one_size_and_lose_at_another():
    # A cap that only the smallest size's max weight clears.
    small_max_weight = run_min_ancillas_challenge(
        {"name": "x", "type": "min_ancillas_at_weight", "max_weight": 1000, "sizes": ["3x3"]}, _jw_plus_spectator
    )["3x3"]["max_weight"]
    cfg = {"name": "x", "type": "min_ancillas_at_weight", "max_weight": small_max_weight, "sizes": ["3x3", "8x8"]}
    results = run_min_ancillas_challenge(cfg, _jw_plus_spectator)
    assert results["3x3"]["eligible"] is True
    assert results["8x8"]["eligible"] is False  # a bigger lattice needs more weight


# ---- run_min_weight_challenge (Challenge B) --------------------------------

def test_weights_challenge_eligible_within_budget():
    cfg = {"name": "x", "type": "min_weight_at_ancillas", "shape": "4x4", "max_ancillas": 4}
    result = run_min_weight_challenge(cfg, _jw_plus_spectator)
    assert result["eligible"] is True
    assert result["n_ancillas"] == 1
    assert "max_weight" in result and "total_weight" in result


def test_weights_challenge_ineligible_over_budget():
    cfg = {"name": "x", "type": "min_weight_at_ancillas", "shape": "4x4", "max_ancillas": 0}
    result = run_min_weight_challenge(cfg, _jw_plus_spectator)
    assert result["eligible"] is False
    assert "n_ancillas" in result["reason"]


def test_weights_challenge_reports_verification_failure_as_ineligible():
    def bad_encode(spec):
        return {"n_qubits": spec["M"] + 1, "majoranas": ["XI"] * (2 * spec["M"]), "stabilizers": []}

    cfg = {"name": "x", "type": "min_weight_at_ancillas", "shape": "2x1", "max_ancillas": 5}
    result = run_min_weight_challenge(cfg, bad_encode)
    assert result["passed"] is False
    assert result["eligible"] is False


# ---- Pareto frontier --------------------------------------------------------

def test_dominates_requires_strict_improvement_in_at_least_one_component():
    a = {"max_weight": 3, "total_weight": 100}
    b = {"max_weight": 3, "total_weight": 100}
    assert not dominates(a, b)  # identical points: neither dominates
    assert not dominates(b, a)


def test_dominates_true_when_no_worse_and_strictly_better_somewhere():
    a = {"max_weight": 3, "total_weight": 90}
    b = {"max_weight": 3, "total_weight": 100}
    assert dominates(a, b)
    assert not dominates(b, a)


def test_dominates_false_when_mixed_tradeoff():
    a = {"max_weight": 2, "total_weight": 110}
    b = {"max_weight": 3, "total_weight": 100}
    assert not dominates(a, b)
    assert not dominates(b, a)


def test_pareto_frontier_keeps_ties_and_drops_dominated_points():
    p1 = {"name": "p1", "max_weight": 3, "total_weight": 100}
    p2 = {"name": "p2", "max_weight": 3, "total_weight": 100}  # tie with p1
    p3 = {"name": "p3", "max_weight": 4, "total_weight": 90}   # incomparable with p1/p2
    p4 = {"name": "p4", "max_weight": 5, "total_weight": 200}  # dominated by everything

    frontier = pareto_frontier([p1, p2, p3, p4])
    names = {p["name"] for p in frontier}
    assert names == {"p1", "p2", "p3"}
