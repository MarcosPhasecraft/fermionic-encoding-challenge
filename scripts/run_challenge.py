"""CLI for the ancilla/stabilizer challenge engine (harness/v2/challenges.py).

    python scripts/run_challenge.py ancillas --graph square --model full \
        --max-weight 3 --sizes 3-15 --solution solution/encode.py

    python scripts/run_challenge.py weights --graph square --lx 6 --ly 6 \
        --model full --max-ancillas 4 --solution solution/encode.py

    python scripts/run_challenge.py from-config challenges/official.json \
        --name square_full_w3 --solution solution/encode.py

A separate script rather than new run.py subcommands, per this pass's own
ground rule of not touching stable legacy code -- see run.py's own
docstring-equivalent comment for why it stays a thin, unchanged CLI. Writes
its own challenge_results.tsv, never results.tsv: the challenge engine's
result shape (per-size profiles, category-weight diagnostics, an ancilla
budget/cap that plain evaluate() knows nothing about) doesn't fit
results.tsv's existing fixed column set, and there's no reason to migrate
that file just because this exists alongside it.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.v2.challenges import (  # noqa: E402
    load_challenges,
    run_min_ancillas_challenge,
    run_min_weight_challenge,
)
from harness.v2.loading import load_submission_extended  # noqa: E402

_RESULTS_FILE = Path(__file__).resolve().parent.parent / "challenge_results.tsv"
_FIELDS = [
    "challenge_name", "challenge_type", "graph", "shape", "model",
    "passed", "eligible", "reason",
    "n_modes", "n_qubits", "n_ancillas", "n_stabilizers", "stabilizer_rank",
    "total_weight", "max_weight", "avg_weight",
    "max_rehop_weight", "max_imhop_weight", "max_num_weight", "max_int_weight",
]


def _stabilizer_rank(result: dict):
    return result.get("checks", {}).get("codespace_dimension", {}).get("rank")


def _append_result(challenge_name: str, challenge_type: str, graph: str, shape: str, model: str, result: dict,
                    results_file: Path = _RESULTS_FILE):
    row = {
        "challenge_name": challenge_name,
        "challenge_type": challenge_type,
        "graph": graph,
        "shape": shape,
        "model": model,
        "stabilizer_rank": _stabilizer_rank(result),
        **result,
    }
    is_new = not results_file.is_file()
    with open(results_file, "a") as f:
        if is_new:
            f.write("\t".join(_FIELDS) + "\n")
        f.write("\t".join(str(row.get(k, "")) for k in _FIELDS) + "\n")


def _parse_sizes(s: str) -> list:
    """'3-15' -> ['3','4',...,'15']; also accepts a plain comma-separated
    list, and explicit LxxLy pairs mixed in ('3-15,8x12') -- each
    comma-part is passed through to harness.v2.challenges._parse_shape
    unchanged if it isn't a '-' range.
    """
    sizes = []
    for part in s.split(","):
        if "-" in part and "x" not in part:
            lo, hi = part.split("-")
            sizes.extend(str(n) for n in range(int(lo), int(hi) + 1))
        else:
            sizes.append(part)
    return sizes


def cmd_ancillas(args):
    encode_fn, order_fn, represent_fn = load_submission_extended(args.solution)
    cfg = {
        "name": "cli-ancillas", "type": "min_ancillas_at_weight",
        "graph": args.graph, "model": args.model,
        "max_weight": args.max_weight, "sizes": _parse_sizes(args.sizes),
    }
    results = run_min_ancillas_challenge(cfg, encode_fn, order_fn, represent_fn)
    for size, result in results.items():
        status = "eligible" if result["eligible"] else f"ineligible ({result['reason']})"
        print(f"{size}: n_ancillas={result.get('n_ancillas')} max_weight={result.get('max_weight')} -- {status}")
        _append_result(cfg["name"], cfg["type"], args.graph, size, args.model, result, Path(args.results_file))


def cmd_weights(args):
    encode_fn, order_fn, represent_fn = load_submission_extended(args.solution)
    shape = f"{args.lx}x{args.ly}"
    cfg = {
        "name": "cli-weights", "type": "min_weight_at_ancillas",
        "graph": args.graph, "model": args.model,
        "shape": shape, "max_ancillas": args.max_ancillas,
    }
    result = run_min_weight_challenge(cfg, encode_fn, order_fn, represent_fn)
    status = "eligible" if result["eligible"] else f"ineligible ({result['reason']})"
    print(f"{shape}: max_weight={result.get('max_weight')} total_weight={result.get('total_weight')} -- {status}")
    _append_result(cfg["name"], cfg["type"], args.graph, shape, args.model, result, Path(args.results_file))


def cmd_from_config(args):
    challenges = {cfg["name"]: cfg for cfg in load_challenges(args.config)}
    if args.name not in challenges:
        raise SystemExit(f"no challenge named {args.name!r} in {args.config} -- have {sorted(challenges)}")
    cfg = challenges[args.name]
    encode_fn, order_fn, represent_fn = load_submission_extended(args.solution)

    results_file = Path(args.results_file)
    if cfg["type"] == "min_ancillas_at_weight":
        results = run_min_ancillas_challenge(cfg, encode_fn, order_fn, represent_fn)
        for size, result in results.items():
            status = "eligible" if result["eligible"] else f"ineligible ({result['reason']})"
            print(f"{size}: n_ancillas={result.get('n_ancillas')} max_weight={result.get('max_weight')} -- {status}")
            _append_result(cfg["name"], cfg["type"], cfg.get("graph", "square"), size, cfg.get("model", "full"), result, results_file)
    else:
        result = run_min_weight_challenge(cfg, encode_fn, order_fn, represent_fn)
        status = "eligible" if result["eligible"] else f"ineligible ({result['reason']})"
        print(f"{cfg['shape']}: max_weight={result.get('max_weight')} total_weight={result.get('total_weight')} -- {status}")
        _append_result(cfg["name"], cfg["type"], cfg.get("graph", "square"), cfg["shape"], cfg.get("model", "full"), result, results_file)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ancillas", help="Challenge A: minimize ancillas at a fixed max weight")
    p.add_argument("--graph", default="square")
    p.add_argument("--model", default="full")
    p.add_argument("--max-weight", type=int, required=True)
    p.add_argument("--sizes", required=True, help="e.g. '3-15' or '3x3,8x8'")
    p.add_argument("--solution", required=True)
    p.add_argument("--results-file", default=str(_RESULTS_FILE))
    p.set_defaults(func=cmd_ancillas)

    p = sub.add_parser("weights", help="Challenge B: minimize weights at a fixed ancilla budget")
    p.add_argument("--graph", default="square")
    p.add_argument("--lx", type=int, required=True)
    p.add_argument("--ly", type=int, default=None)
    p.add_argument("--model", default="full")
    p.add_argument("--max-ancillas", type=int, required=True)
    p.add_argument("--solution", required=True)
    p.add_argument("--results-file", default=str(_RESULTS_FILE))
    p.set_defaults(func=cmd_weights)

    p = sub.add_parser("from-config", help="run a named challenge from a JSON config file")
    p.add_argument("config", help="e.g. challenges/official.json")
    p.add_argument("--name", required=True)
    p.add_argument("--solution", required=True)
    p.add_argument("--results-file", default=str(_RESULTS_FILE))
    p.set_defaults(func=cmd_from_config)

    args = parser.parse_args()
    if getattr(args, "ly", "unset") is None:
        args.ly = args.lx
    args.func(args)


if __name__ == "__main__":
    main()
