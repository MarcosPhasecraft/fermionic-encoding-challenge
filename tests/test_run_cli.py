"""Tests for run.py's CLI, via subprocess -- this is the actual entry point
a contributor uses, so it's worth testing as a black box rather than just
its internal functions. Uses --results-file to avoid touching the real
results.tsv.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _run(*args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "run.py"), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def test_verify_subcommand_on_existing_examples():
    result = _run(
        "verify",
        "--spec", "examples/spec_chain4.json",
        "--mapping", "examples/mapping_chain4_jw.json",
    )
    assert result.returncode == 0
    assert "'passed': True" in result.stdout


def test_evaluate_missing_solution_gives_clean_error():
    result = _run("evaluate", "--solution", "no/such/file.py", "--lx", "3", "--ly", "3")
    assert result.returncode != 0
    assert "no such file" in result.stderr


def test_evaluate_jw_end_to_end(tmp_path):
    results_file = tmp_path / "results.tsv"
    result = _run(
        "evaluate",
        "--solution", "baselines/jw.py",
        "--lx", "3", "--ly", "3",
        "--note", "pytest run",
        "--results-file", str(results_file),
    )
    assert result.returncode == 0
    assert "'total_weight': 201" in result.stdout
    assert "'max_weight': 4" in result.stdout

    lines = results_file.read_text().splitlines()
    assert len(lines) == 2  # header + one row
    assert "pytest run" in lines[1]
    assert "201" in lines[1]


def test_shipped_stub_fails_cleanly_not_with_a_traceback(tmp_path):
    # solution/encode.py ships as an unfilled stub -- pin that running it
    # as-is (the very first thing a fresh clone would do) fails gracefully,
    # not with a raw Python traceback, and doesn't silently "pass" empty.
    results_file = tmp_path / "results.tsv"
    result = _run(
        "evaluate",
        "--lx", "3", "--ly", "3",
        "--results-file", str(results_file),
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stdout
    assert "'passed': False" in result.stdout
    assert "NotImplementedError" in result.stdout


def test_evaluate_broken_encoding_fails_and_logs(tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text(
        "def encode(spec):\n"
        "    m = spec['M']\n"
        "    return {'n_qubits': m, 'majoranas': ['X' * m] * (2 * m), 'stabilizers': []}\n"
    )
    results_file = tmp_path / "results.tsv"
    result = _run(
        "evaluate",
        "--solution", str(broken),
        "--lx", "2", "--ly", "1",
        "--results-file", str(results_file),
    )
    assert result.returncode != 0
    assert "'passed': False" in result.stdout

    lines = results_file.read_text().splitlines()
    assert len(lines) == 2
    assert lines[1].split("\t")[7] == "False"  # passed column
