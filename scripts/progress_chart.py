"""Generates assets/progress_total_weight.png -- a record-over-time chart
embedded at the top of LEADERBOARD.md, before the score tables.

Fixed to ONE (metric, size) slice -- total Pauli weight at 15x15, the
paper's own Table I ceiling -- rather than trying to plot a single "best
overall" line across all sizes. A submission can win at one size and lose
at another, so a line spanning sizes would either have to scalarize across
them (ruled out project-wide -- see CLAUDE.md's "never collapse metrics
into one scalar") or would visibly go up and down in a way that
misrepresents "record" as a concept. Restricted to one size, "best so far"
is a genuine, unambiguous staircase. Other sizes aren't plotted yet -- a
size selector is a possible future addition, deliberately deferred to keep
this first cut simple.

Two dashed reference lines, mirroring ecdsa.fail's own progress chart
(their "Spacetime" tab pairs a record line with a dashed external
reference, e.g. "Litinski, the previous best published circuit
construction"): our own live-computed JW baseline (the obvious reference;
it reproduces arXiv 2504.21636's own published JW row, since JW is
deterministic) and the best of the paper's four published Table I rows at
this size (their own optimized result -- the external record to beat).
"""

import datetime as _dt

TARGET_SIZE = 15


def points_at_size(dated_totals, size_index):
    """dated_totals: [(name, submitted_at, label, {size_index: value}), ...]
    -> [(submitted_at, value, label), ...] for every entry that actually
    has a value at size_index -- a size-scoped submission (e.g. one that
    only claims 7x7) just doesn't appear, no blank-cell handling needed.
    """
    return [
        (submitted_at, totals[size_index], label)
        for name, submitted_at, label, totals in dated_totals
        if size_index in totals
    ]


def compute_staircase(points):
    """points: [(submitted_at_iso, value, label), ...], any order -> the
    subsequence (sorted by time) of points that set a NEW all-time-low
    value, each paired with the running minimum at that moment. A tie
    with the existing record doesn't redraw the line (the record isn't
    beaten, just matched) -- it still shows up in the raw scatter, just
    not as a new step.
    """
    ordered = sorted(points, key=lambda p: p[0])
    staircase = []
    best = None
    for submitted_at, value, label in ordered:
        if best is None or value < best:
            best = value
            staircase.append((submitted_at, value, label))
    return staircase


ACCENT = "#3A5CE0"
REFERENCE_COLORS = ["#E4572E", "#2A9D8F"]  # coral, teal -- distinct from ACCENT and each other


def render_progress_chart(points, reference_lines, out_path, title, ylabel):
    """points: [(submitted_at_iso, value, label), ...] -- every submission
    scored at the target size (only compute_staircase's winners are drawn;
    the rest exist here just to anchor the line's right edge to the latest
    submission date). reference_lines: [(label, value_or_None), ...] --
    horizontal dashed lines (JW, paper-best); a None value is skipped.
    Writes a PNG to out_path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    all_times = sorted(_dt.datetime.fromisoformat(t) for t, _, _ in points)

    staircase = compute_staircase(points)
    stair_times = [_dt.datetime.fromisoformat(t) for t, _, _ in staircase]
    stair_values = [v for _, v, _ in staircase]
    # Extend the flat line to the most recent submission's timestamp, even
    # when that submission didn't itself set a new record -- otherwise the
    # line looks like it stops short of "now" instead of holding steady.
    # Anchored to the data's own latest timestamp (not wall-clock "now") so
    # re-running this with no new submissions reproduces the same image.
    if all_times and stair_times and all_times[-1] > stair_times[-1]:
        stair_times.append(all_times[-1])
        stair_values.append(stair_values[-1])

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "text.color": "#2b2b2b",
        "axes.labelcolor": "#2b2b2b",
        "xtick.color": "#5a5a5a",
        "ytick.color": "#5a5a5a",
    })

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if len(stair_times) > 1:
        # Shade the descent from each past record down to today's best --
        # a quick visual read of "how much progress has been made", not
        # just a dashboard sparkline.
        ax.fill_between(
            stair_times, stair_values, stair_values[-1],
            step="post", color=ACCENT, alpha=0.10, zorder=1, linewidth=0,
        )
        ax.step(
            stair_times, stair_values, where="post",
            color=ACCENT, linewidth=2.5, zorder=3, solid_capstyle="round",
        )
    if stair_times:
        ax.scatter(
            stair_times, stair_values, color=ACCENT, s=70, zorder=4,
            edgecolor="white", linewidth=1.5,
        )
        # Annotate only the opening and current-best values -- with many
        # closely-spaced records (expected as submissions accumulate), a
        # label per point overlaps its neighbors; the two numbers that
        # matter most for an at-a-glance read are "started at" and "now
        # at", and the shape of the staircase already carries the rest.
        endpoints = {0, len(staircase) - 1}
        for i, (t, v, _) in enumerate(staircase):
            if i not in endpoints:
                continue
            ax.annotate(
                f"{v:,}", (_dt.datetime.fromisoformat(t), v),
                textcoords="offset points", xytext=(0, 10), ha="center",
                fontsize=9, color=ACCENT, fontweight="bold",
            )

    # Reference lines are labelled inline, right at the line's own height
    # (not via a legend) -- a legend's automatic placement has no way to
    # know where the dashed lines actually sit and can end up drawn right
    # on top of one.
    trans = ax.get_yaxis_transform()
    for (label, value), color in zip(reference_lines, REFERENCE_COLORS):
        if value is None:
            continue
        ax.axhline(value, color=color, linestyle=(0, (6, 4)), linewidth=1.5, zorder=2)
        ax.text(
            1.015, value, label, transform=trans, color=color, fontsize=9,
            va="center", ha="left", clip_on=False,
        )

    ax.set_title(title, fontsize=15, fontweight="bold", loc="left", pad=14)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.grid(axis="y", color="#e9ecef", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d0d3d8")

    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    # Fixed margins rather than tight_layout: the reference-line labels are
    # drawn outside the axes proper (axes-fraction x > 1), which
    # tight_layout doesn't account for -- a right margin is reserved
    # explicitly instead so they're never cut off at the figure edge.
    fig.subplots_adjust(left=0.10, right=0.78, top=0.88, bottom=0.10)
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)
