"""Tests for harness.v2.hamiltonian_terms -- category-annotated Hamiltonian
terms that must reproduce harness.lattice.hamiltonian()'s exact output when
flattened, plus explicit category-count checks.
"""

from harness.graphs import hex_lattice, triangular_lattice
from harness.lattice import hamiltonian, rectangle
from harness.v2.hamiltonian_terms import hamiltonian_flat, hamiltonian_terms

_MODELS = ("hopping", "quadratic", "full")


def _specs():
    yield rectangle(1, 4)  # 1D chain
    yield rectangle(3, 3)
    yield rectangle(4, 3)  # off-square rectangle
    yield hex_lattice(3, 3)
    yield triangular_lattice(3, 3)


def test_flattened_v2_terms_match_legacy_hamiltonian_exactly():
    for spec in _specs():
        for model in _MODELS:
            assert hamiltonian_flat(spec, model) == hamiltonian(spec, model)


def test_every_term_has_even_degree():
    # The stabilizer-compatibility argument in harness/v2/verify.py's
    # docstring depends on this: every scored term is an even-degree
    # product of Majoranas.
    for spec in _specs():
        for term in hamiltonian_terms(spec, model="full"):
            assert len(term.majoranas) % 2 == 0


def test_category_counts_on_a_single_edge():
    spec = rectangle(2, 1)  # one edge, M=2
    terms = hamiltonian_terms(spec, model="full")
    counts = {c: 0 for c in ("rehop", "imhop", "num", "int")}
    for t in terms:
        counts[t.category] += 1
    assert counts == {"rehop": 2, "imhop": 2, "num": 2, "int": 3}
    assert len(terms) == len(hamiltonian(spec, model="full"))


def test_hopping_model_has_no_num_or_int_terms():
    spec = rectangle(2, 1)
    categories = {t.category for t in hamiltonian_terms(spec, model="hopping")}
    assert categories == {"rehop", "imhop"}


def test_quadratic_model_has_no_int_terms():
    spec = rectangle(2, 1)
    categories = {t.category for t in hamiltonian_terms(spec, model="quadratic")}
    assert categories == {"rehop", "imhop", "num"}


def test_source_metadata_identifies_the_edge_or_mode():
    spec = rectangle(2, 1)  # edge (0, 1), M=2
    terms = hamiltonian_terms(spec, model="full")
    edge_sources = {t.source for t in terms if t.category in ("rehop", "imhop")}
    assert edge_sources == {("edge", 0, 1)}
    mode_sources = {t.source for t in terms if t.category == "num"}
    assert mode_sources == {("mode", 0), ("mode", 1)}
