"""Tests for scripts/update_leaderboard.py's caching layer -- the actual
correctness of a baseline's score is already covered by each baseline's
own tests (via harness.evaluate); these tests only cover the cache-hit/
miss/invalidate decisions, using a call-counting fake evaluate_baseline
so a cache hit can be proven by "the expensive function was never called
again", not just by the returned numbers matching.
"""

import scripts.update_leaderboard as update_leaderboard


def _counting_fake(monkeypatch):
    calls = []

    def fake_evaluate_baseline(encode_fn, order_fn, lx, ly):
        calls.append(lx)
        return (100 + lx, 10 + lx)

    monkeypatch.setattr(update_leaderboard, "evaluate_baseline", fake_evaluate_baseline)
    return calls


# --- scored_with_cache ---


def test_first_call_computes_everything_and_populates_cache(monkeypatch):
    calls = _counting_fake(monkeypatch)
    cache_entries = {}

    totals, maxes, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp1", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [3, 4]
    assert cache_entries["fake"]["fingerprint"] == "fp1"
    assert cache_entries["fake"]["scores"]["3"] == {"total": 103, "max": 13}
    assert cache_entries["fake"]["scores"]["4"] == {"total": 104, "max": 14}


def test_second_call_same_fingerprint_never_calls_evaluate_baseline_again(monkeypatch):
    calls = _counting_fake(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache("fake", None, None, [3, 4], "fp1", cache_entries)
    calls.clear()

    totals, maxes, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp1", cache_entries,
    )

    assert any_recomputed is False
    assert calls == []  # the whole point: the expensive function never ran again
    assert totals == {update_leaderboard.SIZES.index(3): 103, update_leaderboard.SIZES.index(4): 104}


def test_fingerprint_change_forces_full_recompute(monkeypatch):
    # A baseline's own file changed -- every previously cached score for
    # it is potentially stale, so all of its sizes recompute, not just the
    # ones that happen to differ.
    calls = _counting_fake(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache("fake", None, None, [3, 4], "fp1", cache_entries)
    calls.clear()

    _, _, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp2", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [3, 4]


def test_new_size_under_same_fingerprint_only_computes_the_new_one(monkeypatch):
    calls = _counting_fake(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache("fake", None, None, [3], "fp1", cache_entries)
    calls.clear()

    _, _, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp1", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [4]  # size 3 reused, not recomputed

# --- collect_memory_entries / write_memory_index ---


def test_collect_memory_entries_only_lists_baselines_with_a_memory_folder(tmp_path):
    (tmp_path / "alice.memory").mkdir()
    (tmp_path / "alice.memory" / "notes.md").write_text("# notes\n")
    (tmp_path / "bob.py").write_text("")  # no bob.memory/ at all

    entries = update_leaderboard.collect_memory_entries(
        tmp_path, [("alice", "Alice's Encoding"), ("bob", "Bob's Encoding")],
    )

    assert entries == [("alice", "Alice's Encoding", ["notes.md"])]


def test_collect_memory_entries_ignores_an_empty_memory_folder(tmp_path):
    (tmp_path / "alice.memory").mkdir()  # exists but no files in it

    entries = update_leaderboard.collect_memory_entries(tmp_path, [("alice", "Alice's Encoding")])

    assert entries == []


def test_collect_memory_entries_lists_multiple_files_sorted(tmp_path):
    memory_dir = tmp_path / "alice.memory"
    memory_dir.mkdir()
    (memory_dir / "z_later.md").write_text("")
    (memory_dir / "a_first.md").write_text("")

    entries = update_leaderboard.collect_memory_entries(tmp_path, [("alice", "Alice's Encoding")])

    assert entries == [("alice", "Alice's Encoding", ["a_first.md", "z_later.md"])]


def test_write_memory_index_links_to_the_right_files(tmp_path):
    memory_dir = tmp_path / "baselines" / "alice.memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "notes.md").write_text("")
    out_path = tmp_path / "MEMORY.md"

    update_leaderboard.write_memory_index(out_path, tmp_path / "baselines", [("alice", "Alice's Encoding")])

    content = out_path.read_text()
    assert "Alice's Encoding" in content
    assert "`alice`" in content
    assert "baselines/alice.memory/notes.md" in content
    assert "leads, not proven fact" in content  # the ECDSA-style caveat


def test_write_memory_index_omits_baselines_without_notes(tmp_path):
    (tmp_path / "baselines").mkdir()
    out_path = tmp_path / "MEMORY.md"

    update_leaderboard.write_memory_index(out_path, tmp_path / "baselines", [("bob", "Bob's Encoding")])

    content = out_path.read_text()
    assert "Bob's Encoding" not in content
    assert "Nothing here yet" in content


# --- scored_with_cache_graph: the graph-challenge analogue of
# scored_with_cache, keyed by "LxxLy" shape string rather than SIZES.index(l)
# since this table isn't a fixed 3..15 column layout, and mode count alone
# doesn't pin down the graph for these lattice types. ---


def _counting_fake_graph(monkeypatch):
    calls = []

    def fake_evaluate_graph_baseline(encode_fn, order_fn, graph, lx, ly):
        calls.append((graph, lx, ly))
        return (100 + lx, 3)  # (total, max)

    monkeypatch.setattr(update_leaderboard, "evaluate_graph_baseline", fake_evaluate_graph_baseline)
    return calls


def test_scored_with_cache_graph_first_call_computes_and_populates_cache(monkeypatch):
    calls = _counting_fake_graph(monkeypatch)
    cache_entries = {}

    scores, any_recomputed = update_leaderboard.scored_with_cache_graph(
        "fake", None, None, "hexagonal", [(3, 4), (5, 5)], "fp1", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [("hexagonal", 3, 4), ("hexagonal", 5, 5)]
    assert scores == {"3x4": {"total": 103, "max": 3}, "5x5": {"total": 105, "max": 3}}
    assert cache_entries["fake"]["fingerprint"] == "fp1"


def test_scored_with_cache_graph_second_call_same_fingerprint_never_recomputes(monkeypatch):
    calls = _counting_fake_graph(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache_graph("fake", None, None, "hexagonal", [(3, 3)], "fp1", cache_entries)
    calls.clear()

    scores, any_recomputed = update_leaderboard.scored_with_cache_graph(
        "fake", None, None, "hexagonal", [(3, 3)], "fp1", cache_entries,
    )

    assert any_recomputed is False
    assert calls == []
    assert scores == {"3x3": {"total": 103, "max": 3}}


def test_scored_with_cache_graph_fingerprint_change_forces_recompute(monkeypatch):
    calls = _counting_fake_graph(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache_graph("fake", None, None, "hexagonal", [(3, 3)], "fp1", cache_entries)
    calls.clear()

    _, any_recomputed = update_leaderboard.scored_with_cache_graph(
        "fake", None, None, "hexagonal", [(3, 3)], "fp2", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [("hexagonal", 3, 3)]


# --- compute_graph_entries: filters to non-square registry entries only ---


def test_compute_graph_entries_excludes_square_baselines(monkeypatch, tmp_path):
    monkeypatch.setattr(update_leaderboard, "BASELINES", {
        "jw": {"encode": None, "order": None, "sizes": [3], "label": "JW", "module": "baselines.jw", "graph": "square"},
    })
    monkeypatch.setattr(update_leaderboard, "load_score_cache", lambda: {})
    monkeypatch.setattr(update_leaderboard, "harness_fingerprint", lambda: "fp")
    monkeypatch.setattr(update_leaderboard, "save_score_cache", lambda cache: None)

    by_graph = update_leaderboard.compute_graph_entries()

    assert by_graph == {}


def test_compute_graph_entries_groups_by_graph_type(monkeypatch):
    monkeypatch.setattr(update_leaderboard, "BASELINES", {
        "alice": {
            "encode": None, "order": None, "sizes": [(8, 4)], "label": "Alice",
            "module": "baselines.alice", "graph": "hexagonal",
        },
    })
    monkeypatch.setattr(update_leaderboard, "load_score_cache", lambda: {})
    monkeypatch.setattr(update_leaderboard, "harness_fingerprint", lambda: "fp")
    monkeypatch.setattr(update_leaderboard, "save_score_cache", lambda cache: None)
    monkeypatch.setattr(update_leaderboard, "hash_file", lambda path: "filefp")
    monkeypatch.setattr(
        update_leaderboard, "evaluate_graph_baseline",
        lambda encode_fn, order_fn, graph, lx, ly: (42, 1),
    )

    by_graph = update_leaderboard.compute_graph_entries()

    assert list(by_graph.keys()) == ["hexagonal"]
    label, link, scores = by_graph["hexagonal"][0]
    assert label == "Alice"
    assert scores == {"8x4": {"total": 42, "max": 1}}


# --- render_graph_challenge_table ---


def test_render_graph_challenge_table_includes_submission_and_paper_rows(tmp_path, monkeypatch):
    monkeypatch.setitem(update_leaderboard.PAPER_TABLE2, "hexagonal", {"JW": 100, "TT": 50})
    import io
    f = io.StringIO()

    # Hexagonal's CANONICAL_SHAPE is (8, 4) -- this submission's shape key
    # must match it exactly to land in the "vs. Table II" section alongside
    # the paper rows.
    update_leaderboard.render_graph_challenge_table(
        f, "hexagonal", [("Alice", "baselines/alice.py", {"8x4": {"total": 42, "max": 5}})],
    )

    content = f.getvalue()
    assert "Hex-Lattice" in content
    assert "vs. Table II" in content
    assert "[Alice](baselines/alice.py)" in content
    assert "**42**" in content
    assert "JW [1]" in content
    assert "**100**" in content


def test_render_graph_challenge_table_sorts_by_total_weight_ascending(monkeypatch):
    monkeypatch.setitem(update_leaderboard.PAPER_TABLE2, "triangular", {"JW": 100})
    import io
    f = io.StringIO()

    # Triangular's CANONICAL_SHAPE is (8, 8).
    update_leaderboard.render_graph_challenge_table(
        f, "triangular", [("Better", None, {"8x8": {"total": 10, "max": 2}})],
    )

    content = f.getvalue()
    better_row_pos = content.index("**10**")
    paper_row_pos = content.index("**100**")
    assert better_row_pos < paper_row_pos


def test_render_graph_challenge_table_splits_off_canonical_shape_into_other_section(monkeypatch):
    monkeypatch.setitem(update_leaderboard.PAPER_TABLE2, "triangular", {"JW": 100})
    import io
    f = io.StringIO()

    # (3, 3) is not triangular's CANONICAL_SHAPE (8, 8) -- must land in
    # "Other shapes", not alongside the paper's [1] reference rows.
    update_leaderboard.render_graph_challenge_table(
        f, "triangular", [("Offbeat", None, {"3x3": {"total": 5, "max": 2}})],
    )

    content = f.getvalue()
    assert "Other shapes" in content
    other_pos = content.index("Other shapes")
    offbeat_pos = content.index("Offbeat")
    assert offbeat_pos > other_pos  # Offbeat's row is in the "Other shapes" section, after its header
    assert "JW [1]" in content.split("Other shapes")[0]  # paper row stays in the vs. Table II section


def test_render_graph_challenge_table_omits_other_shapes_section_when_empty(monkeypatch):
    monkeypatch.setitem(update_leaderboard.PAPER_TABLE2, "triangular", {"JW": 100})
    import io
    f = io.StringIO()

    update_leaderboard.render_graph_challenge_table(
        f, "triangular", [("OnCanon", None, {"8x8": {"total": 5, "max": 2}})],
    )

    assert "Other shapes" not in f.getvalue()


# --- is_showcased ---


def test_is_showcased_square_in_range():
    assert update_leaderboard.is_showcased("square", 8, 8) is True


def test_is_showcased_square_off_square_rectangle_not_showcased():
    assert update_leaderboard.is_showcased("square", 8, 12) is False


def test_is_showcased_square_out_of_range_not_showcased():
    assert update_leaderboard.is_showcased("square", 20, 20) is False


def test_is_showcased_graph_type_canonical_shape():
    assert update_leaderboard.is_showcased("hexagonal", 8, 4) is True
    assert update_leaderboard.is_showcased("triangular", 8, 8) is True


def test_is_showcased_graph_type_off_canonical_shape_not_showcased():
    assert update_leaderboard.is_showcased("hexagonal", 15, 15) is False


# --- compute_our_entries: mixed square sizes ---


def test_compute_our_entries_folds_only_showcased_shapes(monkeypatch):
    monkeypatch.setattr(update_leaderboard, "BASELINES", {
        "alice": {
            "encode": None, "order": None, "sizes": [3, (8, 12)], "label": "Alice",
            "module": "baselines.alice", "submitted_at": "2026-01-01T00:00:00+00:00",
        },
    })
    monkeypatch.setattr(update_leaderboard, "load_score_cache", lambda: {})
    monkeypatch.setattr(update_leaderboard, "harness_fingerprint", lambda: "fp")
    monkeypatch.setattr(update_leaderboard, "save_score_cache", lambda cache: None)
    monkeypatch.setattr(update_leaderboard, "hash_file", lambda path: "filefp")
    monkeypatch.setattr(
        update_leaderboard, "evaluate_baseline",
        lambda encode_fn, order_fn, lx, ly: (100 + lx + ly, 1),
    )

    total_entries, max_entries, dated_totals = update_leaderboard.compute_our_entries()

    label, link, totals = total_entries[0]
    # Only the plain-int 3x3 shape is showcased; the 8x12 rectangle was
    # still scored (see the cache assertion below) but doesn't appear here.
    assert totals == {update_leaderboard.SIZES.index(3): 106}


def test_compute_our_entries_still_caches_non_showcased_shapes(monkeypatch, tmp_path):
    import scripts.submission_lib as submission_lib
    monkeypatch.setattr(submission_lib, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(update_leaderboard, "BASELINES", {
        "alice": {
            "encode": None, "order": None, "sizes": [(8, 12)], "label": "Alice",
            "module": "baselines.alice", "submitted_at": "2026-01-01T00:00:00+00:00",
        },
    })
    monkeypatch.setattr(update_leaderboard, "harness_fingerprint", lambda: "fp")
    monkeypatch.setattr(update_leaderboard, "hash_file", lambda path: "filefp")
    monkeypatch.setattr(
        update_leaderboard, "evaluate_baseline",
        lambda encode_fn, order_fn, lx, ly: (999, 1),
    )

    update_leaderboard.compute_our_entries()

    cache = update_leaderboard.load_score_cache()
    assert cache["entries"]["alice"]["scores"]["8x12"] == {"total": 999, "max": 1}
