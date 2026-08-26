"""Frozen scorer: Pauli-weight metrics for a verified mapping.

Assumes `mapping` has already passed verify() -- no re-validation here, same
division of labor as paulis.py assuming well-formed strings.

Only score_majorana (our own weight definition) is implemented so far.
score_paper (arXiv 2504.21636 Sec III-C convention) comes with Table I
calibration (PLAN.md Sec 1.6-1.7 Test 4) -- do not reconstruct it from
prose, use their released code.
"""

import numpy as np

from harness.paulis import strings_to_xz_matrix


def _term_weight(x: np.ndarray, z: np.ndarray, term: tuple[int, ...]) -> int:
    """Pauli weight of the product of the Majoranas in `term`.

    XOR, not OR: shared X/Z factors on the same qubit cancel, which is why
    e.g. JW's long Z-strings mostly vanish in nearest-neighbour hopping terms.
    """
    idx = list(term)
    combined_x = np.bitwise_xor.reduce(x[idx], axis=0)
    combined_z = np.bitwise_xor.reduce(z[idx], axis=0)
    return int(np.count_nonzero(combined_x | combined_z))


def score_majorana(spec: dict, mapping: dict, terms: list[tuple[int, ...]]) -> dict:
    x, z = strings_to_xz_matrix(mapping["majoranas"])
    weights = [_term_weight(x, z, term) for term in terms]
    return {
        "n_qubits": mapping["n_qubits"],
        "total_weight": int(sum(weights)),
        "max_weight": max(weights) if weights else 0,
        "avg_weight": sum(weights) / len(weights) if weights else 0.0,
    }
