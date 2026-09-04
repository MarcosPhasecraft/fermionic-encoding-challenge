"""Regenerates LEADERBOARD_ANCILLAS.md (and one
assets/progress_ancillas_square_w<N>.png chart per showcased weight cap,
plus _ancilla_leaderboard_body.md) from scratch -- the ancilla/stabilizer
challenge's own leaderboard, separate from LEADERBOARD.md/LEADERBOARD_GRAPHS.md.

The challenge: pick a maximum Pauli weight cap, then minimize the number
of ancilla qubits (n_qubits - M) needed to reach a genuinely valid
encoding (full checks 0-4 via harness.v2.verify.verify_extended) under
that cap. Lower n_ancillas is better. The cap is the SUBMISSION's choice
("max_weight" in submission.json, defaulting to 3) -- it is not fixed by
the challenge, because the whole interest here is the locality/ancilla
trade-off curve, and pinning one cap would only ever show one point on it.

**Ranking is by ACHIEVED max weight, not claimed cap.** A submission is
listed on every showcased track whose cap it actually satisfies, so an
encoding reaching weight 3 everywhere appears on both the weight-3 and
weight-4 boards (a tighter encoding trivially satisfies a looser cap), and
one reaching weight 4 appears only on the weight-4 board. That's what
makes the boards comparable: the weight-4 board answers "how few ancillas
if you're allowed weight 4", and the honest answer includes every weight-3
construction too.

ANCILLA_SHOWCASED_MAX_WEIGHTS below is the single place deciding which
caps get rendered. A submission may claim ANY positive cap; one outside
this list is still verified, scored, and cached, just not shown --
the same "always scored, shown only if showcased" split is_showcased()
draws for shapes in the ancilla-free challenges.

Square lattice only for now: harness/v2/baselines/dk.py (Derby-Klassen,
arXiv 2003.06939) is the reference baseline on every track, plotted as a
red DOTTED line (not the usual dashed reference-line style -- see
scripts/progress_chart.py's linestyles parameter) since it doubles as both
"the starting point" and "the published result" here, unlike the
ancilla-free challenges' separate JW/paper-best lines. It anchors the
weight-4 board as well as the weight-3 one: no published construction
reaches weight 4 with fewer qubits than DK reaches weight 3 with, so
beating it there is a genuinely open target rather than a formality.
Hexagonal is a valid submission target too (harness.v2.challenges/
harness.graphs already support it) and is fully verified, scored, and
cached exactly like square -- it's just not rendered in a table yet,
because there's no working hexagonal DK reference construction yet (see
NOTES.md). Add a hexagonal section here once that's solved.

Sizes: 3x3..15x15 (SIZES, imported from scripts/update_leaderboard.py) --
the same range as LEADERBOARD.md's own square-lattice sweep, per this
challenge's own design decision to mirror "the other challenge"'s range
for each lattice type rather than invent a new one.

Shares harness/v2/baselines/registry.json (not baselines/registry.json)
and its own .leaderboard_cache_ancillas.json (gated by
harness_v2_fingerprint(), not harness_fingerprint() -- see
scripts/submission_lib.py) -- completely disjoint from the ancilla-free
challenges' own registry/cache/leaderboard files.

Run this after adding or improving an ancilla-challenge baseline, or let
scripts/process_inbox.py do it automatically on acceptance. Never
hand-edit LEADERBOARD_ANCILLAS.md.
"""

import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from scripts.progress_chart import TARGET_SIZE, points_at_size, render_progress_chart
from scripts.submission_lib import (
    ANCILLA_CACHE_PATH,
    ANCILLA_DEFAULT_MAX_WEIGHT,
    hash_file,
    harness_v2_fingerprint,
    load_ancilla_registry,
)
from scripts.update_leaderboard import SIZES, render_ranked_table, source_link

from harness.lattice import build_spec
from harness.v2.evaluate import evaluate_extended
from harness.v2.hamiltonian_terms import hamiltonian_terms
from harness.v2.loading import load_submission_extended

# Which weight caps get a rendered table + chart. Any other cap a
# submission claims is still verified/scored/cached, just not shown --
# add a number here to showcase it, which is the whole change required.
ANCILLA_SHOWCASED_MAX_WEIGHTS = [3, 4]

# The reference baseline anchoring every track's chart, by registry name.
REFERENCE_NAME = "dk"


def _load_ancilla_cache() -> dict:
    if not ANCILLA_CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(ANCILLA_CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_ancilla_cache(cache: dict) -> None:
    ANCILLA_CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")


def evaluate_ancilla_baseline(encode_fn, represent_fn, order_fn, lx, ly, claimed_max_weight) -> tuple:
    """(n_ancillas, achieved_max_weight) for one registered baseline at one
    size. claimed_max_weight is the cap the entry was accepted under -- a
    registered entry has already passed it at registration time, so
    exceeding it here means the baseline's own file changed since (its
    file hash gates the cache, so this really is a fresh result) and the
    registration no longer holds. That's a hard error, not a silent
    downgrade: the registry would otherwise keep advertising a cap the
    code no longer meets.
    """
    spec = build_spec(lx, ly, order_fn)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, encode_fn, terms, represent_fn)
    if not result["passed"]:
        raise RuntimeError(f"{encode_fn} failed verify_extended() at {lx}x{ly}: {result}")
    if result["max_weight"] > claimed_max_weight:
        raise RuntimeError(
            f"{encode_fn} now reaches max_weight {result['max_weight']} at {lx}x{ly}, "
            f"above the cap of {claimed_max_weight} it is registered under"
        )
    return result["n_ancillas"], result["max_weight"]


def scored_with_cache(name, encode_fn, represent_fn, order_fn, sizes, file_fp, cache_entries, claimed_max_weight):
    """({size_index: (n_ancillas, achieved_max_weight)}, any_recomputed) --
    the ancilla challenge's analogue of scripts/update_leaderboard.py's
    scored_with_cache. Only square-lattice sizes within SIZES are folded
    into the returned dict (mirrors is_showcased("square", ...) there);
    every claimed size is still scored and cached regardless.

    A cache entry missing "max_weight" is treated as a miss and recomputed:
    entries written before per-track ranking existed only stored
    n_ancillas, and the achieved weight is exactly what decides which
    tracks an entry belongs on -- guessing it from the claimed cap would
    silently mis-file a tight encoding onto only the loose board.
    """
    cached = cache_entries.get(name)
    if cached is None or cached["fingerprint"] != file_fp:
        cached = {"fingerprint": file_fp, "scores": {}}

    scores = {}
    any_recomputed = False
    for l in sizes:
        key = str(l)
        hit = cached["scores"].get(key)
        if hit is not None and "max_weight" in hit:
            n_ancillas, achieved = hit["n_ancillas"], hit["max_weight"]
        else:
            n_ancillas, achieved = evaluate_ancilla_baseline(
                encode_fn, represent_fn, order_fn, l, l, claimed_max_weight,
            )
            cached["scores"][key] = {"n_ancillas": n_ancillas, "max_weight": achieved}
            any_recomputed = True
        if l in SIZES:
            scores[SIZES.index(l)] = (n_ancillas, achieved)

    cache_entries[name] = cached
    return scores, any_recomputed


def compute_square_entries():
    """[(name, submitted_at, label, link, {size_index: (n_ancillas, achieved)}), ...]
    for every registered ancilla-challenge baseline targeting the square
    lattice. Unfiltered by weight cap -- entries_for_cap() below does that
    per track, so one pass of (potentially expensive) scoring serves every
    track.
    """
    cache = _load_ancilla_cache()
    harness_fp = harness_v2_fingerprint()
    if cache.get("_harness_fingerprint") != harness_fp:
        cache = {"_harness_fingerprint": harness_fp, "entries": {}}
    cache.setdefault("entries", {})

    registry = load_ancilla_registry()

    entries = []
    for name, entry in registry.items():
        if entry.get("graph", "square") != "square":
            continue
        module = entry["module"]
        module_path = REPO_ROOT / f"{module.replace('.', '/')}.py"
        encode_fn, order_fn, represent_fn = load_submission_extended(str(module_path))
        file_fp = hash_file(module_path)
        claimed = entry.get("max_weight", ANCILLA_DEFAULT_MAX_WEIGHT)

        sizes = [s for s in entry["sizes"] if isinstance(s, int)]
        scores, any_recomputed = scored_with_cache(
            name, encode_fn, represent_fn, order_fn, sizes, file_fp, cache["entries"], claimed,
        )
        status = "recomputed" if any_recomputed else "cached, unchanged"
        print(f"{name} ({status}, claims max_weight<={claimed}): {scores}")

        entries.append((name, entry.get("submitted_at"), entry["label"], source_link(module), scores))

    _save_ancilla_cache(cache)
    return entries


def entries_for_cap(all_entries, cap):
    """[(label, link, {size_index: n_ancillas}), ...] for render_ranked_table
    -- every entry, at every size where its ACHIEVED max weight is within
    `cap`. An entry qualifying at no size is dropped entirely (same
    "size-scoped submission simply doesn't appear" handling
    render_ranked_table already does elsewhere).
    """
    out = []
    for name, submitted_at, label, link, scores in all_entries:
        values = {i: n for i, (n, achieved) in scores.items() if achieved <= cap}
        if values:
            out.append((label, link, values))
    return out


def dated_for_cap(all_entries, cap):
    """The same filtering, in scripts/progress_chart.py's dated_totals shape
    ([(name, submitted_at, label, {size_index: value}), ...]). Undated
    entries are skipped -- a chart can't place a point without a date.
    """
    out = []
    for name, submitted_at, label, link, scores in all_entries:
        if submitted_at is None:
            continue
        values = {i: n for i, (n, achieved) in scores.items() if achieved <= cap}
        if values:
            out.append((name, submitted_at, label, values))
    return out


def write_ancilla_progress_chart(dated, cap) -> str:
    """assets/progress_ancillas_square_w<cap>.png -- best n_ancillas over
    time at TARGET_SIZE (15x15, matching LEADERBOARD.md's own target size)
    for one weight track, with the reference baseline's own n_ancillas at
    that size (looked up from `dated`, the same already-computed data every
    other point comes from -- not a fresh separate evaluation) as a red
    DOTTED reference line.
    """
    size_index = SIZES.index(TARGET_SIZE)
    points = points_at_size(dated, size_index)
    reference = next((v.get(size_index) for name, _, _, v in dated if name == REFERENCE_NAME), None)

    assets_dir = REPO_ROOT / "assets"
    assets_dir.mkdir(exist_ok=True)
    out_path = assets_dir / f"progress_ancillas_square_w{cap}.png"
    render_progress_chart(
        points, [("Derby-Klassen", reference)], out_path,
        title=f"Fewest ancillas at max weight ≤ {cap}, {TARGET_SIZE}x{TARGET_SIZE} square lattice",
        ylabel="Ancilla qubits (n_qubits - M)",
        linestyles=[(0, (1, 1.6))],  # dotted, not the usual dashed -- see module docstring
    )
    print(f"wrote {out_path}")
    return f"assets/{out_path.name}?v={hash_file(out_path)[:12]}"


def render_ancilla_leaderboard_body(f, all_entries, chart_paths):
    f.write(
        "One board per maximum-weight cap. A submission picks the cap it "
        "targets (`\"max_weight\"` in `submission.json`, default 3) and is "
        "listed on **every** board whose cap it actually satisfies -- an "
        "encoding reaching weight 3 everywhere appears on both boards below, "
        "since it trivially satisfies the looser cap too. Lower ancilla count "
        "is better.\n\n"
    )
    for cap in ANCILLA_SHOWCASED_MAX_WEIGHTS:
        f.write(f"## Square lattice — fewest ancillas at max weight ≤ {cap}\n\n")
        f.write(f"![Fewest ancillas progress at max weight {cap}]({chart_paths[cap]})\n\n")
        f.write(
            f"Best ancilla count reached so far at {TARGET_SIZE}x{TARGET_SIZE} under a "
            f"max Pauli weight of {cap}, plotted against submission date -- a new point "
            "only appears if it's a strict improvement on the prior record. The dotted "
            "line is Derby-Klassen's own ancilla count at this size (arXiv 2003.06939), "
            "the construction to beat on this board.\n\n"
        )
        render_ranked_table(
            f, f"Ancilla count, max weight ≤ {cap}",
            f"min n_ancillas subject to max_weight ≤ {cap}",
            entries_for_cap(all_entries, cap),
            heading=False,  # this section already has its own heading above
        )


def _rebase_links_for_ancillas_page(text: str) -> str:
    """LEADERBOARD_ANCILLAS.md's own links (harness/v2/baselines/*.py,
    assets/*.png) are repo-root-relative -- correct for that file (sits at
    the repo root) but one level too shallow once embedded into
    ancillas.md, which GitHub Pages serves at /ancillas/, not the site
    root. Same fix, same reasoning as
    scripts/update_leaderboard.py's _rebase_links_for_graphs_page (see its
    own docstring for the full story of how this was discovered) --
    a separate copy, not a shared import, since the link prefixes differ
    (harness/v2/baselines/, not bare baselines/).
    """
    return text.replace("](harness/v2/baselines/", "](../harness/v2/baselines/").replace("](assets/", "](../assets/")


def main():
    print("Computing square-lattice ancilla-challenge entries...")
    all_entries = compute_square_entries()

    print("Writing progress charts...")
    chart_paths = {}
    for cap in ANCILLA_SHOWCASED_MAX_WEIGHTS:
        chart_paths[cap] = write_ancilla_progress_chart(dated_for_cap(all_entries, cap), cap)

    body = io.StringIO()
    render_ancilla_leaderboard_body(body, all_entries, chart_paths)
    body_text = body.getvalue()

    caps = ", ".join(str(c) for c in ANCILLA_SHOWCASED_MAX_WEIGHTS)
    leaderboard_path = REPO_ROOT / "LEADERBOARD_ANCILLAS.md"
    with open(leaderboard_path, "w") as f:
        f.write("# Leaderboard -- ancilla/stabilizer challenge\n\n")
        f.write(
            "Generated by `scripts/update_leaderboard_ancillas.py` — **do not hand-edit "
            "this file**. A separate challenge from `LEADERBOARD.md`/`LEADERBOARD_GRAPHS.md`: "
            "cap the maximum Pauli weight (`D = max(Num, ReHop, ImHop, Inter)`, checked at "
            "every claimed size, not just asserted) and minimize the number of ancilla "
            "qubits (`n_qubits - M`) needed to reach a genuinely valid encoding under that "
            "cap -- every one of the stabilizer checks in `harness/v2/verify.py`, not just "
            "Majorana anticommutation. A submission chooses its own cap; boards are "
            f"rendered for caps {caps} (`ANCILLA_SHOWCASED_MAX_WEIGHTS` in the generating "
            "script), and any other cap is still verified, scored, and cached, just not "
            "shown. See the top-level `README.md`'s \"The ancilla/stabilizer challenge\" "
            "section and `inbox/README.md` for the submission format and how it's told "
            "apart from the other challenges.\n\n"
        )
        f.write(body_text)
    print(f"wrote {leaderboard_path}")

    body_path = REPO_ROOT / "_ancilla_leaderboard_body.md"
    body_path.write_text(_rebase_links_for_ancillas_page(body_text))
    print(f"wrote {body_path}")


if __name__ == "__main__":
    main()
