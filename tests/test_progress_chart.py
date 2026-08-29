"""Tests for scripts/progress_chart.py. points_at_size and compute_staircase
are pure functions, tested directly. render_progress_chart is a thin
matplotlib wrapper -- smoke tested (does it write a real PNG) rather than
pixel-tested.
"""

import scripts.progress_chart as progress_chart
from scripts.progress_chart import compute_staircase, points_at_size


# --- points_at_size ---


def test_points_at_size_includes_only_entries_with_that_size():
    dated_totals = [
        ("jw", "2026-01-01T00:00:00+00:00", "JW", {0: 900, 1: 500}),
        ("scoped", "2026-01-02T00:00:00+00:00", "Scoped", {0: 800}),
    ]
    assert points_at_size(dated_totals, 1) == [("2026-01-01T00:00:00+00:00", 500, "JW")]


def test_points_at_size_empty_when_nobody_has_that_size():
    dated_totals = [("jw", "2026-01-01T00:00:00+00:00", "JW", {0: 900})]
    assert points_at_size(dated_totals, 5) == []


# --- compute_staircase ---


def test_staircase_keeps_only_strict_improvements_in_time_order():
    points = [
        ("2026-01-03T00:00:00+00:00", 500, "third"),
        ("2026-01-01T00:00:00+00:00", 900, "first"),
        ("2026-01-02T00:00:00+00:00", 700, "second"),
    ]
    assert compute_staircase(points) == [
        ("2026-01-01T00:00:00+00:00", 900, "first"),
        ("2026-01-02T00:00:00+00:00", 700, "second"),
        ("2026-01-03T00:00:00+00:00", 500, "third"),
    ]


def test_staircase_skips_a_submission_that_is_worse_than_the_running_best():
    points = [
        ("2026-01-01T00:00:00+00:00", 500, "best"),
        ("2026-01-02T00:00:00+00:00", 800, "worse"),
    ]
    assert compute_staircase(points) == [("2026-01-01T00:00:00+00:00", 500, "best")]


def test_staircase_does_not_redraw_on_an_exact_tie():
    # A tie matches the record but doesn't beat it -- the raw scatter still
    # shows the point, but the staircase (the drawn line) doesn't step for it.
    points = [
        ("2026-01-01T00:00:00+00:00", 500, "first"),
        ("2026-01-02T00:00:00+00:00", 500, "tying"),
    ]
    assert compute_staircase(points) == [("2026-01-01T00:00:00+00:00", 500, "first")]


def test_staircase_empty_input_gives_empty_output():
    assert compute_staircase([]) == []


# --- render_progress_chart (smoke test) ---


def test_render_progress_chart_writes_a_real_png(tmp_path):
    points = [
        ("2026-01-01T00:00:00+00:00", 900, "JW"),
        ("2026-01-05T00:00:00+00:00", 700, "Better"),
        ("2026-01-10T00:00:00+00:00", 750, "Worse than best"),
    ]
    reference_lines = [("JW", 900), ("Paper best", 600)]
    out_path = tmp_path / "chart.png"

    progress_chart.render_progress_chart(
        points, reference_lines, out_path, title="Test chart", ylabel="Total Pauli weight",
    )

    assert out_path.is_file()
    assert out_path.stat().st_size > 1000
    assert out_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_progress_chart_handles_a_single_point(tmp_path):
    # No staircase "line" is possible with one point -- must not crash on
    # the single-point edge case (len(stair_times) == 1).
    out_path = tmp_path / "chart.png"
    progress_chart.render_progress_chart(
        [("2026-01-01T00:00:00+00:00", 900, "JW")],
        [("JW", 900)],
        out_path, title="Test chart", ylabel="Total Pauli weight",
    )
    assert out_path.is_file()


def test_render_progress_chart_handles_none_reference_value(tmp_path):
    out_path = tmp_path / "chart.png"
    progress_chart.render_progress_chart(
        [("2026-01-01T00:00:00+00:00", 900, "JW")],
        [("JW", None)],
        out_path, title="Test chart", ylabel="Total Pauli weight",
    )
    assert out_path.is_file()
