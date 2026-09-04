"""Tests for scripts/update_leaderboard_ancillas.py -- same monkeypatch-the-
module-level-functions isolation style as tests/test_update_leaderboard.py.

The per-track behaviour is the interesting part: an entry is ranked on
every showcased weight cap it ACHIEVES, not the one it claimed.
"""

import io

import scripts.update_leaderboard_ancillas as ula


def _counting_fake(monkeypatch, results_by_size):
    """results_by_size: {L: (n_ancillas, achieved_max_weight)}."""
    calls = []

    def fake_evaluate(encode_fn, represent_fn, order_fn, lx, ly, claimed_max_weight):
        calls.append((lx, ly))
        return results_by_size[lx]

    monkeypatch.setattr(ula, "evaluate_ancilla_baseline", fake_evaluate)
    return calls


def test_scored_with_cache_first_call_computes_everything(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: (2, 3), 5: (8, 3)})
    entries = {}
    scores, recomputed = ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries, 3)
    assert recomputed is True
    assert len(calls) == 2
    assert scores == {0: (2, 3), 2: (8, 3)}  # SIZES.index(3)==0, SIZES.index(5)==2


def test_scored_with_cache_second_call_same_fingerprint_never_recomputes(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: (2, 3), 5: (8, 3)})
    entries = {}
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries, 3)
    calls.clear()
    scores, recomputed = ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries, 3)
    assert recomputed is False
    assert len(calls) == 0
    assert scores == {0: (2, 3), 2: (8, 3)}


def test_scored_with_cache_fingerprint_change_forces_recompute(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: (2, 3), 5: (8, 3)})
    entries = {}
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries, 3)
    calls.clear()
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp2", entries, 3)
    assert len(calls) == 2


def test_scored_with_cache_new_size_only_computes_the_new_one(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: (2, 3), 5: (8, 3), 7: (18, 3)})
    entries = {}
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries, 3)
    calls.clear()
    ula.scored_with_cache("dk", None, None, None, [3, 5, 7], "fp1", entries, 3)
    assert calls == [(7, 7)]


def test_scored_with_cache_legacy_entry_without_max_weight_is_recomputed(monkeypatch):
    # Cache entries written before per-track ranking existed stored only
    # n_ancillas -- the achieved weight decides which boards an entry lands
    # on, so a hit missing it must recompute rather than guess.
    calls = _counting_fake(monkeypatch, {3: (2, 3)})
    entries = {"dk": {"fingerprint": "fp1", "scores": {"3": {"n_ancillas": 2}}}}
    scores, recomputed = ula.scored_with_cache("dk", None, None, None, [3], "fp1", entries, 3)
    assert recomputed is True
    assert calls == [(3, 3)]
    assert scores == {0: (2, 3)}


def test_scored_with_cache_size_outside_sizes_still_cached_but_not_returned(monkeypatch):
    # 16 is outside SIZES (3..15) -- still evaluated/cached (mirrors the
    # ancilla-free leaderboard's is_showcased-excluded-but-still-scored
    # philosophy), just not folded into the returned column dict.
    calls = _counting_fake(monkeypatch, {3: (2, 3), 16: (999, 3)})
    entries = {}
    scores, _ = ula.scored_with_cache("dk", None, None, None, [3, 16], "fp1", entries, 3)
    assert 16 not in scores
    assert "16" in entries["dk"]["scores"]


# ---- per-track filtering (entries_for_cap / dated_for_cap) -------------------

_ENTRIES = [
    # achieves weight 3 at both sizes -> qualifies for the 3 and 4 boards
    ("dk", "2026-01-01T00:00:00+00:00", "Derby-Klassen", "harness/v2/baselines/dk.py", {0: (2, 3), 2: (8, 3)}),
    # achieves weight 4 -> only the 4 board, and with fewer ancillas
    ("loose", "2026-02-01T00:00:00+00:00", "Loose Encoding", "harness/v2/baselines/loose.py", {0: (1, 4), 2: (5, 4)}),
]


def test_entries_for_cap_3_excludes_the_weight_4_entry():
    got = ula.entries_for_cap(_ENTRIES, 3)
    assert [label for label, link, values in got] == ["Derby-Klassen"]


def test_entries_for_cap_4_includes_both():
    got = ula.entries_for_cap(_ENTRIES, 4)
    assert sorted(label for label, link, values in got) == ["Derby-Klassen", "Loose Encoding"]


def test_entries_for_cap_filters_per_size_not_per_entry():
    # An entry that meets the cap at one size but not another is listed only
    # at the sizes where it actually does.
    mixed = [("m", None, "Mixed", "l.py", {0: (2, 3), 2: (5, 4)})]
    assert ula.entries_for_cap(mixed, 3) == [("Mixed", "l.py", {0: 2})]
    assert ula.entries_for_cap(mixed, 4) == [("Mixed", "l.py", {0: 2, 2: 5})]


def test_entries_for_cap_drops_an_entry_qualifying_nowhere():
    assert ula.entries_for_cap([("m", None, "Mixed", "l.py", {0: (2, 5)})], 3) == []


def test_dated_for_cap_skips_undated_entries():
    undated = [("m", None, "Mixed", "l.py", {0: (2, 3)})]
    assert ula.dated_for_cap(undated, 3) == []


def test_dated_for_cap_shape_matches_progress_chart_expectations():
    got = ula.dated_for_cap(_ENTRIES, 4)
    assert got[0] == ("dk", "2026-01-01T00:00:00+00:00", "Derby-Klassen", {0: 2, 2: 8})


# ---- compute_square_entries / rendering --------------------------------------

def test_compute_square_entries_excludes_hexagonal_registrations(monkeypatch):
    monkeypatch.setattr(ula, "load_ancilla_registry", lambda: {
        "dk": {"module": "harness.v2.baselines.dk", "sizes": [3], "label": "Derby-Klassen",
               "graph": "square", "max_weight": 3, "submitted_at": None},
        "alice_hex": {"module": "harness.v2.baselines.alice_hex", "sizes": [(3, 3)], "label": "Alice Hex",
                      "graph": "hexagonal", "max_weight": 3, "submitted_at": None},
    })
    monkeypatch.setattr(ula, "_load_ancilla_cache", lambda: {})
    monkeypatch.setattr(ula, "_save_ancilla_cache", lambda cache: None)
    monkeypatch.setattr(ula, "harness_v2_fingerprint", lambda: "fp")

    from harness.v2.baselines import dk
    monkeypatch.setattr(ula, "load_submission_extended", lambda path: (dk.encode, None, dk.represent))
    monkeypatch.setattr(ula, "hash_file", lambda path: "filefp")

    entries = ula.compute_square_entries()
    labels = {label for name, submitted_at, label, link, scores in entries}
    assert labels == {"Derby-Klassen"}  # alice_hex excluded -- graph != "square"


def test_render_body_writes_one_section_per_showcased_cap():
    f = io.StringIO()
    charts = {cap: f"assets/progress_ancillas_square_w{cap}.png" for cap in ula.ANCILLA_SHOWCASED_MAX_WEIGHTS}
    ula.render_ancilla_leaderboard_body(f, _ENTRIES, charts)
    body = f.getvalue()
    for cap in ula.ANCILLA_SHOWCASED_MAX_WEIGHTS:
        assert f"max weight ≤ {cap}" in body
        assert f"progress_ancillas_square_w{cap}.png" in body
    # The weight-4-only entry must appear on the 4 board but not the 3 board.
    board3, board4 = body.split("max weight ≤ 4")[0], body.split("max weight ≤ 4")[1]
    assert "Loose Encoding" not in board3
    assert "Loose Encoding" in board4


def test_render_body_does_not_double_up_headings():
    f = io.StringIO()
    charts = {cap: "chart.png" for cap in ula.ANCILLA_SHOWCASED_MAX_WEIGHTS}
    ula.render_ancilla_leaderboard_body(f, _ENTRIES, charts)
    headings = [line for line in f.getvalue().splitlines() if line.startswith("## ")]
    assert len(headings) == len(ula.ANCILLA_SHOWCASED_MAX_WEIGHTS)
