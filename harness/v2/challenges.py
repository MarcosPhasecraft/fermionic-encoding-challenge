"""Challenge engine (Phase 4): Challenge A (minimize ancillas at a fixed
max weight) and Challenge B (minimize weight at a fixed ancilla budget),
built on the Phase 1-3 machinery (harness.v2.verify/score/evaluate).

Deliberately separate from the legacy leaderboard: nothing here touches
results.tsv, baselines/registry.json, or the existing score cache -- see
scripts/run_challenge.py for the CLI, which writes its own
challenge_results.tsv instead.

Challenge definitions are plain dicts (see validate_challenge for the
required shape); challenges/official.json holds the example configs this
module's docstring examples and scripts/run_challenge.py refer to.
"""

import json
from pathlib import Path

from harness.graphs import GRAPH_TYPES
from harness.graphs import build_spec as build_graph_spec
from harness.lattice import build_spec as build_square_spec
from harness.v2.evaluate import evaluate_extended
from harness.v2.hamiltonian_terms import hamiltonian_terms

_VALID_TYPES = {"min_ancillas_at_weight", "min_weight_at_ancillas"}


class ChallengeError(Exception):
    """A challenge definition is malformed."""


def _parse_shape(s: str) -> tuple:
    """'8x4' -> (8, 4); '8' -> (8, 8) -- same Lx=Ly default the square
    challenge uses elsewhere in this repo, extended (like the graph
    challenge's own shapes) to accept an explicit LxxLy pair.
    """
    if "x" in s:
        lx, ly = s.split("x")
        return int(lx), int(ly)
    return int(s), int(s)


def validate_challenge(cfg: dict) -> None:
    name = cfg.get("name", "<unnamed>")
    if cfg.get("type") not in _VALID_TYPES:
        raise ChallengeError(f"challenge {name!r}: 'type' must be one of {sorted(_VALID_TYPES)}, got {cfg.get('type')!r}")

    graph = cfg.get("graph", "square")
    if graph != "square" and graph not in GRAPH_TYPES:
        raise ChallengeError(f"challenge {name!r}: unknown graph {graph!r}")

    if cfg["type"] == "min_ancillas_at_weight":
        if not cfg.get("sizes"):
            raise ChallengeError(f"challenge {name!r}: 'sizes' is required and must be non-empty")
        if "max_weight" not in cfg:
            raise ChallengeError(f"challenge {name!r}: 'max_weight' is required")
    else:
        if not cfg.get("shape"):
            raise ChallengeError(f"challenge {name!r}: 'shape' is required")
        if "max_ancillas" not in cfg:
            raise ChallengeError(f"challenge {name!r}: 'max_ancillas' is required")


def load_challenges(path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    for cfg in data:
        validate_challenge(cfg)
    return data


def _build_spec(graph: str, lx: int, ly: int, order_fn):
    if graph == "square":
        return build_square_spec(lx, ly, order_fn)
    return build_graph_spec(graph, lx, ly, order_fn)


def _evaluate_one(graph, lx, ly, model, encode_fn, order_fn, represent_fn) -> dict:
    spec = _build_spec(graph, lx, ly, order_fn)
    terms = hamiltonian_terms(spec, model=model)
    return evaluate_extended(spec, encode_fn, terms, represent_fn)


def _with_eligibility(result: dict, is_eligible_when_passed, cap_reason) -> dict:
    result = dict(result)
    if not result["passed"]:
        result["eligible"] = False
        result.setdefault("reason", result.get("error", "verification failed"))
    elif not is_eligible_when_passed(result):
        result["eligible"] = False
        result["reason"] = cap_reason(result)
    else:
        result["eligible"] = True
        result["reason"] = None
    return result


def run_min_ancillas_challenge(cfg: dict, encode_fn, order_fn=None, represent_fn=None) -> dict:
    """Challenge A: for every size in cfg['sizes'], minimize n_ancillas
    subject to max_weight <= cfg['max_weight'].

    Returns {size: result_dict, ...} -- a per-size profile, NEVER a single
    scalar summed across sizes. An encoding can win at one size and lose at
    another; hiding that behind a sum would throw away exactly the
    information a "does this construction hold up as size grows" question
    needs. Each result_dict is the full evaluate_extended() output (so
    n_ancillas/max_weight/total_weight/category maxima/checks are all
    there for logging) plus 'eligible' (bool) and 'reason' (str or None).
    """
    graph = cfg.get("graph", "square")
    model = cfg.get("model", "full")
    max_weight = cfg["max_weight"]

    results = {}
    for size in cfg["sizes"]:
        lx, ly = _parse_shape(size)
        raw = _evaluate_one(graph, lx, ly, model, encode_fn, order_fn, represent_fn)
        results[size] = _with_eligibility(
            raw,
            is_eligible_when_passed=lambda r: r["max_weight"] <= max_weight,
            cap_reason=lambda r: f"max_weight {r['max_weight']} exceeds cap {max_weight}",
        )
    return results


def run_min_weight_challenge(cfg: dict, encode_fn, order_fn=None, represent_fn=None) -> dict:
    """Challenge B: at cfg['shape'], eligible iff n_ancillas <=
    cfg['max_ancillas']; the objective is the pair (max_weight,
    total_weight), reported as-is -- see pareto_frontier() for comparing
    multiple submissions' points, rather than inventing a combined scalar
    here.
    """
    graph = cfg.get("graph", "square")
    model = cfg.get("model", "full")
    max_ancillas = cfg["max_ancillas"]
    lx, ly = _parse_shape(cfg["shape"])

    raw = _evaluate_one(graph, lx, ly, model, encode_fn, order_fn, represent_fn)
    return _with_eligibility(
        raw,
        is_eligible_when_passed=lambda r: r["n_ancillas"] <= max_ancillas,
        cap_reason=lambda r: f"n_ancillas {r['n_ancillas']} exceeds budget {max_ancillas}",
    )


def dominates(a: dict, b: dict) -> bool:
    """Pareto dominance in (max_weight, total_weight): a dominates b iff a
    is no worse in either component and strictly better in at least one.
    a, b: dicts with 'max_weight'/'total_weight' keys (e.g. two
    run_min_weight_challenge results already filtered to eligible==True).
    """
    return (
        a["max_weight"] <= b["max_weight"]
        and a["total_weight"] <= b["total_weight"]
        and (a["max_weight"] < b["max_weight"] or a["total_weight"] < b["total_weight"])
    )


def pareto_frontier(points: list) -> list:
    """The non-dominated subset of `points` (each a dict with
    'max_weight'/'total_weight' keys, plus whatever else the caller wants
    to carry along, e.g. a submission name). Assumes every point already
    passed its own eligibility check -- filter those in first.

    Ties (two points equal in both components) are both kept: neither
    strictly dominates the other. No coefficient trades one unit of max
    weight against one unit of total weight to break them -- same
    no-invented-exchange-rate principle as PLAN.md Sec 1.6's "never combine
    metrics into a single product".
    """
    return [p for p in points if not any(dominates(q, p) for q in points if q is not p)]
