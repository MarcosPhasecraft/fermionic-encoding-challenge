"""Extended scorer: certified stabilizer-dressed Pauli weight, plus
per-category maxima (max_rehop_weight/max_imhop_weight/max_num_weight/
max_int_weight).

Assumes `mapping` has already passed harness.v2.verify.verify_extended --
no re-validation of the Majorana/stabilizer algebra here, same division of
labor as harness.score.score_majorana. Not an edit to harness/score.py --
see harness/v2/verify.py's docstring for why new functionality lives in
harness/v2/ instead.

Logical Pauli operators on a stabilizer code are defined only modulo the
stabilizer group: P and P*S represent the same operator for any stabilizer
S, so the harness cannot just XOR the submitted Majoranas and score that raw
product -- a construction like Derby-Klassen can have a much lower-weight
local representative for a Hamiltonian term than its raw Majorana product,
differing from it by exactly a stabilizer. Finding the true minimum-weight
coset representative is a decoding problem this frozen scorer has no
business solving; instead the submission may supply an optional
represent(term, raw_pauli, spec, mapping) -> str hook proposing one, and
this module *certifies* it exactly (raw_pauli * proposed is in the
stabilizer group) before trusting its weight. An uncertified proposal is
rejected before scoring, never silently ignored or silently accepted.
"""

import numpy as np

from harness.paulis import string_to_xz, strings_to_xz_matrix, xz_to_string
from harness.v2.binary_linear_algebra import Gf2RowSpace

_CATEGORIES = ("rehop", "imhop", "num", "int")


class RepresentativeRejected(Exception):
    """A submission's represent() hook returned something that isn't a
    valid, stabilizer-equivalent representative of the raw Majorana product
    it was asked to represent -- or crashed. Raised, not silently swallowed;
    harness.v2.evaluate.evaluate_extended catches this and turns it into a
    structured failed result, the same never-crash-past-the-caller
    convention harness.evaluate.evaluate uses for a crashing encode_fn.
    """


def _raw_pauli_xz(x: np.ndarray, z: np.ndarray, majorana_indices: tuple):
    idx = list(majorana_indices)
    return np.bitwise_xor.reduce(x[idx], axis=0), np.bitwise_xor.reduce(z[idx], axis=0)


def score_extended(spec: dict, mapping: dict, term_records: list, represent_fn=None) -> dict:
    """term_records: list[harness.v2.hamiltonian_terms.HamiltonianTerm], not
    the bare majorana-index tuples harness.lattice.hamiltonian() returns --
    category maxima need each term's category label.

    Raises RepresentativeRejected if represent_fn proposes (or crashes
    while proposing) an uncertifiable representative for any term; callers
    that need the never-raise convention should go through
    harness.v2.evaluate.evaluate_extended instead of calling this directly.
    """
    majoranas = mapping["majoranas"]
    stabilizers = mapping.get("stabilizers", [])
    n_qubits = mapping["n_qubits"]
    x, z = strings_to_xz_matrix(majoranas)

    if stabilizers:
        sx, sz = strings_to_xz_matrix(stabilizers)
        s_bin = np.hstack([sx, sz])
    else:
        s_bin = np.zeros((0, 2 * n_qubits), dtype=np.uint8)
    stabilizer_space = Gf2RowSpace(s_bin)

    weights = []
    category_weights = {c: [] for c in _CATEGORIES}

    for t in term_records:
        raw_x, raw_z = _raw_pauli_xz(x, z, t.majoranas)

        if represent_fn is None:
            rep_x, rep_z = raw_x, raw_z
        else:
            raw_string = xz_to_string(raw_x, raw_z)
            try:
                rep_string = represent_fn(t, raw_string, spec, mapping)
            except Exception as e:
                raise RepresentativeRejected(f"represent() for {t} raised {type(e).__name__}: {e}") from e

            if not isinstance(rep_string, str) or len(rep_string) != n_qubits:
                raise RepresentativeRejected(
                    f"represent() for {t} returned {rep_string!r}, expected a length-{n_qubits} Pauli string"
                )
            try:
                rep_x, rep_z = string_to_xz(rep_string)
            except KeyError:
                raise RepresentativeRejected(f"represent() for {t} returned {rep_string!r}, not a valid IXYZ string")

            diff = np.concatenate([rep_x ^ raw_x, rep_z ^ raw_z])
            if not stabilizer_space.contains(diff):
                raise RepresentativeRejected(
                    f"represent() for {t} proposed {rep_string!r}, not equivalent to the raw "
                    f"product {raw_string!r} modulo the stabilizer group"
                )

        w = int(np.count_nonzero(rep_x | rep_z))
        weights.append(w)
        category_weights[t.category].append(w)

    def _max_or_none(ws):
        return max(ws) if ws else None

    return {
        "n_qubits": n_qubits,
        "n_modes": spec["M"],
        "n_ancillas": n_qubits - spec["M"],
        "n_stabilizers": len(stabilizers),
        "total_weight": int(sum(weights)),
        "max_weight": max(weights) if weights else 0,
        "avg_weight": sum(weights) / len(weights) if weights else 0.0,
        "max_rehop_weight": _max_or_none(category_weights["rehop"]),
        "max_imhop_weight": _max_or_none(category_weights["imhop"]),
        "max_num_weight": _max_or_none(category_weights["num"]),
        "max_int_weight": _max_or_none(category_weights["int"]),
    }
