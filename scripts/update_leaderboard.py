"""Regenerates LEADERBOARD.md from scratch.

Layout: one table per metric (total, max), columns fixed at 3x3..15x15,
but ROWS ARE RANK POSITIONS, not fixed encodings -- row 1 is whoever
actually wins at that size, row 2 the runner-up, etc. A column can (and
does, at larger sizes) have a different winner than its neighbor, which a
fixed-row-per-encoding table can't represent; this can. It also means a
size-scoped submission (one that only claims some sizes) just doesn't
appear in the ranking for sizes it has no value for -- no blank-cell
bookkeeping needed, the column for that size simply has fewer rows filled.

For every baseline registered in baselines.BASELINES, evaluates it under
the harness's three built-in orderings (row_major, snake, diagonal) and
takes the best of those three per metric, per size -- NOT an exhaustive
search over all orderings (infeasible beyond the smallest sizes; see
NOTES.md for the one size, 3x3, where a separate exhaustive search
additionally confirms these are the true global optimum).

Paper reference rows (arXiv 2504.21636's own published Table I) are
static data pulled from the paper's LaTeX source (not its prose, not its
released code -- see NOTES.md for why that distinction matters),
hardcoded below since they don't come from running any code here.

Run this after adding or improving a baseline. LEADERBOARD.md is a
generated artifact -- never hand-edit it.
"""

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from baselines import BASELINES
from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle

SIZES = list(range(3, 16))
ORDERINGS = ("row_major", "snake", "diagonal")

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
# Which of our baselines.BASELINES names correspond to which paper row --
# used to display our own row under the paper's own notation (JW, PB, not
# the lowercase registry key). Anything registered under a name not listed
# here just displays under its registry name.
PAPER_ROW_FOR = {"jw": "JW", "parity": "PB"}


def source_link(encode_fn) -> str:
    """Repo-relative path to the file defining encode_fn, for a markdown
    link straight to the actual submission.
    """
    path = Path(inspect.getsourcefile(encode_fn)).resolve()
    return path.relative_to(REPO_ROOT).as_posix()


def best_over_orderings(encode_fn, lx, ly):
    best_total = None
    best_max = None
    for ordering in ORDERINGS:
        spec = rectangle(lx, ly, ordering=ordering)
        terms = hamiltonian(spec, model="full")
        result = evaluate(spec, encode_fn, terms)
        if not result["passed"]:
            raise RuntimeError(f"{encode_fn} failed verify() at {lx}x{ly}/{ordering}: {result}")
        if best_total is None or result["total_weight"] < best_total:
            best_total = result["total_weight"]
        if best_max is None or result["max_weight"] < best_max:
            best_max = result["max_weight"]
    return best_total, best_max


def compute_our_entries():
    """entries[metric] = list of (label, link, {size_index: value}).

    Only computes the sizes each baseline actually claims (registry.json's
    "sizes" list) -- a size-scoped submission just gets fewer entries in
    its dicts, which render_ranked_table already handles as "not ranked
    at this size" rather than needing an explicit blank convention.
    """
    total_entries, max_entries = [], []
    for name, entry in BASELINES.items():
        encode_fn, sizes = entry["encode"], entry["sizes"]
        label = PAPER_ROW_FOR.get(name, name)
        link = source_link(encode_fn)
        totals, maxes = {}, {}
        for l in sizes:
            i = SIZES.index(l)
            total, max_weight = best_over_orderings(encode_fn, l, l)
            totals[i] = total
            maxes[i] = max_weight
        print(f"{name}: total={totals}")
        print(f"{name}: max={maxes}")
        total_entries.append((label, link, totals))
        max_entries.append((label, link, maxes))
    return total_entries, max_entries


def paper_entries(paper_dict):
    return [(key, None, dict(enumerate(values))) for key, values in paper_dict.items()]


def render_cell(label, link, value):
    if link:
        return f"[{label}]({link}) — {value}"
    return f"{label} [[1]](#references) — {value}"


def render_ranked_table(f, title, formula, entries):
    f.write(f"## {title}\n\n")
    f.write(f"`{formula}`\n\n")

    columns = []
    for i in range(len(SIZES)):
        col = [(values[i], label, link) for label, link, values in entries if i in values]
        col.sort(key=lambda t: t[0])
        columns.append(col)

    max_rows = max(len(c) for c in columns)

    header = " | ".join(f"{l}×{l}" for l in SIZES)
    f.write(f"| rank | {header} |\n")
    f.write("|---" * (len(SIZES) + 1) + "|\n")

    for rank in range(max_rows):
        cells = []
        for col in columns:
            if rank < len(col):
                value, label, link = col[rank]
                cells.append(render_cell(label, link, value))
            else:
                cells.append("")
        f.write(f"| {rank + 1} | " + " | ".join(cells) + " |\n")

    f.write("\n")


def main():
    our_totals, our_maxes = compute_our_entries()

    leaderboard_path = REPO_ROOT / "LEADERBOARD.md"
    with open(leaderboard_path, "w") as f:
        f.write("# Leaderboard -- square grids, 3x3 to 15x15\n\n")
        f.write(
            "Generated by `scripts/update_leaderboard.py` — **do not hand-edit this "
            "file**. Rows are rank positions, not fixed encodings: row 1 is whoever "
            "actually has the best score at that size, row 2 the runner-up, and so "
            "on, so a column can have a different winner than its neighbor. Our own "
            "entries are the best of the harness's three built-in orderings "
            "(`row_major`, `snake`, `diagonal`), not an exhaustive search over every "
            "ordering (infeasible beyond the smallest sizes; see NOTES.md for the "
            "one size, 3×3, where a separate exhaustive search additionally confirms "
            "these are the true global optimum). `[1]` rows are arXiv 2504.21636's "
            "own published Table I, included for direct comparison.\n\n"
            "Lower is better, on both tables.\n\n"
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
            "via quadratic assignment*, arXiv 2504.21636.\n"
        )

    print(f"wrote {leaderboard_path}")


if __name__ == "__main__":
    main()
