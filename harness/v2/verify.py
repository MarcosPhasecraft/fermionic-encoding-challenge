"""Extended verifier: adds the stabilizer checks (2-4) that PLAN.md Sec 1.5
specced back in Stage 1 but left unimplemented, on top of the legacy
checks 0-1 (well-formed, Majorana algebra) from harness/verify.py.

Lives in harness/v2/ rather than being added directly to harness/verify.py,
for the same reason as harness/v2/hamiltonian_terms.py not wrapping
harness/lattice.py: scripts/submission_lib.py's harness_fingerprint() hashes
every harness/*.py file's content to gate the whole legacy score cache, and
Path.glob("*.py") is non-recursive, so harness/v2/*.py is invisible to it --
no existing baseline needs rescoring because this module exists. See
NOTES.md for the fuller ancilla/stabilizer-extension writeup.

An ancilla-free mapping (n_qubits == M, stabilizers == []) passes checks
2-4 vacuously and verify_extended's result is equivalent to plain
harness.verify.verify's.

**Check 3 here is stricter than PLAN.md Sec 1.5's own spec, deliberately.**
PLAN.md requires only that a stabilizer's commutation signature against the
Majoranas be *constant* (all-commute, or all-anticommute) -- provably
sufficient for this harness's own scoring, since every Hamiltonian term
harness.lattice.hamiltonian()/harness.v2.hamiltonian_terms() ever produces
is an EVEN-degree product of Majoranas (2 for hopping/number, 4 for
interaction, never odd), and a constant-signature stabilizer commutes with
any even-degree product regardless of whether the constant is 0 or 1
(each of the 2k anticommutations it picks up moving past the factors
cancels: (-1)^(2k) = 1 either way). This module instead requires the
stronger condition -- a stabilizer must commute with *every individual*
Majorana, not just have a constant signature -- because the ancilla
extension's submission contract treats the 2M submitted Majoranas
themselves as claimed logical operators on the code space (not merely
building blocks that are only ever used in even-sized products), and a
constant-but-nonzero signature means every individual Majorana maps between
different stabilizer eigenspaces rather than preserving the code. This is a
deliberate, chosen tradeoff (stricter than the current benchmark's scoring
strictly requires) -- not a bug, and not an oversight of PLAN.md's own
(different, also-correct-for-its-narrower-purpose) condition.
"""

import numpy as np

from harness.paulis import commutation_matrix, strings_to_xz_matrix
from harness.v2.binary_linear_algebra import gf2_rank
from harness.verify import verify as verify_legacy

_VALID_CHARS = set("IXYZ")


def _check_stabilizers_well_formed(n_qubits: int, stabilizers) -> dict:
    issues = []
    if not isinstance(stabilizers, list):
        return {"passed": False, "issues": [f"stabilizers must be a list, got {stabilizers!r}"]}

    for idx, s in enumerate(stabilizers):
        if not isinstance(s, str) or len(s) != n_qubits:
            issues.append(f"stabilizers[{idx}] has length {len(s) if isinstance(s, str) else s!r}, expected {n_qubits}")
        elif not set(s) <= _VALID_CHARS:
            bad = sorted(set(s) - _VALID_CHARS)
            issues.append(f"stabilizers[{idx}]={s!r} has invalid characters {bad}")

    return {"passed": len(issues) == 0, "issues": issues}


def _stacked_xz(majoranas: list[str], stabilizers: list[str], n_qubits: int):
    """(X, Z) for majoranas followed by stabilizers, stacked into one matrix
    so a single harness.paulis.commutation_matrix() call yields the
    Majorana-Majorana, Majorana-stabilizer, and stabilizer-stabilizer blocks
    at once -- reuses that function unmodified rather than adding a
    rectangular (two-different-operand-sets) variant of it.
    """
    mx, mz = strings_to_xz_matrix(majoranas)
    if stabilizers:
        sx, sz = strings_to_xz_matrix(stabilizers)
    else:
        sx = np.zeros((0, n_qubits), dtype=np.uint8)
        sz = np.zeros((0, n_qubits), dtype=np.uint8)
    return np.vstack([mx, sx]), np.vstack([mz, sz])


def verify_extended(spec: dict, mapping: dict) -> dict:
    """verify(), extended with stabilizer checks 2-4. Never raises, same
    convention as harness.verify.verify -- every failure is reported in the
    returned dict.
    """
    legacy = verify_legacy(spec, mapping)
    result = {"passed": False, "checks": dict(legacy["checks"])}
    if not legacy["passed"]:
        return result

    n_qubits = mapping["n_qubits"]
    m = spec["M"]
    stabilizers = mapping.get("stabilizers", [])

    well_formed = _check_stabilizers_well_formed(n_qubits, stabilizers)
    result["checks"]["stabilizers_well_formed"] = well_formed
    if not well_formed["passed"]:
        return result

    n_majoranas = len(mapping["majoranas"])  # == 2M, guaranteed by legacy well_formed
    X, Z = _stacked_xz(mapping["majoranas"], stabilizers, n_qubits)
    C = commutation_matrix(X, Z)
    stab_block = C[n_majoranas:, n_majoranas:]
    cross_block = C[:n_majoranas, n_majoranas:]

    abelian = {"passed": bool(np.all(stab_block == 0))}
    result["checks"]["stabilizers_abelian"] = abelian

    # Strong condition -- see module docstring for why this isn't PLAN.md
    # Sec 1.5's weaker "constant signature" rule.
    compatible = {"passed": bool(np.all(cross_block == 0))}
    result["checks"]["stabilizers_compatible"] = compatible

    if stabilizers:
        sx, sz = strings_to_xz_matrix(stabilizers)
        rank = gf2_rank(np.hstack([sx, sz]))
    else:
        rank = 0

    # n_qubits >= m is guaranteed here: check 1 (2M pairwise-anticommuting
    # Paulis) already forces it, since at most 2*n_qubits Paulis on n_qubits
    # qubits can pairwise anticommute.
    expected_ancillas = n_qubits - m
    dimension = {
        "passed": len(stabilizers) == rank == expected_ancillas,
        "n_stabilizers": len(stabilizers),
        "rank": rank,
        "n_ancillas": expected_ancillas,
    }
    result["checks"]["codespace_dimension"] = dimension

    result["passed"] = abelian["passed"] and compatible["passed"] and dimension["passed"]
    return result
