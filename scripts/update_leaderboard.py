"""Regenerates LEADERBOARD.md (and MEMORY.md) from scratch.

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

Run this after adding or improving a baseline. LEADERBOARD.md is a
generated artifact -- never hand-edit it.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from baselines import BASELINES
from harness.evaluate import evaluate
from harness.lattice import build_spec, hamiltonian

SIZES = list(range(3, 16))
CACHE_PATH = REPO_ROOT / ".leaderboard_cache.json"

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


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _harness_fingerprint() -> str:
    """Hash of every harness/*.py file's content, sorted by filename for
    determinism. Gates the whole cache at once (see module docstring) --
    a baseline's score can depend on any harness utility its encode()/
    order() calls into, not just the scoring functions proper, so there's
    no safe way to track "which files affect which baseline" per-entry.
    """
    hasher = hashlib.sha256()
    for path in sorted((REPO_ROOT / "harness").glob("*.py")):
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _load_cache() -> dict:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")


def scored_with_cache(name, encode_fn, order_fn, sizes, file_fp, cache_entries):
    """(totals_by_size_index, maxes_by_size_index, any_recomputed) for one
    baseline. Reuses cache_entries[name]'s stored scores for whichever
    sizes are already cached under a matching file_fp (that baseline's own
    current fingerprint); anything not cached (a fingerprint mismatch --
    the file changed -- invalidates all of that entry's old scores at
    once, not just the sizes that happen to differ; or a size not seen
    before) is computed via evaluate_baseline and folded into
    cache_entries[name] in place, so the caller can persist it.

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
    for l in sizes:
        i = SIZES.index(l)
        hit = cached["scores"].get(str(l))
        if hit is not None:
            total, max_weight = hit["total"], hit["max"]
        else:
            total, max_weight = evaluate_baseline(encode_fn, order_fn, l, l)
            cached["scores"][str(l)] = {"total": total, "max": max_weight}
            any_recomputed = True
        totals[i] = total
        maxes[i] = max_weight

    cache_entries[name] = cached
    return totals, maxes, any_recomputed


def compute_our_entries():
    """entries[metric] = list of (label, link, {size_index: value}).

    Only computes the sizes each baseline actually claims (registry.json's
    "sizes" list) -- a size-scoped submission just gets fewer entries in
    its dicts, which render_ranked_table already handles as "not ranked
    at this size" rather than needing an explicit blank convention.

    See the module docstring for the caching scheme (per-baseline file
    hash, gated by a whole-harness/ hash) and scored_with_cache for the
    actual per-baseline hit/miss decision.
    """
    cache = _load_cache()
    harness_fp = _harness_fingerprint()
    if cache.get("_harness_fingerprint") != harness_fp:
        # Something in harness/ changed since the cache was written -- every
        # previously cached score is potentially stale, so start clean.
        cache = {"_harness_fingerprint": harness_fp, "entries": {}}
    cache.setdefault("entries", {})

    total_entries, max_entries = [], []
    for name, entry in BASELINES.items():
        encode_fn, order_fn, sizes = entry["encode"], entry["order"], entry["sizes"]
        label, module = entry["label"], entry["module"]
        link = source_link(module)
        file_fp = _hash_file(REPO_ROOT / f"{module.replace('.', '/')}.py")

        totals, maxes, any_recomputed = scored_with_cache(
            name, encode_fn, order_fn, sizes, file_fp, cache["entries"],
        )

        status = "recomputed" if any_recomputed else "cached, unchanged"
        print(f"{name} ({status}): total={totals}")
        print(f"{name} ({status}): max={maxes}")
        total_entries.append((label, link, totals))
        max_entries.append((label, link, maxes))

    _save_cache(cache)
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

    names_and_labels = [(name, entry["label"]) for name, entry in BASELINES.items()]
    write_memory_index(REPO_ROOT / "MEMORY.md", REPO_ROOT / "baselines", names_and_labels)


if __name__ == "__main__":
    main()
