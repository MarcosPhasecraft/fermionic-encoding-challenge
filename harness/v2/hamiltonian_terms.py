"""Categorized Hamiltonian term lists -- the same terms harness.lattice's
hamiltonian(spec, model) returns, annotated with which physical piece
(ReHop/ImHop/Num/Int) each came from, needed by harness/v2/score.py to
report per-category maximum weights.

Deliberately a parallel implementation, not a wrapper around
harness.lattice.hamiltonian() or a refactor of it into one -- editing
harness/lattice.py would change its content hash and, via
scripts/submission_lib.py's harness_fingerprint(), invalidate the entire
legacy score cache for a change that produces identical scores. See
tests/test_v2_hamiltonian_terms.py's golden-regression test, which asserts
this module's flattened output is byte-for-byte identical to the legacy
function's for every model on several graphs -- that's what stands in for
"this really is the same logic" instead of sharing code.
"""

from dataclasses import dataclass

_VALID_MODELS = {"hopping", "quadratic", "full"}


@dataclass(frozen=True)
class HamiltonianTerm:
    majoranas: tuple  # Majorana-index tuple; same convention as harness.lattice.hamiltonian
    category: str  # "rehop" | "imhop" | "num" | "int"
    source: tuple  # ("edge", i, j) or ("mode", i) -- diagnostic only, not scored


def hamiltonian_terms(spec: dict, model: str = "quadratic") -> list[HamiltonianTerm]:
    if model not in _VALID_MODELS:
        raise ValueError(f"unknown model {model!r}, expected one of {_VALID_MODELS}")

    m = spec["M"]
    terms = []

    for i, j in spec["edges"]:
        terms.append(HamiltonianTerm((2 * i, 2 * j + 1), "rehop", ("edge", i, j)))
        terms.append(HamiltonianTerm((2 * i + 1, 2 * j), "rehop", ("edge", i, j)))
        terms.append(HamiltonianTerm((2 * i, 2 * j), "imhop", ("edge", i, j)))
        terms.append(HamiltonianTerm((2 * i + 1, 2 * j + 1), "imhop", ("edge", i, j)))

    if model in ("quadratic", "full"):
        for i in range(m):
            terms.append(HamiltonianTerm((2 * i, 2 * i + 1), "num", ("mode", i)))

    if model == "full":
        for i, j in spec["edges"]:
            terms.append(HamiltonianTerm((2 * i, 2 * i + 1), "int", ("edge", i, j)))
            terms.append(HamiltonianTerm((2 * j, 2 * j + 1), "int", ("edge", i, j)))
            terms.append(HamiltonianTerm((2 * i, 2 * i + 1, 2 * j, 2 * j + 1), "int", ("edge", i, j)))

    return terms


def hamiltonian_flat(spec: dict, model: str = "quadratic") -> list[tuple]:
    """[t.majoranas for t in hamiltonian_terms(...)] -- same shape as
    harness.lattice.hamiltonian()'s return value, for the golden-regression
    test and for any caller that only needs the bare index tuples.
    """
    return [t.majoranas for t in hamiltonian_terms(spec, model)]
