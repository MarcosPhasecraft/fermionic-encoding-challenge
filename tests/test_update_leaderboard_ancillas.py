"""Tests for scripts/update_leaderboard_ancillas.py -- same monkeypatch-the-
module-level-functions isolation style as tests/test_update_leaderboard.py.
"""

import io

import scripts.update_leaderboard_ancillas as ula


def _counting_fake(monkeypatch, n_ancillas_by_size):
    calls = []

    def fake_evaluate(encode_fn, represent_fn, order_fn, lx, ly):
        calls.append((lx, ly))
        return n_ancillas_by_size[lx], 3

    monkeypatch.setattr(ula, "evaluate_ancilla_baseline", fake_evaluate)
    return calls


def test_scored_with_cache_first_call_computes_everything(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: 2, 5: 8})
    entries = {}
    ancillas, recomputed = ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries)
    assert recomputed is True
    assert len(calls) == 2
    assert ancillas == {0: 2, 2: 8}  # SIZES.index(3)==0, SIZES.index(5)==2


def test_scored_with_cache_second_call_same_fingerprint_never_recomputes(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: 2, 5: 8})
    entries = {}
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries)
    calls.clear()
    ancillas, recomputed = ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries)
    assert recomputed is False
    assert len(calls) == 0
    assert ancillas == {0: 2, 2: 8}


def test_scored_with_cache_fingerprint_change_forces_recompute(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: 2, 5: 8})
    entries = {}
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries)
    calls.clear()
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp2", entries)
    assert len(calls) == 2


def test_scored_with_cache_new_size_only_computes_the_new_one(monkeypatch):
    calls = _counting_fake(monkeypatch, {3: 2, 5: 8, 7: 18})
    entries = {}
    ula.scored_with_cache("dk", None, None, None, [3, 5], "fp1", entries)
    calls.clear()
    ula.scored_with_cache("dk", None, None, None, [3, 5, 7], "fp1", entries)
    assert calls == [(7, 7)]


def test_scored_with_cache_size_outside_sizes_still_cached_but_not_returned(monkeypatch):
    # 16 is outside SIZES (3..15) -- still evaluated/cached (mirrors the
    # ancilla-free leaderboard's is_showcased-excluded-but-still-scored
    # philosophy), just not folded into the returned column dict.
    calls = _counting_fake(monkeypatch, {3: 2, 16: 999})
    entries = {}
    ancillas, _ = ula.scored_with_cache("dk", None, None, None, [3, 16], "fp1", entries)
    assert 16 not in ancillas
    assert "16" in entries["dk"]["scores"]


def test_compute_square_entries_excludes_hexagonal_registrations(monkeypatch):
    monkeypatch.setattr(ula, "load_ancilla_registry", lambda: {
        "dk": {"module": "harness.v2.baselines.dk", "sizes": [3], "label": "Derby-Klassen", "graph": "square", "submitted_at": None},
        "alice_hex": {"module": "harness.v2.baselines.alice_hex", "sizes": [(3, 3)], "label": "Alice Hex", "graph": "hexagonal", "submitted_at": None},
    })
    monkeypatch.setattr(ula, "_load_ancilla_cache", lambda: {})
    monkeypatch.setattr(ula, "_save_ancilla_cache", lambda cache: None)
    monkeypatch.setattr(ula, "harness_v2_fingerprint", lambda: "fp")

    from harness.v2.baselines import dk
    monkeypatch.setattr(ula, "load_submission_extended", lambda path: (dk.encode, None, dk.represent))
    monkeypatch.setattr(ula, "hash_file", lambda path: "filefp")

    entries, dated = ula.compute_square_entries()
    labels = {label for label, link, values in entries}
    assert labels == {"Derby-Klassen"}  # alice_hex excluded -- graph != "square"


def test_render_ancilla_leaderboard_body_includes_the_ranked_table():
    f = io.StringIO()
    ula.render_ancilla_leaderboard_body(
        f, "assets/progress_ancillas_square.png?v=abc",
        [("Derby-Klassen", "harness/v2/baselines/dk.py", {0: 2, 2: 8})],
    )
    body = f.getvalue()
    assert "Derby-Klassen" in body
    assert "min n_ancillas subject to max_weight" in body
    assert "Lower is better." in body
