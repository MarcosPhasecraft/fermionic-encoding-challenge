"""Entry point.

Debug path (PLAN.md, "Making the transition free"):

    python run.py --spec spec.json --mapping mapping.json

Runs verify() on hand-written JSON files and prints the result. Useful for
poking at the verifier directly without writing a Python script each time.
"""

import argparse
import json
import pprint

from harness.verify import verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="path to a JSON file holding the spec")
    parser.add_argument("--mapping", required=True, help="path to a JSON file holding the mapping")
    args = parser.parse_args()

    with open(args.spec) as f:
        spec = json.load(f)
    with open(args.mapping) as f:
        mapping = json.load(f)

    # pprint packs short nested lists (e.g. violation pairs) onto one line
    # instead of exploding every element, which json.dumps(indent=...) does.
    pprint.pprint(verify(spec, mapping), sort_dicts=False, width=100)


if __name__ == "__main__":
    main()
