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

Run this after adding or improving a baseline. LEADERBOARD.md is a
generated artifact -- never hand-edit it.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from baselines import BASELINES
from harness.evaluate import evaluate
from harness.lattice import build_spec, hamiltonian

SIZES = list(range(3, 16))

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
# here just displays under its registry name. Parity/BK/TT each get two
# entries (row_major, snake) since no single one of the built-in orderings
# is best on both metrics for those three encodings -- see NOTES.md.
PAPER_ROW_FOR = {
    "jw": "JW",
    "parity": "PB (row-major)",
    "parity_snake": "PB (snake)",
    "bk": "BK (row-major)",
    "bk_snake": "BK (snake)",
    "ternary": "TT (row-major)",
    "ternary_snake": "TT (snake)",
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


def compute_our_entries():
    """entries[metric] = list of (label, link, {size_index: value}).

    Only computes the sizes each baseline actually claims (registry.json's
    "sizes" list) -- a size-scoped submission just gets fewer entries in
    its dicts, which render_ranked_table already handles as "not ranked
    at this size" rather than needing an explicit blank convention.
    """
    total_entries, max_entries = [], []
    for name, entry in BASELINES.items():
        encode_fn, order_fn, sizes = entry["encode"], entry["order"], entry["sizes"]
        label = PAPER_ROW_FOR.get(name, name)
        link = source_link(entry["module"])
        totals, maxes = {}, {}
        for l in sizes:
            i = SIZES.index(l)
            total, max_weight = evaluate_baseline(encode_fn, order_fn, l, l)
            totals[i] = total
            maxes[i] = max_weight
        print(f"{name}: total={totals}")
        print(f"{name}: max={maxes}")
        total_entries.append((label, link, totals))
        max_entries.append((label, link, maxes))
    return total_entries, max_entries


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


def render_ranked_table(f, title, formula, entries):
    f.write(f"## {title}\n\n")
    f.write(f"`{formula}`\n\n")

    columns = []
    for i in range(len(SIZES)):
        col = [(values[i], label, link) for label, link, values in entries if i in values]
        col.sort(key=lambda t: t[0])
        columns.append(group_ties(col))

    max_rows = max(len(c) for c in columns)

    header = " | ".join(f"{l}×{l}" for l in SIZES)
    f.write(f"| rank | {header} |\n")
    f.write("|---" * (len(SIZES) + 1) + "|\n")

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


def main():
    our_totals, our_maxes = compute_our_entries()

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
            "via quadratic assignment*, arXiv 2504.21636. Code: "
            "[`github.com/cameton/QCE_QubitAssignment`]"
            "(https://github.com/cameton/QCE_QubitAssignment).\n"
        )

    print(f"wrote {leaderboard_path}")


if __name__ == "__main__":
    main()
