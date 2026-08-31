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
            "module": "baselines.alice", "graph": "hexagonal", "submitted_at": "2026-01-01T00:00:00+00:00",
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
    name, submitted_at, label, link, scores = by_graph["hexagonal"][0]
    assert name == "alice"
    assert submitted_at == "2026-01-01T00:00:00+00:00"
    assert label == "Alice"
    assert scores == {"8x4": {"total": 42, "max": 1}}


# --- graph_sweep_entries / graph_paper_entries / graph_sweep_column_labels ---


def _graph_entry(name="alice", submitted_at="2026-01-01T00:00:00+00:00", label="Alice", link=None, **scores):
    return (name, submitted_at, label, link, scores)


def test_graph_sweep_entries_includes_only_showcased_shapes():
    # triangular's sweep is 3x3..15x15 (Lx=Ly); 8x12 is off-square.
    by_graph = {
        "triangular": [_graph_entry(**{
            "8x8": {"total": 42, "max": 5}, "8x12": {"total": 99, "max": 9},
        })],
    }

    entries = update_leaderboard.graph_sweep_entries(by_graph, "triangular", "total")

    col = update_leaderboard.GRAPH_SWEEP_SIZES["triangular"].index(8)
    assert entries == [("Alice", None, {col: 42})]  # 8x12 (not showcased) is excluded


def test_graph_sweep_entries_column_matches_sweep_index():
    by_graph = {"hexagonal": [_graph_entry(**{"5x5": {"total": 7, "max": 3}})]}

    entries = update_leaderboard.graph_sweep_entries(by_graph, "hexagonal", "total")

    col = update_leaderboard.GRAPH_SWEEP_SIZES["hexagonal"].index(5)
    assert entries == [("Alice", None, {col: 7})]


def test_graph_sweep_entries_omits_entry_with_no_showcased_shape():
    by_graph = {"triangular": [_graph_entry(**{"8x12": {"total": 99, "max": 9}})]}
    assert update_leaderboard.graph_sweep_entries(by_graph, "triangular", "total") == []


def test_graph_paper_entries_triangular_total_has_one_row_per_method():
    # Triangular's CANONICAL_SHAPE (8, 8) is Lx=Ly and inside its sweep.
    entries = update_leaderboard.graph_paper_entries("triangular", "total")
    labels = {label for label, link, cols in entries}
    assert labels == {"JW", "TT"}
    col = update_leaderboard.GRAPH_SWEEP_SIZES["triangular"].index(8)
    for label, link, cols in entries:
        assert link is None
        assert cols == {col: update_leaderboard.PAPER_TABLE2["triangular"][label]}


def test_graph_paper_entries_hexagonal_is_empty():
    # Hexagonal's CANONICAL_SHAPE (8, 4) is not Lx=Ly, so it has no valid
    # column in the Lx=Ly-only sweep -- no paper row, not a misplaced one.
    assert update_leaderboard.graph_paper_entries("hexagonal", "total") == []


def test_graph_paper_entries_max_is_always_empty():
    # Table II reports total weight only -- no fabricated max reference.
    assert update_leaderboard.graph_paper_entries("triangular", "max") == []
    assert update_leaderboard.graph_paper_entries("hexagonal", "max") == []


def test_graph_sweep_column_labels():
    assert update_leaderboard.graph_sweep_column_labels("hexagonal")[0] == "3×3"
    assert update_leaderboard.graph_sweep_column_labels("triangular")[-1] == "8×8"
    assert len(update_leaderboard.graph_sweep_column_labels("triangular")) == 6
    assert len(update_leaderboard.graph_sweep_column_labels("hexagonal")) == 6


# --- graph_other_shapes / render_other_graph_shapes ---


def test_graph_other_shapes_excludes_showcased_shape():
    by_graph = {
        "triangular": [_graph_entry(link="baselines/alice.py", **{
            "8x8": {"total": 7, "max": 3},  # showcased -- excluded
            "8x12": {"total": 99, "max": 9},  # off-square -- included
        })],
    }

    rows = update_leaderboard.graph_other_shapes(by_graph)

    assert rows == [("Tri-Lattice", "8x12", "[Alice](baselines/alice.py)", 99, 9)]


def test_graph_other_shapes_includes_periodic_types_entirely():
    # periodic_hexagonal/periodic_triangular have no sweep at all -- every
    # shape they claim lands here, even an Lx=Ly one.
    by_graph = {"periodic_hexagonal": [_graph_entry(**{"8x4": {"total": 5, "max": 2}})]}

    rows = update_leaderboard.graph_other_shapes(by_graph)

    assert rows == [("Periodic Hex-Lattice", "8x4", "Alice", 5, 2)]


def test_graph_other_shapes_sorted_by_lattice_then_total():
    by_graph = {
        "triangular": [_graph_entry(label="B", **{"8x12": {"total": 50, "max": 5}})],
        "hexagonal": [_graph_entry(label="A", **{"8x12": {"total": 10, "max": 5}})],
    }

    rows = update_leaderboard.graph_other_shapes(by_graph)

    assert [r[0] for r in rows] == ["Hex-Lattice", "Tri-Lattice"]


def test_render_other_graph_shapes_omitted_when_empty():
    import io
    f = io.StringIO()
    update_leaderboard.render_other_graph_shapes(f, [])
    assert f.getvalue() == ""


def test_render_other_graph_shapes_renders_rows():
    import io
    f = io.StringIO()
    update_leaderboard.render_other_graph_shapes(f, [("Tri-Lattice", "8x12", "Alice", 99, 9)])
    content = f.getvalue()
    assert "Other shapes" in content
    assert "Tri-Lattice" in content and "8x12" in content and "**99**" in content


# --- graph_dated_totals: for write_graph_progress_chart ---


def test_graph_dated_totals_only_showcased_shape():
    by_graph = {
        "triangular": [_graph_entry(name="alice", submitted_at="2026-01-02T00:00:00+00:00", **{
            "8x8": {"total": 42, "max": 5}, "8x12": {"total": 1, "max": 1},
        })],
    }

    dated = update_leaderboard.graph_dated_totals(by_graph, "triangular")

    col = update_leaderboard.GRAPH_SWEEP_SIZES["triangular"].index(8)
    assert dated == [("alice", "2026-01-02T00:00:00+00:00", "Alice", {col: 42})]


def test_graph_dated_totals_skips_entries_without_a_timestamp():
    by_graph = {"triangular": [_graph_entry(submitted_at=None, **{"8x8": {"total": 42, "max": 5}})]}
    assert update_leaderboard.graph_dated_totals(by_graph, "triangular") == []


def test_graph_dated_totals_skips_entries_with_no_showcased_shape():
    by_graph = {"triangular": [_graph_entry(**{"8x12": {"total": 1, "max": 1}})]}
    assert update_leaderboard.graph_dated_totals(by_graph, "triangular") == []


# --- render_ranked_table: custom column_labels ---


def test_render_ranked_table_with_custom_column_labels():
    import io
    f = io.StringIO()
    update_leaderboard.render_ranked_table(
        f, "Title", "formula", [("Alice", None, {0: 10, 1: 20})],
        column_labels=["Foo", "Bar"],
    )
    content = f.getvalue()
    assert "| rank | Foo | Bar |" in content
    assert "**10**" in content and "**20**" in content


def test_render_ranked_table_empty_entries_shows_nothing_here_yet():
    # Not a header-only table: a markdown table with a header/separator
    # but zero body rows isn't reliably recognized as a table by every
    # renderer (confirmed against GitHub Pages' kramdown, which fell back
    # to showing the raw "| rank | ... |" text as a literal paragraph).
    import io
    f = io.StringIO()
    update_leaderboard.render_ranked_table(f, "Title", "formula", [], column_labels=["Foo"])
    content = f.getvalue()
    assert "Nothing here yet" in content
    assert "| rank |" not in content


# --- _rebase_links_for_graphs_page ---


def test_rebase_links_for_graphs_page_rewrites_baseline_links():
    text = "**42**<br>[JW](baselines/jw_triangular.py)"
    assert update_leaderboard._rebase_links_for_graphs_page(text) == \
        "**42**<br>[JW](../baselines/jw_triangular.py)"


def test_rebase_links_for_graphs_page_rewrites_chart_embed():
    text = "![Total Pauli weight progress, Tri-Lattice](assets/progress_triangular_weight.png?v=abc123)"
    assert update_leaderboard._rebase_links_for_graphs_page(text) == \
        "![Total Pauli weight progress, Tri-Lattice](../assets/progress_triangular_weight.png?v=abc123)"


def test_rebase_links_for_graphs_page_leaves_other_links_alone():
    # A same-page anchor and an absolute external URL should pass through
    # unchanged -- only the two repo-root-relative link kinds get rewritten.
    text = "JW [[1]](#references)\n[1] ... [arXiv 2504.21636](https://arxiv.org/abs/2504.21636)"
    assert update_leaderboard._rebase_links_for_graphs_page(text) == text


# --- is_showcased ---


def test_is_showcased_square_in_range():
    assert update_leaderboard.is_showcased("square", 8, 8) is True


def test_is_showcased_square_off_square_rectangle_not_showcased():
    assert update_leaderboard.is_showcased("square", 8, 12) is False


def test_is_showcased_square_out_of_range_not_showcased():
    assert update_leaderboard.is_showcased("square", 20, 20) is False


def test_is_showcased_triangular_in_sweep():
    assert update_leaderboard.is_showcased("triangular", 3, 3) is True
    assert update_leaderboard.is_showcased("triangular", 8, 8) is True


def test_is_showcased_hexagonal_in_sweep():
    assert update_leaderboard.is_showcased("hexagonal", 3, 3) is True
    assert update_leaderboard.is_showcased("hexagonal", 8, 8) is True


def test_is_showcased_hexagonal_canonical_shape_not_showcased():
    # (8, 4) is hexagonal's own paper-comparison shape, but Lx != Ly, so
    # it has no column in the Lx=Ly-only sweep -- not showcased.
    assert update_leaderboard.is_showcased("hexagonal", 8, 4) is False


def test_is_showcased_triangular_out_of_sweep_range_not_showcased():
    assert update_leaderboard.is_showcased("triangular", 9, 9) is False


def test_is_showcased_hexagonal_out_of_sweep_range_not_showcased():
    assert update_leaderboard.is_showcased("hexagonal", 9, 9) is False


def test_is_showcased_periodic_types_never_showcased():
    assert update_leaderboard.is_showcased("periodic_hexagonal", 8, 4) is False
    assert update_leaderboard.is_showcased("periodic_triangular", 8, 8) is False


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
