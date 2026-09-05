"""Frozen verifier: checks that a mapping is a valid Majorana encoding.

Never raises on malformed input -- every check reports failure in the
returned dict instead. See PLAN.md Sec 1.5 for the check definitions.

Only checks 0 (well-formed) and 1 (Majorana algebra) are implemented so far.
Checks 2-4 (stabilizers) come once mapping["stabilizers"] is exercised.
"""

import numpy as np

from harness.paulis import commutation_matrix, strings_to_xz_matrix

_VALID_CHARS = set("IXYZ")


def _check_well_formed(spec: dict, mapping: dict) -> dict:
    if not isinstance(spec, dict):
        return {"passed": False, "issues": [f"spec must be a dict, got {spec!r}"]}
    if not isinstance(mapping, dict):
        return {"passed": False, "issues": [f"mapping must be a dict, got {mapping!r}"]}

    issues = []
    n_qubits = mapping.get("n_qubits")
    majoranas = mapping.get("majoranas")
    m = spec.get("M")

    if not isinstance(m, int) or m <= 0:
        issues.append(f"spec['M'] must be a positive int, got {m!r}")
        # Can't check the majorana count or anything downstream without a valid M.
        return {"passed": False, "issues": issues}

    if not isinstance(n_qubits, int) or n_qubits <= 0:
        issues.append(f"n_qubits must be a positive int, got {n_qubits!r}")

    if not isinstance(majoranas, list) or len(majoranas) != 2 * m:
        got = len(majoranas) if isinstance(majoranas, list) else majoranas
        issues.append(f"expected {2 * m} majorana strings (2M for M={m}), got {got!r}")
        # Can't check individual strings without a valid list of the right shape.
        return {"passed": False, "issues": issues}

    for idx, s in enumerate(majoranas):
        if not isinstance(s, str) or (isinstance(n_qubits, int) and len(s) != n_qubits):
            issues.append(f"majoranas[{idx}] has length {len(s) if isinstance(s, str) else s!r}, expected {n_qubits}")
        elif not set(s) <= _VALID_CHARS:
            bad = sorted(set(s) - _VALID_CHARS)
            issues.append(f"majoranas[{idx}]={s!r} has invalid characters {bad}")

    return {"passed": len(issues) == 0, "issues": issues}


def _check_majorana_algebra(majoranas: list[str]) -> dict:
    """Check 1: every distinct pair of Majoranas anticommutes (C == J - I)."""
    x, z = strings_to_xz_matrix(majoranas)
    c = commutation_matrix(x, z)
    k = len(majoranas)
    expected = 1 - np.eye(k, dtype=np.uint8)
    # Every failing pair, not a sample -- np.argwhere scans the whole upper
    # triangle, so this is exhaustive.
    bad = np.argwhere(np.triu(c != expected, k=1))
    violations = [(int(i), int(j)) for i, j in bad]
    # Return the full list, not just one example: a person or agent debugging
    # a broken proposal needs to see every failure to tell a single bug from
    # several distinct ones.
    return {
        "passed": len(violations) == 0,
        "n_violations": len(violations),
        "violations": violations,
    }


def verify(spec: dict, mapping: dict) -> dict:
    result = {"passed": False, "checks": {}}

    well_formed = _check_well_formed(spec, mapping)
    result["checks"]["well_formed"] = well_formed
    if not well_formed["passed"]:
        return result

    algebra = _check_majorana_algebra(mapping["majoranas"])
    result["checks"]["majorana_algebra"] = algebra

    result["passed"] = algebra["passed"]
    return result

# tampering attempt
