"""Entry point. Two modes:

    python run.py verify --spec spec.json --mapping mapping.json
        Debug path (PLAN.md, "Making the transition free"): runs verify()
        on hand-written JSON. For poking at the verifier directly, e.g. the
        small hand-built rejection cases.

    python run.py evaluate --lx 3 --ly 3 [--solution solution/encode.py]
        The primary path: imports encode(spec) -> mapping from a file (a
        submission, or any baseline), runs it through evaluate() (verify,
        then score only if verification passes), prints the result, and
        appends a row to results.tsv -- mirrors ecdsafail's "run --note".
"""

import argparse
import datetime
import importlib.util
import json
import pprint
import sys
from pathlib import Path

from harness.evaluate import evaluate
from harness.lattice import hamiltonian, rectangle
from harness.verify import verify

RESULTS_TSV = Path(__file__).parent / "results.tsv"
_TSV_COLUMNS = [
    "timestamp", "note", "solution", "lx", "ly", "ordering", "model",
    "passed", "n_qubits", "total_weight", "max_weight", "avg_weight",
]


def _load_encode_fn(path: str):
    if not Path(path).is_file():
        raise SystemExit(f"no such file: {path!r}")
    module_spec = importlib.util.spec_from_file_location("submission", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    if not hasattr(module, "encode"):
        raise SystemExit(f"{path} has no encode(spec) function")
    return module.encode


def _append_result(row: dict, results_file: Path):
    is_new = not results_file.exists()
    with open(results_file, "a") as f:
        if is_new:
            f.write("\t".join(_TSV_COLUMNS) + "\n")
        f.write("\t".join(str(row.get(c, "")) for c in _TSV_COLUMNS) + "\n")


def cmd_verify(args):
    with open(args.spec) as f:
        spec = json.load(f)
    with open(args.mapping) as f:
        mapping = json.load(f)
    pprint.pprint(verify(spec, mapping), sort_dicts=False, width=100)


def cmd_evaluate(args):
    encode_fn = _load_encode_fn(args.solution)
    spec = rectangle(args.lx, args.ly, ordering=args.ordering)
    terms = hamiltonian(spec, model=args.model)
    result = evaluate(spec, encode_fn, terms)

    pprint.pprint(result, sort_dicts=False, width=100)

    results_file = Path(args.results_file)
    _append_result({
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": args.note.replace("\t", " ").replace("\n", " "),
        "solution": args.solution,
        "lx": args.lx,
        "ly": args.ly,
        "ordering": args.ordering,
        "model": args.model,
        "passed": result["passed"],
        "n_qubits": result.get("n_qubits", ""),
        "total_weight": result.get("total_weight", ""),
        "max_weight": result.get("max_weight", ""),
        "avg_weight": result.get("avg_weight", ""),
    }, results_file)
    print(f"\nlogged to {results_file}")

    if not result["passed"]:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="debug path: verify a hand-written spec+mapping JSON pair")
    verify_parser.add_argument("--spec", required=True, help="path to a JSON file holding the spec")
    verify_parser.add_argument("--mapping", required=True, help="path to a JSON file holding the mapping")
    verify_parser.set_defaults(func=cmd_verify)

    evaluate_parser = subparsers.add_parser("evaluate", help="primary path: score a solution's encode(spec) -> mapping")
    evaluate_parser.add_argument("--solution", default="solution/encode.py", help="path to a Python file with an encode(spec) function")
    evaluate_parser.add_argument("--lx", type=int, required=True)
    evaluate_parser.add_argument("--ly", type=int, default=1)
    evaluate_parser.add_argument("--ordering", default="row_major", choices=["row_major", "snake", "diagonal"])
    evaluate_parser.add_argument("--model", default="full", choices=["hopping", "quadratic", "full"])
    evaluate_parser.add_argument("--note", default="", help="free-text note, logged to results.tsv")
    evaluate_parser.add_argument("--results-file", default=str(RESULTS_TSV), help="override the results log path (mainly for tests)")
    evaluate_parser.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
