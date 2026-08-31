"""Regenerates LEADERBOARD.md (and MEMORY.md, and assets/progress_total_weight.png)
from scratch.

Layout: one table per metric (total, max), columns fixed at 3x3..15x15,
but ROWS ARE RANK POSITIONS, not fixed encodings -- row 1 is whoever
actually wins at that size, row 2 the runner-up, etc. A column can (and
does, at larger sizes) have a different winner than its neighbor, which a
fixed-row-per-encoding table can't represent; this can. It also means a
size-scoped submission (one that only claims some sizes) just doesn't
appear in the ranking for sizes it has no value for -- no blank-cell
bookkeeping needed, the column for that size simply has fewer rows filled.

For every baseline registered in baselines.BASELINES, evaluates it under
that baseline's own declared order(Lx, Ly) -> perm (row_major if it
declares none -- see harness.lattice.build_spec). The harness does not
search orderings on a submission's behalf: each entry here reflects one
specific, submission-chosen labelling, not a best-of-several search
(infeasible beyond the smallest sizes anyway; see NOTES.md for the one
size, 3x3, where a separate exhaustive search over all 9! orderings
confirmed ternary tree's row_major/snake numbers are within reach of the
true global optimum for at least that size). Where an encoding's own best
total and best max come from genuinely different orderings (true for
parity, BK, and ternary tree -- NOTES.md has the breakdown), it's
registered twice, once per ordering, rather than one leaderboard entry
silently mixing numbers from two different runs.

Paper reference rows (arXiv 2504.21636's own published Table I) are
static data pulled from the paper's LaTeX source (not its prose, not its
released code -- see NOTES.md for why that distinction matters),
hardcoded below since they don't come from running any code here.

Caches each baseline's per-size (total, max) in .leaderboard_cache.json
(gitignored -- local build state, not repo content), keyed by a hash of
that baseline's own source file. A baseline whose file hasn't changed
since last time reuses its cached score instead of rerunning verify()+
score() from scratch -- matters once a submission's own encode() does
something expensive (a local search, an ensemble of restarts; adding one
new baseline used to mean re-running every existing one too). A hash of
the whole harness/ directory gates the entire cache: since a baseline's
score can depend on harness utilities it calls into (e.g.
harness.constructors.from_linear_encoding), not just its own file, ANY
change anywhere in harness/ invalidates every cached score at once, never
just the ones that "look" affected -- this cannot go stale silently. The
harness's own scoring logic isn't expected to change going forward, but
the cache is built to not assume that.

Also writes MEMORY.md: an index of any baseline that shipped with an
optional memory/ folder (notes on what was tried, carried in by
scripts/process_inbox.py -- see inbox/README.md), deliberately kept
separate from the score tables above rather than cluttering their cells.

Also writes assets/progress_total_weight.png, embedded at the top of
LEADERBOARD.md before the tables: total Pauli weight at a single fixed
size (TARGET_SIZE, see scripts/progress_chart.py) plotted against each
submission's date, so the record-over-time line is unambiguous -- a
submission can win at one lattice size and lose at another, so a line
spanning multiple sizes would either have to scalarize across them (ruled
out project-wide) or visibly go up and down. The full per-size picture is
still the two tables below it, unabridged.

Also writes _leaderboard_body.md: the chart+tables+references shared
between LEADERBOARD.md and the GitHub Pages site (index.md), so the
site's shorter blurb doesn't require hand-duplicating the actual scores.
Excluded from Jekyll's own page generation in _config.yml.

Run this after adding or improving a baseline. LEADERBOARD.md is a
generated artifact -- never hand-edit it.
"""

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

# Imported as scripts.submission_lib (not bare `submission_lib`), matching
# scripts/process_inbox.py's convention -- see that file's comment for why
# the distinction matters (module identity, not just resolvability). Tests
# that need to redirect the cache file monkeypatch
# scripts.submission_lib.CACHE_PATH directly, not a copy here.
from scripts.progress_chart import TARGET_SIZE, points_at_size, render_progress_chart
from scripts.submission_lib import (
    harness_fingerprint, hash_file, load_score_cache, save_score_cache, shape_key,
)

from baselines import BASELINES
from harness.evaluate import evaluate
from harness.graphs import CANONICAL_SHAPE, build_spec as build_graph_spec
from harness.lattice import build_spec, hamiltonian

SIZES = list(range(3, 16))


# Range of Lx=Ly sizes shown in each graph type's own sweep table/chart --
# both capped at 8x8, deliberately smaller than SIZES' own 3x3..15x15
# (arXiv 2504.21636 Table I's square-lattice sweep): a submission's own
# encode() may do real optimization work, and 8x8 keeps the largest case
# in either sweep comfortably fast to verify/score regardless of what a
# submission does, without needing to reason about it case by case.
# Deliberately the SAME numeric cap for both graph types, not a per-type
# qubit-count-matched one: hexagonal's mode count (M = 2*Lx*Ly, two sites
# per unit cell) grows twice as fast as triangular's (M = Lx*Ly, same as
# the square lattice), so hexagonal's top qubit count at 8x8 (128) ends up
# double triangular's (64) -- accepted for how much simpler "both sweep
# 3x3..8x8" is to state and explain than two different numbers would be.
# periodic_hexagonal/periodic_triangular have no sweep defined -- not
# shown in any table yet (still submittable, still scored and cached,
# same as any other is_showcased()-excluded shape -- see NOTES.md).
GRAPH_SWEEP_SIZES = {
    "triangular": list(range(3, 9)),
    "hexagonal": list(range(3, 9)),
}


def is_showcased(graph: str, lx: int, ly: int) -> bool:
    """Whether a (graph, Lx, Ly) shape appears in a rendered table/chart, as
    opposed to just being verified, scored, and cached. The single place
    this decision is made -- everything downstream just calls this, so
    showcasing a new shape/graph type later is a one-line edit here, not a
    rendering rewrite. Today: square shapes showcase iff they're an exact
    L x L within SIZES (arXiv 2504.21636 Table I's own 3x3..15x15 sweep);
    triangular/hexagonal showcase iff they're an exact L x L within that
    graph type's own GRAPH_SWEEP_SIZES; periodic_hexagonal/
    periodic_triangular never showcase (no sweep defined for them).
    Anything else -- an off-square rectangle, an out-of-range size, any
    periodic-type shape -- is still verified/scored/cached (see
    scripts/submission_lib.py's validate_mixed_sizes/validate_shapes and
    scripts/process_inbox.py), just not shown.
    """
    if graph == "square":
        return lx == ly and lx in SIZES
    sweep = GRAPH_SWEEP_SIZES.get(graph)
    return sweep is not None and lx == ly and lx in sweep

# arXiv 2504.21636 Table I, verbatim from the LaTeX source (main.tex, the
# \begin{table*}...\end{table*} block labeled tab:lattice), for L=3..15.
PAPER_TOTAL = {
    "BK": [304, 635, 1107, 1712, 2473, 3331, 4467, 5741, 7127, 8850, 10438, 12595, 14522],
    "JW": [237, 512, 909, 1460, 2189, 3104, 4277, 5632, 7389, 9320, 11609, 14364, 17601],
    "PB": [301, 645, 1147, 1815, 2683, 3775, 5155, 6751, 8729, 10987, 13657, 17449, 20505],
    "TT": [313, 628, 1080, 1676, 2375, 3237, 4303, 5473, 6799, 8342, 9853, 11844, 13942],
}
PAPER_MAX = {
    "BK": [5, 7, 9, 9, 11, 11, 12, 13, 13, 13, 14, 15, 15],
    "JW": [4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 18, 20],
    "PB": [5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 17, 18, 20],
    "TT": [5, 5, 7, 7, 8, 8, 9, 9, 9, 10, 10, 10, 11],
}

# arXiv 2504.21636 Table II, verbatim from the LaTeX source (main.tex, the
# \begin{table}...\end{table} block labeled tab:graphs), for the
# ancilla-free Jordan-Wigner and Ternary Tree transformations on four
# 64-mode graphs, under the same D = Num + ReHop + ImHop + Inter metric
# already used for the square-lattice challenge -- see harness.graphs and
# NOTES.md for the reproducibility caveat: the paper doesn't state the exact
# (Lx, Ly)/shape used, so our own construction won't reproduce these numbers
# exactly, only land in the same ballpark. The other three graphs in the
# same table (Random 3-Regular, Margulis-Gabber-Galil, Chordal Cycle) are
# specific instances from the paper's own generation, not reproducible
# without their released code -- deliberately out of scope here.
PAPER_TABLE2 = {
    "hexagonal": {"JW": 7564, "TT": 5489},
    "triangular": {"JW": 2384, "TT": 2478},
    "periodic_hexagonal": {"JW": 8584, "TT": 4794},
    "periodic_triangular": {"JW": 2704, "TT": 2356},
}
GRAPH_LABELS = {
    "hexagonal": "Hex-Lattice",
    "triangular": "Tri-Lattice",
    "periodic_hexagonal": "Periodic Hex-Lattice",
    "periodic_triangular": "Periodic Tri-Lattice",
}


def source_link(module: str) -> str:
    """Repo-relative path to the module declaring a baseline, for a markdown
    link straight to the actual submission. Built from the registry's own
    "module" string rather than introspecting encode_fn -- a *_snake.py
    wrapper imports its encode() from elsewhere, so the function object's
    own source file would point at the wrong file.
    """
    return module.replace(".", "/") + ".py"


def evaluate_baseline(encode_fn, order_fn, lx, ly):
    spec = build_spec(lx, ly, order_fn)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode_fn, terms)
    if not result["passed"]:
        raise RuntimeError(f"{encode_fn} failed verify() at {lx}x{ly}: {result}")
    return result["total_weight"], result["max_weight"]


def scored_with_cache(name, encode_fn, order_fn, sizes, file_fp, cache_entries):
    """(totals_by_size_index, maxes_by_size_index, any_recomputed) for one
    baseline. Reuses cache_entries[name]'s stored scores for whichever
    sizes are already cached under a matching file_fp (that baseline's own
    current fingerprint); anything not cached (a fingerprint mismatch --
    the file changed -- invalidates all of that entry's old scores at
    once, not just the sizes that happen to differ; or a size not seen
    before) is computed via evaluate_baseline and folded into
    cache_entries[name] in place, so the caller can persist it.

    `sizes` entries are either a plain int (Lx=Ly=that int, the original
    and still by far the common case) or an explicit (Lx, Ly) pair (a
    submission-claimed rectangle -- see submission_lib.validate_mixed_sizes).
    Every entry is verified/scored/cached the same way regardless; only
    entries where is_showcased("square", lx, ly) holds get folded into the
    returned totals/maxes dicts (keyed by SIZES.index(lx), same as always)
    -- everything else is still computed and cached, just not returned for
    LEADERBOARD.md's ranked tables to see. A plain-int entry always uses
    the cache key str(l) (unchanged from before this existed, so the 17
    baselines registered before rectangles were possible keep their exact
    cache hits); an explicit pair uses shape_key(lx, ly) instead.

    Pulled out of compute_our_entries() specifically so this -- the actual
    caching decision -- is testable with fake encode_fn/order_fn and an
    arbitrary fingerprint string, without needing real baseline files or
    the real harness/ directory.
    """
    cached = cache_entries.get(name)
    if cached is None or cached["fingerprint"] != file_fp:
        cached = {"fingerprint": file_fp, "scores": {}}

    totals, maxes = {}, {}
    any_recomputed = False
    for s in sizes:
        lx, ly = (s, s) if isinstance(s, int) else s
        key = str(s) if isinstance(s, int) else shape_key(lx, ly)
        hit = cached["scores"].get(key)
        if hit is not None:
            total, max_weight = hit["total"], hit["max"]
        else:
            total, max_weight = evaluate_baseline(encode_fn, order_fn, lx, ly)
            cached["scores"][key] = {"total": total, "max": max_weight}
            any_recomputed = True
        if is_showcased("square", lx, ly):
            i = SIZES.index(lx)
            totals[i] = total
            maxes[i] = max_weight

    cache_entries[name] = cached
    return totals, maxes, any_recomputed


def evaluate_graph_baseline(encode_fn, order_fn, graph, lx, ly):
    """(total_weight, max_weight) for one graph-challenge baseline -- the
    graph-challenge analogue of evaluate_baseline, same D = Num + ReHop +
    ImHop + Inter metric (model="full") as the square-lattice challenge,
    matching arXiv 2504.21636 Table II.
    """
    spec = build_graph_spec(graph, lx, ly, order_fn)
    terms = hamiltonian(spec, model="full")
    result = evaluate(spec, encode_fn, terms)
    if not result["passed"]:
        raise RuntimeError(f"{encode_fn} failed verify() at {graph} {lx}x{ly}: {result}")
    return result["total_weight"], result["max_weight"]


def scored_with_cache_graph(name, encode_fn, order_fn, graph, sizes, file_fp, cache_entries):
    """(scores_by_shape, any_recomputed) for one graph-challenge baseline --
    scores_by_shape: {"LxxLy": {"total": int, "max": int}}. sizes is a
    list of (lx, ly) pairs -- unlike the square-lattice challenge, mode
    count alone doesn't pin down the graph here (see harness.graphs.CANONICAL_SHAPE),
    so every shape a submission claims is scored and cached independently;
    graph_sweep_entries/graph_other_shapes decide which of them is_showcased().
    Deliberately separate from scored_with_cache rather than a shared
    abstraction: that one is keyed by SIZES.index(l) (a fixed 3..15 column
    position, specific to the square-lattice table's layout), which doesn't
    apply here. Shares the same underlying cache file/entries shape
    (cache_entries[name] = {"fingerprint", "scores"}), so both challenges
    live in one .leaderboard_cache.json without a second cache file.
    """
    cached = cache_entries.get(name)
    if cached is None or cached["fingerprint"] != file_fp:
        cached = {"fingerprint": file_fp, "scores": {}}

    scores = {}
    any_recomputed = False
    for lx, ly in sizes:
        key = shape_key(lx, ly)
        hit = cached["scores"].get(key)
        if hit is not None:
            total, max_weight = hit["total"], hit["max"]
        else:
            total, max_weight = evaluate_graph_baseline(encode_fn, order_fn, graph, lx, ly)
            cached["scores"][key] = {"total": total, "max": max_weight}
            any_recomputed = True
        scores[key] = {"total": total, "max": max_weight}

    cache_entries[name] = cached
    return scores, any_recomputed


def compute_graph_entries():
    """{graph_type: [(name, submitted_at, label, link, {shape: {"total", "max"}}), ...]} --
    the graph-challenge analogue of compute_our_entries(), filtered to
    exactly the registry entries compute_our_entries() itself excludes
    (entry.get("graph", "square") != "square"), so every registered
    baseline is scored by exactly one of the two functions, never both.
    Shares .leaderboard_cache.json with compute_our_entries() (same file,
    same "_harness_fingerprint" gate, disjoint "entries" keys by name).

    Carries name/submitted_at (unlike compute_our_entries()'s total_entries/
    max_entries, which drop them) because every consumer here needs them:
    graph_sweep_entries/graph_other_shapes don't, but graph_dated_totals
    (the progress-chart data) does, and there's no reason to compute the
    same scores twice just to get a differently-shaped tuple.
    """
    cache = load_score_cache()
    harness_fp = harness_fingerprint()
    if cache.get("_harness_fingerprint") != harness_fp:
        cache = {"_harness_fingerprint": harness_fp, "entries": {}}
    cache.setdefault("entries", {})

    by_graph = {}
    for name, entry in BASELINES.items():
        graph = entry.get("graph", "square")
        if graph == "square":
            continue
        encode_fn, order_fn, sizes = entry["encode"], entry["order"], entry["sizes"]
        label, module = entry["label"], entry["module"]
        link = source_link(module)
        file_fp = hash_file(REPO_ROOT / f"{module.replace('.', '/')}.py")

        scores, any_recomputed = scored_with_cache_graph(
            name, encode_fn, order_fn, graph, sizes, file_fp, cache["entries"],
        )
        status = "recomputed" if any_recomputed else "cached, unchanged"
        print(f"{name} ({status}, graph={graph}): {scores}")
        by_graph.setdefault(graph, []).append((name, entry["submitted_at"], label, link, scores))

    save_score_cache(cache)
    return by_graph


def _shape_of(key: str) -> tuple[int, int]:
    lx, ly = (int(v) for v in key.split("x"))
    return lx, ly


def graph_sweep_entries(by_graph, graph, metric):
    """[(label, link, {size_index: value}), ...] for render_ranked_table --
    the graph-challenge analogue of compute_our_entries()'s total_entries/
    max_entries, for ONE graph type's own Lx=Ly sweep (GRAPH_SWEEP_SIZES),
    column-indexed by GRAPH_SWEEP_SIZES[graph].index(L) exactly like the
    square-lattice table is indexed by SIZES.index(L). Only showcased
    shapes contribute -- an entry with none (every shape it claims for
    this graph type falls outside the sweep) is simply omitted, same
    "size-scoped submission" handling render_ranked_table already does.
    """
    sweep = GRAPH_SWEEP_SIZES[graph]
    entries = []
    for name, submitted_at, label, link, scores in by_graph.get(graph, []):
        values = {}
        for key, s in scores.items():
            lx, ly = _shape_of(key)
            if is_showcased(graph, lx, ly):
                values[sweep.index(lx)] = s[metric]
        if values:
            entries.append((label, link, values))
    return entries


def graph_paper_entries(graph, metric):
    """[(method, None, {size_index: value}), ...] for render_ranked_table --
    arXiv 2504.21636 Table II's own JW/TT numbers for one graph type,
    placed at the column matching that type's CANONICAL_SHAPE -- only if
    that shape is itself an Lx=Ly point inside the type's own sweep. True
    for triangular's (8, 8) (Lx=Ly, and 8 is within GRAPH_SWEEP_SIZES);
    NOT true for hexagonal's (8, 4) (Lx != Ly, since hexagonal has two
    sites per unit cell) -- there is no valid column for it in an
    Lx=Ly-only sweep, so hexagonal gets no paper reference row here at
    all, rather than a misplaced one. Table II only reports total weight,
    not a per-graph max -- see PAPER_TABLE2 -- so this returns [] for
    "max" regardless of graph.
    """
    if metric != "total":
        return []
    canon_lx, canon_ly = CANONICAL_SHAPE[graph]
    if canon_lx != canon_ly or not is_showcased(graph, canon_lx, canon_ly):
        return []
    col = GRAPH_SWEEP_SIZES[graph].index(canon_lx)
    # Bare method name, no "[1]" suffix -- render_cell already appends
    # " [[1]](#references)" itself for any link=None entry (see
    # paper_entries()'s identical convention for the square-lattice
    # challenge); adding it here too would show up doubled.
    return [(method, None, {col: weight}) for method, weight in PAPER_TABLE2[graph].items()]


def graph_sweep_column_labels(graph):
    return [f"{l}×{l}" for l in GRAPH_SWEEP_SIZES[graph]]


def graph_other_shapes(by_graph):
    """[(lattice_label, shape, name, total, max), ...] -- every claimed
    shape that isn't showcased in its graph type's own sweep table, across
    all graph types (including periodic_hexagonal/periodic_triangular,
    which have no sweep at all and so land here entirely) in one flat
    list. Sorted by lattice label then total weight, so same-lattice rows
    stay grouped without needing a sub-header per lattice.
    """
    rows = []
    for graph, entries in by_graph.items():
        for name, submitted_at, label, link, scores in entries:
            display_name = f"[{label}]({link})" if link else label
            for key, s in scores.items():
                if not is_showcased(graph, *_shape_of(key)):
                    rows.append((GRAPH_LABELS[graph], key, display_name, s["total"], s["max"]))
    rows.sort(key=lambda r: (r[0], r[3]))
    return rows


def render_other_graph_shapes(f, rows):
    """Omitted entirely (not even a header) if empty -- no submission has
    claimed a non-showcased shape yet, so there's nothing to show.
    """
    if not rows:
        return
    f.write("## Other shapes\n\n")
    f.write(
        "Claimed shapes outside the sweep tables below -- an off-square "
        "rectangle, an out-of-range size, or any shape at all for the "
        "periodic variants (not swept yet) -- still verified, scored, and "
        "cached, just not ranked above.\n\n"
    )
    f.write("| lattice | shape | label | total weight | max weight |\n")
    f.write("|---|---|---|---|---|\n")
    for lattice, shape, name, total, max_weight in rows:
        f.write(f"| {lattice} | {shape} | {name} | **{total}** | {max_weight} |\n")
    f.write("\n")


def graph_dated_totals(by_graph, graph):
    """[(name, submitted_at, label, {size_index: total_weight}), ...] for
    one graph type's own Lx=Ly sweep, in scripts/progress_chart.py's
    dated_totals shape -- reused as-is by write_graph_progress_chart via
    points_at_size(dated_totals, size_index), same mechanism as the
    square-lattice chart. Skips an entry with no submitted_at (shouldn't
    happen -- process_inbox.py and submit_baseline.py both always stamp
    one -- but a chart can't place an undated point regardless).
    """
    sweep = GRAPH_SWEEP_SIZES[graph]
    dated = []
    for name, submitted_at, label, link, scores in by_graph.get(graph, []):
        if submitted_at is None:
            continue
        values = {}
        for key, s in scores.items():
            lx, ly = _shape_of(key)
            if is_showcased(graph, lx, ly):
                values[sweep.index(lx)] = s["total"]
        if values:
            dated.append((name, submitted_at, label, values))
    return dated


def write_graph_progress_chart(dated_tri_totals) -> str:
    """Writes assets/progress_triangular_weight.png and returns its
    repo-relative path. Tri-Lattice only (not Hex-Lattice too): its own
    paper-comparison shape, (8, 8), is Lx=Ly and so lands naturally inside
    the Lx=Ly-only sweep this chart (and the tables) show -- unlike
    Hex-Lattice's (8, 4), which doesn't (hexagonal has two sites per unit
    cell, so its M=64 point is never a square Lx=Ly shape). Tri-Lattice is
    the one graph type where "our own JW" and "the paper's own number" can
    be placed at the same, real column -- exactly mirroring the
    square-lattice chart's own JW-vs-Table-I comparison. Reference lines:
    the registered "jw_triangular" baseline's own score at the target size
    (mirrors write_progress_chart's "jw" lookup) and the better of Table
    II's two triangular numbers (JW, TT).
    """
    graph = "triangular"
    target_size = CANONICAL_SHAPE[graph][0]  # 8 -- the paper's own M=64 point, an Lx=Ly shape here
    size_index = GRAPH_SWEEP_SIZES[graph].index(target_size)
    points = points_at_size(dated_tri_totals, size_index)

    jw_value = next(
        (totals.get(size_index) for name, _, _, totals in dated_tri_totals if name == "jw_triangular"), None,
    )
    paper_best = min(PAPER_TABLE2[graph].values())

    assets_dir = REPO_ROOT / "assets"
    assets_dir.mkdir(exist_ok=True)
    out_path = assets_dir / "progress_triangular_weight.png"
    render_progress_chart(
        points,
        [("JW", jw_value), ("Best of Table II [1]", paper_best)],
        out_path,
        title=f"Total Pauli weight, Tri-Lattice ({target_size}x{target_size})",
        ylabel="Total Pauli weight",
    )
    print(f"wrote {out_path}")
    return f"assets/{out_path.name}?v={hash_file(out_path)[:12]}"


def compute_our_entries():
    """(total_entries, max_entries, dated_totals).

    total_entries/max_entries: list of (label, link, {size_index: value}),
    for render_ranked_table. Only computes the sizes each baseline actually
    claims (registry.json's "sizes" list) -- a size-scoped submission just
    gets fewer entries in its dicts, which render_ranked_table already
    handles as "not ranked at this size" rather than needing an explicit
    blank convention. A baseline may also claim off-square rectangles
    (see submission_lib.validate_mixed_sizes) -- those are still verified,
    scored, and cached by scored_with_cache, just excluded here (and hence
    from every rendered table/chart) via is_showcased.

    dated_totals: list of (name, submitted_at, label, {size_index: value}) --
    the same total-weight scores as total_entries, but keeping the
    registry name and submission date, which the ranked table doesn't need
    but scripts/progress_chart.py's points_at_size does.

    See the module docstring for the caching scheme (per-baseline file
    hash, gated by a whole-harness/ hash) and scored_with_cache for the
    actual per-baseline hit/miss decision.
    """
    cache = load_score_cache()
    harness_fp = harness_fingerprint()
    if cache.get("_harness_fingerprint") != harness_fp:
        # Something in harness/ changed since the cache was written -- every
        # previously cached score is potentially stale, so start clean.
        cache = {"_harness_fingerprint": harness_fp, "entries": {}}
    cache.setdefault("entries", {})

    total_entries, max_entries, dated_totals = [], [], []
    for name, entry in BASELINES.items():
        if entry.get("graph", "square") != "square":
            # Not this leaderboard's/chart's concern -- see the
            # graph-challenge rendering path instead. Keeps this table and
            # progress_total_weight.png's timeline structurally unable to
            # see a non-square entry, not just carefully avoided.
            continue
        encode_fn, order_fn, sizes = entry["encode"], entry["order"], entry["sizes"]
        label, module = entry["label"], entry["module"]
        link = source_link(module)
        file_fp = hash_file(REPO_ROOT / f"{module.replace('.', '/')}.py")

        totals, maxes, any_recomputed = scored_with_cache(
            name, encode_fn, order_fn, sizes, file_fp, cache["entries"],
        )

        status = "recomputed" if any_recomputed else "cached, unchanged"
        print(f"{name} ({status}): total={totals}")
        print(f"{name} ({status}): max={maxes}")
        total_entries.append((label, link, totals))
        max_entries.append((label, link, maxes))
        dated_totals.append((name, entry["submitted_at"], label, totals))

    save_score_cache(cache)
    return total_entries, max_entries, dated_totals


def paper_entries(paper_dict):
    return [(key, None, dict(enumerate(values))) for key, values in paper_dict.items()]


def render_cell(value, contenders):
    # <br>, not a raw newline -- markdown table cells are single-line, so a
    # literal line break needs the HTML tag to render as two lines on GitHub.
    # contenders is a list since exact ties share one cell/rank (see
    # NOTES.md's "9x9 TT tie" finding) -- one name per line below the value.
    names = [f"[{label}]({link})" if link else f"{label} [[1]](#references)" for label, link in contenders]
    return f"**{value}**<br>" + "<br>".join(names)


def group_ties(col):
    """col: sorted [(value, label, link), ...] -> [(value, [(label, link), ...]), ...],
    merging consecutive equal values into one group -- an exact tie is one
    rank, not several, and shows every contender in that one cell.
    """
    groups = []
    for value, label, link in col:
        if groups and groups[-1][0] == value:
            groups[-1][1].append((label, link))
        else:
            groups.append((value, [(label, link)]))
    return groups


def collect_memory_entries(baselines_dir: Path, names_and_labels):
    """(name, label, [filenames]) for every (name, label) whose
    baselines_dir/<name>.memory/ directory exists and actually has files
    in it, in the order given. Baselines without one are simply omitted --
    no "no notes" filler. Takes baselines_dir as a parameter (rather than
    reading the module-level BASELINES_DIR-equivalent directly) so this is
    testable against a temp directory standing in for baselines/.
    """
    entries = []
    for name, label in names_and_labels:
        memory_dir = baselines_dir / f"{name}.memory"
        if memory_dir.is_dir():
            filenames = sorted(p.name for p in memory_dir.iterdir() if p.is_file())
            if filenames:
                entries.append((name, label, filenames))
    return entries


def write_memory_index(path: Path, baselines_dir: Path, names_and_labels) -> None:
    """Generates MEMORY.md -- shared, ECDSA-style notes on what was tried,
    carried in from an accepted submission's optional memory/ folder (see
    scripts/process_inbox.py and inbox/README.md). Explicitly not
    verified: this is prose a submitter chose to include, not code the
    harness runs, so it's leads for the next person, not proven fact --
    same caveat ecdsa.fail's own shared memory notes carry. Deliberately
    kept out of LEADERBOARD.md's table cells, which stay focused on scores.
    """
    entries = collect_memory_entries(baselines_dir, names_and_labels)
    with open(path, "w") as f:
        f.write("# Lessons from past attempts\n\n")
        f.write(
            "Generated by `scripts/update_leaderboard.py` — **do not hand-edit this "
            "file**. Notes submitters chose to include alongside their encoding — "
            "not verified independently. Treat these as leads, not proven fact: "
            "verify a claim yourself before relying on it (the same caveat "
            "ecdsa.fail's own shared memory notes carry).\n\n"
        )
        if not entries:
            f.write("Nothing here yet.\n")
        for name, label, filenames in entries:
            f.write(f"## {label} — `{name}`\n\n")
            for filename in filenames:
                f.write(f"- [{filename}](baselines/{name}.memory/{filename})\n")
            f.write("\n")
    print(f"wrote {path}")


def render_ranked_table(f, title, formula, entries, column_labels=None):
    """Renders one rank-based table: rows are rank positions (row 1 is
    whoever wins at that column, not a fixed encoding -- see the module
    docstring), columns are whatever column_labels names. Defaults to the
    square-lattice challenge's own 3x3..15x15 header (column i = SIZES[i]);
    the graph challenge passes its own four lattice-type labels instead,
    reusing this same function rather than a second copy of the rank/tie
    logic -- entries is already shaped identically either way:
    [(label, link, {column_index: value}), ...].
    """
    if column_labels is None:
        column_labels = [f"{l}×{l}" for l in SIZES]

    f.write(f"## {title}\n\n")
    f.write(f"`{formula}`\n\n")

    columns = []
    for i in range(len(column_labels)):
        col = [(values[i], label, link) for label, link, values in entries if i in values]
        col.sort(key=lambda t: t[0])
        columns.append(group_ties(col))

    max_rows = max((len(c) for c in columns), default=0)

    if max_rows == 0:
        # A header/separator row with no body row isn't reliably
        # recognized as a table by every markdown renderer -- GitHub
        # Pages' kramdown, in particular, falls back to showing the raw
        # "| rank | ... |" text as a literal paragraph instead of a table
        # (confirmed against the live site). Nothing to rank yet, so skip
        # the table structure entirely rather than emit broken markup.
        f.write("Nothing here yet.\n\n")
        return

    header = " | ".join(column_labels)
    f.write(f"| rank | {header} |\n")
    f.write("|---" * (len(column_labels) + 1) + "|\n")

    for rank in range(max_rows):
        cells = []
        for col in columns:
            if rank < len(col):
                value, contenders = col[rank]
                cells.append(render_cell(value, contenders))
            else:
                cells.append("")
        f.write(f"| {rank + 1} | " + " | ".join(cells) + " |\n")

    f.write("\n")


def write_progress_chart(dated_totals) -> str:
    """Writes assets/progress_total_weight.png and returns its repo-relative
    path for embedding in LEADERBOARD.md. Fixed to total Pauli weight at
    TARGET_SIZE (see scripts/progress_chart.py's module docstring for why
    just one size, not an aggregate across sizes). Reference lines: our own
    live-computed JW score at that size, and the best of the paper's four
    published Table I rows at that size.
    """
    size_index = SIZES.index(TARGET_SIZE)
    points = points_at_size(dated_totals, size_index)

    jw_value = next(
        (totals.get(size_index) for name, _, _, totals in dated_totals if name == "jw"), None,
    )
    paper_best = min(values[size_index] for values in PAPER_TOTAL.values())

    assets_dir = REPO_ROOT / "assets"
    assets_dir.mkdir(exist_ok=True)
    out_path = assets_dir / "progress_total_weight.png"
    render_progress_chart(
        points,
        [("JW", jw_value), ("Best of Table I [1]", paper_best)],
        out_path,
        title=f"Total Pauli weight, {TARGET_SIZE}x{TARGET_SIZE} lattice",
        ylabel="Total Pauli weight",
    )
    print(f"wrote {out_path}")
    # A cache-busting query string, not just the bare path -- the filename
    # never changes between regenerations, and some browsers (Safari in
    # particular, more aggressively than Chrome) can keep serving a stale
    # cached copy under that same URL even after a hard refresh or a new
    # window. Tying it to the file's own content hash means the URL only
    # ever changes when the image actually does.
    return f"assets/{out_path.name}?v={hash_file(out_path)[:12]}"


def render_leaderboard_body(f, chart_path, our_totals, our_maxes):
    """Writes the chart + both ranked tables + references -- everything
    shared between LEADERBOARD.md (for GitHub's file browser, prefixed
    there with a longer methodology paragraph) and the Pages site's
    index.md (prefixed there with a short blurb instead). Kept as one
    function, called once per output, so the actual scores/tables are
    never hand-duplicated between the two.
    """
    f.write(
        f"![Total Pauli weight progress at {TARGET_SIZE}x{TARGET_SIZE}]({chart_path})\n\n"
        f"Best total Pauli weight reached so far at "
        f"{TARGET_SIZE}x{TARGET_SIZE}, plotted against submission date -- "
        "a new point only appears if it's a strict improvement on the prior "
        "record. Dashed lines are the JW "
        "reference and the best of arXiv 2504.21636's own published Table I "
        "rows at this size. Fixed to one size because a submission can win "
        "at one lattice size and lose at another -- see the full tables "
        "below for the complete picture across 3x3..15x15.\n\n"
    )
    render_ranked_table(
        f, "Total Pauli weight", "D = Num + ReHop + ImHop + Inter",
        our_totals + paper_entries(PAPER_TOTAL),
    )
    render_ranked_table(
        f, "Maximum Pauli weight", "D = max(Num, ReHop, ImHop, Inter)",
        our_maxes + paper_entries(PAPER_MAX),
    )
    f.write(
        "## References\n\n"
        "[1] Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings "
        "via quadratic assignment*, [arXiv 2504.21636]"
        "(https://arxiv.org/abs/2504.21636). Code: "
        "[`github.com/cameton/QCE_QubitAssignment`]"
        "(https://github.com/cameton/QCE_QubitAssignment).\n"
    )


def main():
    our_totals, our_maxes, dated_totals = compute_our_entries()
    chart_path = write_progress_chart(dated_totals)

    body = io.StringIO()
    render_leaderboard_body(body, chart_path, our_totals, our_maxes)
    body_text = body.getvalue()

    leaderboard_path = REPO_ROOT / "LEADERBOARD.md"
    with open(leaderboard_path, "w") as f:
        f.write("# Leaderboard -- square grids, 3x3 to 15x15\n\n")
        f.write(
            "Generated by `scripts/update_leaderboard.py` — **do not hand-edit this "
            "file**. Rows are rank positions, not fixed encodings: row 1 is whoever "
            "actually has the best score at that size, row 2 the runner-up, and so "
            "on, so a column can have a different winner than its neighbor. Each "
            "entry reflects that submission's own declared mode ordering "
            "(`order(Lx, Ly) -> perm`, defaulting to `row_major` if it declares none) "
            "-- the harness doesn't search orderings on a submission's behalf. Where "
            "an encoding's own best total and best max weight come from genuinely "
            "different orderings, it appears twice (e.g. `BK (row-major)` / "
            "`BK (snake)`) rather than one entry silently mixing numbers from two "
            "different runs. An exact tie between two or more entries shares one "
            "rank and one cell -- value on top, every tied contender listed "
            "below it. `[1]` rows are arXiv 2504.21636's own published "
            "Table I, included for direct comparison.\n\n"
            "Lower is better, on both tables.\n\n"
        )
        f.write(body_text)

    print(f"wrote {leaderboard_path}")

    # A separate fragment, not just LEADERBOARD.md re-included wholesale --
    # the Pages site wants the chart/tables/references without the long
    # methodology paragraph above (that's what LEADERBOARD.md itself is
    # for; the site instead gets a short blurb, written directly in
    # index.md, linking back to the repo for the rest). Excluded from
    # Jekyll's own page generation via _config.yml so it doesn't also show
    # up as its own bare page.
    body_path = REPO_ROOT / "_leaderboard_body.md"
    body_path.write_text(body_text)
    print(f"wrote {body_path}")

    names_and_labels = [
        (name, entry["label"]) for name, entry in BASELINES.items()
        if entry.get("graph", "square") == "square"
    ]
    write_memory_index(REPO_ROOT / "MEMORY.md", REPO_ROOT / "baselines", names_and_labels)

    write_graph_challenge_leaderboard()


def _rebase_links_for_graphs_page(text: str) -> str:
    """graph_body_text's own baselines/*.py links and assets/*.png chart
    embed are repo-root-relative (correct for LEADERBOARD_GRAPHS.md, a
    file sitting at the repo root right next to those directories) --
    but _graph_leaderboard_body.md is included into graphs.md, which
    GitHub Pages serves one path segment deeper, at /graphs/, not at the
    site root. The exact same relative link that's correct from the repo
    root resolves one level too deep from there (confirmed against the
    live site: baselines/jw_triangular.py and assets/progress_*.png both
    404'd on the /graphs/ page while working fine from LEADERBOARD_GRAPHS.md
    and from the site's own root page, index.md -- the square-lattice
    challenge never hits this because both of ITS consumers, LEADERBOARD.md
    and index.md, sit at the same depth). Only these two link kinds ever
    appear with this prefix in generated graph-challenge content --
    render_cell's [label](link) from source_link(), and the chart's
    ![alt](chart_path) -- so a plain string substitution is exact, not a
    heuristic.
    """
    return text.replace("](baselines/", "](../baselines/").replace("](assets/", "](../assets/")


def write_graph_challenge_leaderboard():
    """Writes LEADERBOARD_GRAPHS.md (and _graph_leaderboard_body.md, the
    Pages-site fragment) -- the beyond-square-lattices challenge, entirely
    separate from LEADERBOARD.md above: different graphs (hexagonal,
    triangular, and their periodic variants, not square grids), same
    D = Num + ReHop + ImHop + Inter metric. Nothing here reads or writes
    LEADERBOARD.md, _leaderboard_body.md, MEMORY.md, or
    assets/progress_total_weight.png.

    One pair of ranked tables (total, max) per swept graph type
    (Tri-Lattice, Hex-Lattice -- periodic variants aren't swept, see
    GRAPH_SWEEP_SIZES), columns = that type's own Lx=Ly sizes, mirroring
    LEADERBOARD.md's own layout exactly (row 1 is whoever wins at that
    size, not a fixed encoding, same tie-handling). Tri-Lattice's own
    paper-comparison shape (8, 8) is Lx=Ly, so its tables carry a real
    "[1]"-linked Table II reference column; Hex-Lattice's (8, 4) isn't
    Lx=Ly, so its tables have no paper reference at all -- not a
    misplaced one (see graph_paper_entries). A claimed shape outside its
    graph type's sweep (an off-square rectangle, an out-of-range size, or
    any periodic-type shape) still gets verified, scored, and cached,
    just folded into one shared "Other shapes" table below instead of the
    sweep tables.
    """
    by_graph = compute_graph_entries()
    chart_path = write_graph_progress_chart(graph_dated_totals(by_graph, "triangular"))

    graph_body = io.StringIO()
    graph_body.write(
        f"![Total Pauli weight progress, Tri-Lattice]({chart_path})\n\n"
        "Best total Pauli weight reached so far on the Tri-Lattice at "
        "8x8 (arXiv 2504.21636's own Table II comparison point), plotted "
        "against submission date -- shown for Tri-Lattice only since it's "
        "the one graph type whose paper-comparison shape is itself Lx=Ly "
        "(Hex-Lattice's is not -- see NOTES.md). Dashed lines are the JW "
        "reference and the better of Table II's own two Tri-Lattice "
        "numbers (JW, TT). See the full tables below for the complete "
        "picture across both graph types and every swept size.\n\n"
    )
    for graph in ("triangular", "hexagonal"):
        label = GRAPH_LABELS[graph]
        column_labels = graph_sweep_column_labels(graph)
        render_ranked_table(
            graph_body, f"{label} — Total Pauli weight", "D = Num + ReHop + ImHop + Inter",
            graph_sweep_entries(by_graph, graph, "total") + graph_paper_entries(graph, "total"),
            column_labels=column_labels,
        )
        render_ranked_table(
            graph_body, f"{label} — Maximum Pauli weight", "D = max(Num, ReHop, ImHop, Inter)",
            graph_sweep_entries(by_graph, graph, "max") + graph_paper_entries(graph, "max"),
            column_labels=column_labels,
        )
    render_other_graph_shapes(graph_body, graph_other_shapes(by_graph))
    graph_body.write(
        "## References\n\n"
        "[1] Chiew, Ibrahim, Safro, Strelchuk, *Optimal fermion-qubit mappings "
        "via quadratic assignment*, [arXiv 2504.21636]"
        "(https://arxiv.org/abs/2504.21636), Table II.\n"
    )
    graph_body_text = graph_body.getvalue()

    graphs_path = REPO_ROOT / "LEADERBOARD_GRAPHS.md"
    with open(graphs_path, "w") as f:
        f.write("# Leaderboard -- beyond square lattices\n\n")
        f.write(
            "Generated by `scripts/update_leaderboard.py` — **do not hand-edit this "
            "file**. A separate challenge from the square-lattice one in "
            "`LEADERBOARD.md`: the target graphs are 2D lattice types from arXiv "
            "2504.21636's Table II (Tri-Lattice/triangular and Hex-Lattice/"
            "hexagonal, not square grids), scored under the exact same "
            "`D = Num + ReHop + ImHop + Inter` metric as the square-lattice "
            "challenge. Same layout as `LEADERBOARD.md` too: rows are rank "
            "positions, not fixed encodings, and columns are lattice sizes "
            "`Lx = Ly` (a submission may claim other shapes too -- see "
            "\"Other shapes\" below) -- swept `3x3..8x8` for both Tri-Lattice and "
            "Hex-Lattice (`GRAPH_SWEEP_SIZES` in `scripts/update_leaderboard.py`; "
            "the same numeric cap for both, deliberately, even though Hex-Lattice "
            "has two sites per unit cell and so reaches double the qubit count of "
            "Tri-Lattice at the same `L` -- 128 vs. 64 at `8x8`). Periodic "
            "Hex-Lattice and Periodic Tri-Lattice are valid targets too "
            "(`\"graph\": \"periodic_hexagonal\"/\"periodic_triangular\"` in "
            "`submission.json`) but aren't swept/shown in a table yet -- any shape "
            "claimed for them is still verified, scored, and cached, and shows up "
            "in \"Other shapes\" below. Same non-negotiable rule as the "
            "square-lattice challenge: the harness does not search orderings on a "
            "submission's behalf; each graph type ships one canonical default "
            "ordering (see `harness/graphs.py`), overridable by a submission's own "
            "declared `order(Lx, Ly) -> perm` exactly as today.\n\n"
            "A submission declares which shape(s) it targets as explicit `Lx x Ly` "
            "pairs (e.g. `\"sizes\": \"3x3,8x8\"` in `submission.json` -- see "
            "`inbox/README.md`), not a single size: for these lattice types, mode "
            "count `M` alone does **not** determine the graph -- different `(Lx, "
            "Ly)` splits at the same `M` are structurally different graphs. `[1]` "
            "rows are arXiv 2504.21636's own published Table II, shown at "
            "Tri-Lattice's 8x8 column (its own paper-comparison shape, which "
            "happens to be `Lx = Ly`); Hex-Lattice's paper-comparison shape is "
            "`(8, 4)`, not `Lx = Ly`, so it has no column in these Lx=Ly-only "
            "sweep tables and gets no `[1]` row here -- our own `jw_hexagonal`/"
            "`tt_hexagonal` baselines are still real, ranked entries, just without "
            "a paper number to line up against. Our own construction of any "
            "canonical shape won't reproduce the paper's numbers exactly (the "
            "paper doesn't state the exact shape/ordering it used), only land in "
            "the same ballpark; see NOTES.md.\n\n"
            "Lower is better, on every table.\n\n"
        )
        f.write(graph_body_text)
    print(f"wrote {graphs_path}")

    graph_body_path = REPO_ROOT / "_graph_leaderboard_body.md"
    graph_body_path.write_text(_rebase_links_for_graphs_page(graph_body_text))
    print(f"wrote {graph_body_path}")


if __name__ == "__main__":
    main()
