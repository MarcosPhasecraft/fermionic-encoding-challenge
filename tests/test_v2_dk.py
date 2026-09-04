"""Tests for harness.v2.baselines.dk -- the Derby-Klassen square-lattice
baseline (arXiv 2003.06939). Verifies the reconstruction against the
paper's own stated Table I results (max hopping weight 3, max Coulomb
weight 2, fewer than 1.5 qubits per mode) via the actual harness, not by
re-deriving the physics in the test itself.
"""

import pytest

from harness.lattice import build_spec
from harness.v2.baselines.dk import encode, represent
from harness.v2.evaluate import evaluate_extended
from harness.v2.hamiltonian_terms import hamiltonian_terms
from harness.v2.verify import verify_extended

# Case I (even face count) -- the paper's cleanest case.
_CASE_I_SIZES = [(3, 3), (4, 3), (3, 4), (3, 5), (5, 3), (5, 5), (7, 3), (9, 9)]
# Case III (odd face count, i.e. Lx and Ly both even): majority-odd
# colouring plus one extra corner-to-corner stabilizer removing the spare
# logical qubit -- Supplementary Material Theorem 3.
_CASE_III_SIZES = [(4, 4), (6, 6), (4, 6), (6, 4), (8, 8), (10, 10)]
_ALL_SIZES = _CASE_I_SIZES + _CASE_III_SIZES
_DEGENERATE_SIZES = [(1, 1), (1, 3), (3, 1)]


@pytest.mark.parametrize("lx,ly", _ALL_SIZES)
def test_verify_extended_passes_at_every_case_i_size(lx, ly):
    spec = build_spec(lx, ly, None)
    mapping = encode(spec)
    result = verify_extended(spec, mapping)
    assert result["passed"], result["checks"]


@pytest.mark.parametrize("lx,ly", _ALL_SIZES)
def test_codespace_dimension_is_exactly_the_full_fock_space(lx, ly):
    # n_stabilizers == rank == n_ancillas, giving 2**M exactly -- not a
    # restricted-parity or extra-logical-qubit space.
    spec = build_spec(lx, ly, None)
    mapping = encode(spec)
    result = verify_extended(spec, mapping)
    dim = result["checks"]["codespace_dimension"]
    assert dim["n_ancillas"] == mapping["n_qubits"] - spec["M"]
    assert dim["n_stabilizers"] == dim["rank"] == dim["n_ancillas"]


@pytest.mark.parametrize("lx,ly", _ALL_SIZES)
def test_qubit_count_is_under_1_5_times_the_mode_count(lx, ly):
    spec = build_spec(lx, ly, None)
    mapping = encode(spec)
    assert mapping["n_qubits"] < 1.5 * spec["M"]


@pytest.mark.parametrize("lx,ly", _ALL_SIZES)
def test_matches_the_papers_own_table_1_weight_claims(lx, ly):
    spec = build_spec(lx, ly, None)
    mapping = encode(spec)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, encode, terms, represent_fn=represent)
    assert result["passed"], result
    assert result["max_rehop_weight"] == 3
    assert result["max_imhop_weight"] == 3
    assert result["max_num_weight"] == 1
    assert result["max_int_weight"] == 2
    assert result["max_weight"] == 3


@pytest.mark.parametrize("lx,ly", _CASE_III_SIZES)
def test_case_iii_sizes_are_supported_not_rejected(lx, ly):
    # Both Lx, Ly even -> odd face count. Previously refused outright; now
    # handled via the paper's own majority-odd colouring (Theorem 3) plus
    # one extra stabilizer, with no extension beyond the paper.
    spec = build_spec(lx, ly, None)
    mapping = encode(spec)
    assert verify_extended(spec, mapping)["passed"]


@pytest.mark.parametrize("lx,ly", _CASE_III_SIZES)
def test_case_iii_uses_one_more_stabilizer_than_it_has_even_faces(lx, ly):
    # floor(nF/2) even-face loops + 1 corner-to-corner string = ceil(nF/2)
    # = n_ancillas, which is exactly what collapses the extra logical qubit.
    spec = build_spec(lx, ly, None)
    mapping = encode(spec)
    n_faces = (lx - 1) * (ly - 1)
    assert n_faces % 2 == 1
    assert len(mapping["stabilizers"]) == (n_faces + 1) // 2
    assert mapping["n_qubits"] - spec["M"] == (n_faces + 1) // 2


@pytest.mark.parametrize("lx,ly", [(4, 4), (6, 6), (8, 8), (10, 10)])
def test_case_iii_qubit_count_matches_the_papers_majority_odd_faces_column(lx, ly):
    # Table I's own "majority odd faces" column: 1.5L^2 - L + 1 qubits.
    spec = build_spec(lx, lx, None)
    mapping = encode(spec)
    assert mapping["n_qubits"] == int(1.5 * lx * lx) - lx + 1


@pytest.mark.parametrize("lx,ly", _DEGENERATE_SIZES)
def test_degenerate_zero_face_sizes_are_rejected(lx, ly):
    spec = build_spec(lx, ly, None)
    with pytest.raises(ValueError, match="no faces"):
        encode(spec)


def test_uncertified_representative_would_be_caught_by_score_extended():
    # Sanity check that this baseline's own represent() isn't accidentally
    # exempt from certification -- swap in a deliberately-wrong hook and
    # confirm score_extended still rejects it (proves represent()'s outputs
    # are being genuinely checked against the stabilizer group, not just
    # trusted because they came from a "real" baseline).
    from harness.v2.score import RepresentativeRejected, score_extended

    spec = build_spec(3, 3, None)
    mapping = encode(spec)
    terms = hamiltonian_terms(spec, model="full")

    def wrong_represent(term, raw_pauli, spec, mapping):
        return "I" * mapping["n_qubits"]  # never a valid representative

    with pytest.raises(RepresentativeRejected):
        score_extended(spec, mapping, terms, represent_fn=wrong_represent)


def test_no_represent_hook_still_verifies_though_raw_weight_may_be_higher():
    # The raw (undressed) majoranas must still pass verify_extended and
    # score without a represent() hook -- represent() only affects which
    # representative is used for scoring, not whether the encoding itself
    # is valid.
    spec = build_spec(3, 3, None)
    mapping = encode(spec)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, encode, terms, represent_fn=None)
    assert result["passed"]
    assert result["total_weight"] >= 0
