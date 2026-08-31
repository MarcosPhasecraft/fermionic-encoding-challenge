"""Regenerates LEADERBOARD_ANCILLAS.md (and assets/progress_ancillas_square.png,
_ancilla_leaderboard_body.md) from scratch -- the ancilla/stabilizer
challenge's own leaderboard, separate from LEADERBOARD.md/LEADERBOARD_GRAPHS.md.

The challenge: fix the maximum Pauli weight at 3 (ANCILLA_MAX_WEIGHT in
scripts/submission_lib.py) and minimize the number of ancilla qubits
(n_qubits - M) needed to reach a genuinely valid encoding (full checks 0-4
via harness.v2.verify.verify_extended) at that weight. Lower n_ancillas is
better; a submission that can't back max_weight <= 3 at a claimed size is
rejected outright by scripts/process_inbox.py, so every registered entry
here is guaranteed eligible already -- this script only ranks, it doesn't
filter.

Square lattice only for now: harness/v2/baselines/dk.py (Derby-Klassen,
arXiv 2003.06939) is the reference baseline, plotted as a red DOTTED line
(not the usual dashed reference-line style -- see
scripts/progress_chart.py's linestyles parameter) since it doubles as both
"the starting point" and "the published result" here, unlike the
ancilla-free challenges' separate JW/paper-best lines. Hexagonal is a
valid submission target too (harness.v2.challenges/harness.graphs already
support it) and is fully verified, scored, and cached exactly like square
-- it's just not rendered in a table yet, because there's no working
hexagonal DK reference construction yet (see NOTES.md for why: the
paper's column-alternating edge-orientation rule doesn't translate
cleanly into this repo's brick-wall coordinate convention, and unlike the
square lattice, every hexagonal face needs a genuinely valid stabilizer --
there's no free choice to paper over the gap with). Add a
GRAPH_SWEEP_SIZES-style "hexagonal" table here once that's solved.

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
    ANCILLA_BASELINES_DIR,
    ANCILLA_CACHE_PATH,
    ANCILLA_MAX_WEIGHT,
    hash_file,
    harness_v2_fingerprint,
    load_ancilla_registry,
)
from scripts.update_leaderboard import SIZES, render_ranked_table, source_link

from harness.lattice import build_spec
from harness.v2.evaluate import evaluate_extended
from harness.v2.hamiltonian_terms import hamiltonian_terms
from harness.v2.loading import load_submission_extended


def _load_ancilla_cache() -> dict:
    if not ANCILLA_CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(ANCILLA_CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save_ancilla_cache(cache: dict) -> None:
    ANCILLA_CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")


def evaluate_ancilla_baseline(encode_fn, represent_fn, order_fn, lx, ly) -> tuple:
    spec = build_spec(lx, ly, order_fn)
    terms = hamiltonian_terms(spec, model="full")
    result = evaluate_extended(spec, encode_fn, terms, represent_fn)
    if not result["passed"]:
        raise RuntimeError(f"{encode_fn} failed verify_extended() at {lx}x{ly}: {result}")
    if result["max_weight"] > ANCILLA_MAX_WEIGHT:
        raise RuntimeError(f"{encode_fn} exceeds max_weight {ANCILLA_MAX_WEIGHT} at {lx}x{ly}: {result['max_weight']}")
    return result["n_ancillas"], result["max_weight"]


def scored_with_cache(name, encode_fn, represent_fn, order_fn, sizes, file_fp, cache_entries):
    """(ancillas_by_size_index, any_recomputed) -- the ancilla challenge's
    analogue of scripts/update_leaderboard.py's scored_with_cache. Only
    square-lattice sizes within SIZES are folded into the returned dict
    (mirrors is_showcased("square", ...) there); a hexagonal-targeted
    entry's sizes are still scored/cached below (via the caller's own
    per-shape loop) but never reach this square-only ranking function.
    """
    cached = cache_entries.get(name)
    if cached is None or cached["fingerprint"] != file_fp:
        cached = {"fingerprint": file_fp, "scores": {}}

    ancillas = {}
    any_recomputed = False
    for l in sizes:
        key = str(l)
        hit = cached["scores"].get(key)
        if hit is not None:
            n_ancillas = hit["n_ancillas"]
        else:
            n_ancillas, _ = evaluate_ancilla_baseline(encode_fn, represent_fn, order_fn, l, l)
            cached["scores"][key] = {"n_ancillas": n_ancillas}
            any_recomputed = True
        if l in SIZES:
            ancillas[SIZES.index(l)] = n_ancillas

    cache_entries[name] = cached
    return ancillas, any_recomputed


def compute_square_entries():
    """[(name, submitted_at, label, link, {size_index: n_ancillas}), ...]
    for every registered ancilla-challenge baseline targeting the square
    lattice -- dk (this repo's own reference, always included, exactly
    like jw/parity are unconditionally present for the ancilla-free
    leaderboard) plus anything accepted via scripts/process_inbox.py.
    """
    cache = _load_ancilla_cache()
    harness_fp = harness_v2_fingerprint()
    if cache.get("_harness_fingerprint") != harness_fp:
        cache = {"_harness_fingerprint": harness_fp, "entries": {}}
    cache.setdefault("entries", {})

    registry = load_ancilla_registry()

    entries = []
    dated = []
    for name, entry in registry.items():
        if entry.get("graph", "square") != "square":
            continue
        module = entry["module"]
        module_path = REPO_ROOT / f"{module.replace('.', '/')}.py"
        encode_fn, order_fn, represent_fn = load_submission_extended(str(module_path))
        file_fp = hash_file(module_path)

        sizes = [s for s in entry["sizes"] if isinstance(s, int)]
        ancillas, any_recomputed = scored_with_cache(name, encode_fn, represent_fn, order_fn, sizes, file_fp, cache["entries"])
        status = "recomputed" if any_recomputed else "cached, unchanged"
        print(f"{name} ({status}): {ancillas}")

        link = source_link(module)
        entries.append((entry["label"], link, ancillas))
        if entry.get("submitted_at") is not None:
            dated.append((name, entry["submitted_at"], entry["label"], ancillas))

    _save_ancilla_cache(cache)
    return entries, dated


def write_ancilla_progress_chart(dated) -> str:
    """assets/progress_ancillas_square.png -- best n_ancillas over time at
    TARGET_SIZE (15x15, matching LEADERBOARD.md's own target size), with
    Derby-Klassen's own n_ancillas at that size (looked up from `dated`,
    the same already-computed data every other entry's point comes from --
    not a fresh separate evaluation) as a red DOTTED reference line (see
    this module's own docstring for why dotted, not the usual dashed style).
    """
    size_index = SIZES.index(TARGET_SIZE)
    points = points_at_size(dated, size_index)
    dk_value = next((ancillas.get(size_index) for name, _, _, ancillas in dated if name == "dk"), None)

    assets_dir = REPO_ROOT / "assets"
    assets_dir.mkdir(exist_ok=True)
    out_path = assets_dir / "progress_ancillas_square.png"
    render_progress_chart(
        points, [("Derby-Klassen", dk_value)], out_path,
        title=f"Fewest ancillas at max weight ≤ {ANCILLA_MAX_WEIGHT}, {TARGET_SIZE}x{TARGET_SIZE} square lattice",
        ylabel="Ancilla qubits (n_qubits - M)",
        linestyles=[(0, (1, 1.6))],  # dotted, not the usual dashed -- see module docstring
    )
    print(f"wrote {out_path}")
    return f"assets/{out_path.name}?v={hash_file(out_path)[:12]}"


def render_ancilla_leaderboard_body(f, chart_path, square_entries):
    f.write(f"![Fewest ancillas progress, square lattice]({chart_path})\n\n")
    f.write(
        f"Best ancilla count reached so far at {TARGET_SIZE}x{TARGET_SIZE}, subject to "
        f"max Pauli weight ≤ {ANCILLA_MAX_WEIGHT}, plotted against submission date -- "
        "a new point only appears if it's a strict improvement on the prior record. "
        "The dotted line is Derby-Klassen's own ancilla count at this size (arXiv "
        "2003.06939) -- both the starting point and the published result here, since "
        "this challenge doesn't yet have a separate community record to beat. See the "
        "full table below for the complete picture across every swept size.\n\n"
    )
    f.write("Lower is better.\n\n")
    render_ranked_table(
        f, "Square lattice -- fewest ancillas at max weight ≤ 3",
        f"min n_ancillas subject to max_weight ≤ {ANCILLA_MAX_WEIGHT}",
        square_entries,
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
    square_entries, dated = compute_square_entries()

    print("Writing progress chart...")
    chart_path = write_ancilla_progress_chart(dated)

    body = io.StringIO()
    render_ancilla_leaderboard_body(body, chart_path, square_entries)
    body_text = body.getvalue()

    leaderboard_path = REPO_ROOT / "LEADERBOARD_ANCILLAS.md"
    with open(leaderboard_path, "w") as f:
        f.write("# Leaderboard -- ancilla/stabilizer challenge\n\n")
        f.write(
            "Generated by `scripts/update_leaderboard_ancillas.py` — **do not hand-edit "
            "this file**. A separate challenge from `LEADERBOARD.md`/`LEADERBOARD_GRAPHS.md`: "
            f"the maximum Pauli weight is fixed at {ANCILLA_MAX_WEIGHT} (`D = max(Num, ReHop, "
            "ImHop, Inter) ≤ 3`, checked at every claimed size, not just asserted) and the "
            "goal is to minimize the number of ancilla qubits (`n_qubits - M`) needed to reach "
            "a genuinely valid encoding -- every one of the stabilizer checks in "
            "`harness/v2/verify.py`, not just Majorana anticommutation. See the top-level "
            "`README.md`'s \"The ancilla/stabilizer challenge\" section and `inbox/README.md` "
            "for the submission format and how it's told apart from the other challenges.\n\n"
        )
        f.write(body_text)
    print(f"wrote {leaderboard_path}")

    body_path = REPO_ROOT / "_ancilla_leaderboard_body.md"
    body_path.write_text(_rebase_links_for_ancillas_page(body_text))
    print(f"wrote {body_path}")


if __name__ == "__main__":
    main()
