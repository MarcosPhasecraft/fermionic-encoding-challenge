"""Tests for harness/graphs.py -- the non-square 2D lattice builders for the
ancilla/graph-challenge phase. Exact edge counts below were computed by
running the builders directly (not hand-derived) and cross-checked via the
handshake lemma (sum of degrees == 2 * edge count) for the larger cases.
"""

import pytest

from harness.graphs import build_spec, hex_lattice, triangular_lattice


# --- hex_lattice ---


def test_hex_lattice_mode_count_is_2_lx_ly():
    assert hex_lattice(3, 4)["M"] == 24


def test_hex_lattice_2x2_open_edge_count():
    spec = hex_lattice(2, 2, periodic=False)
    assert len(spec["edges"]) == 8


def test_hex_lattice_2x2_periodic_edge_count():
    spec = hex_lattice(2, 2, periodic=True)
    assert len(spec["edges"]) == 12


def test_hex_lattice_periodic_has_more_edges_than_open_at_3x3():
    open_spec = hex_lattice(3, 3, periodic=False)
    periodic_spec = hex_lattice(3, 3, periodic=True)
    assert len(open_spec["edges"]) == 21
    assert len(periodic_spec["edges"]) == 27


def test_hex_lattice_3x3_periodic_is_3_regular():
    # Handshake lemma: every site has exactly 3 neighbours in the bulk, and
    # periodic wrapping removes all boundary effects, so this must hold
    # exactly: sum of degrees == 2 * edge count == 3 * M.
    spec = hex_lattice(3, 3, periodic=True)
    assert 2 * len(spec["edges"]) == 3 * spec["M"]


def test_hex_lattice_canonical_ordering_is_deterministic():
    assert hex_lattice(3, 3)["edges"] == hex_lattice(3, 3)["edges"]


def test_hex_lattice_custom_perm_overrides_default():
    m = 2 * 2 * 2
    reversed_perm = list(range(m))[::-1]
    spec = hex_lattice(2, 2, perm=reversed_perm)
    default_spec = hex_lattice(2, 2)
    assert spec["edges"] != default_spec["edges"]


def test_hex_lattice_rejects_invalid_perm():
    with pytest.raises(ValueError):
        hex_lattice(2, 2, perm=[0, 1, 2])  # wrong length


# --- triangular_lattice ---


def test_triangular_lattice_mode_count_is_lx_ly():
    assert triangular_lattice(4, 5)["M"] == 20


def test_triangular_lattice_2x2_open_edge_count():
    spec = triangular_lattice(2, 2, periodic=False)
    assert len(spec["edges"]) == 5


def test_triangular_lattice_2x2_periodic_edge_count():
    # Lx=Ly=2 is the degenerate case where a naive periodic wrap would
    # double-count every bond -- confirms the dedup actually collapses them.
    spec = triangular_lattice(2, 2, periodic=True)
    assert len(spec["edges"]) == 6


def test_triangular_lattice_3x3_periodic_is_6_regular():
    spec = triangular_lattice(3, 3, periodic=True)
    assert 2 * len(spec["edges"]) == 6 * spec["M"]


def test_triangular_lattice_no_self_loops_at_lx_or_ly_1():
    spec = triangular_lattice(1, 4, periodic=True)
    assert all(u != v for u, v in spec["edges"])


def test_triangular_lattice_canonical_ordering_is_deterministic():
    assert triangular_lattice(3, 3)["edges"] == triangular_lattice(3, 3)["edges"]


# --- build_spec dispatch ---


def test_build_spec_dispatches_to_hexagonal():
    spec = build_spec("hexagonal", 2, 2)
    assert spec["M"] == 8


def test_build_spec_dispatches_to_periodic_triangular():
    spec = build_spec("periodic_triangular", 3, 3)
    assert len(spec["edges"]) == 27


def test_build_spec_unknown_graph_raises():
    with pytest.raises(ValueError):
        build_spec("kagome", 3, 3)


def test_build_spec_uses_order_fn_when_given():
    called_with = {}

    def order_fn(Lx, Ly):
        called_with["Lx"], called_with["Ly"] = Lx, Ly
        return list(range(Lx * Ly))[::-1]

    default_spec = build_spec("triangular", 3, 3)
    custom_spec = build_spec("triangular", 3, 3, order_fn=order_fn)
    assert called_with == {"Lx": 3, "Ly": 3}
    assert custom_spec["edges"] != default_spec["edges"]
