"""Tests for scripts/run_challenge.py's CLI, via subprocess -- same
black-box approach as tests/test_run_cli.py for run.py. Uses --results-file
to avoid touching the real challenge_results.tsv.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

_SPECTATOR_SOLUTION = """
from baselines.jw import encode as jw_encode

def encode(spec):
    mapping = jw_encode(spec)
    m = mapping["n_qubits"]
    return {
        "n_qubits": m + 1,
        "majoranas": [s + "I" for s in mapping["majoranas"]],
        "stabilizers": ["I" * m + "Z"],
    }
"""


def _run(*args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_challenge.py"), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def test_ancillas_subcommand_end_to_end(tmp_path):
    solution = tmp_path / "spectator.py"
    solution.write_text(_SPECTATOR_SOLUTION)
    results_file = tmp_path / "challenge_results.tsv"

    result = _run(
        "ancillas", "--graph", "square", "--max-weight", "1000",
        "--sizes", "3x3,4x4", "--solution", str(solution),
        "--results-file", str(results_file),
    )
    assert result.returncode == 0, result.stderr
    assert "3x3:" in result.stdout
    assert "4x4:" in result.stdout
    assert "eligible" in result.stdout

    lines = results_file.read_text().splitlines()
    assert len(lines) == 3  # header + 2 sizes
    header = lines[0].split("\t")
    assert "n_ancillas" in header
    for row in lines[1:]:
        assert row.split("\t")[header.index("n_ancillas")] == "1"


def test_weights_subcommand_end_to_end(tmp_path):
    solution = tmp_path / "spectator.py"
    solution.write_text(_SPECTATOR_SOLUTION)
    results_file = tmp_path / "challenge_results.tsv"

    result = _run(
        "weights", "--graph", "square", "--lx", "4", "--ly", "4",
        "--max-ancillas", "4", "--solution", str(solution),
        "--results-file", str(results_file),
    )
    assert result.returncode == 0, result.stderr
    assert "eligible" in result.stdout

    lines = results_file.read_text().splitlines()
    assert len(lines) == 2  # header + 1 row


def test_weights_subcommand_defaults_ly_to_lx():
    solution = REPO_ROOT / "baselines" / "jw.py"
    result = _run(
        "weights", "--lx", "3", "--max-ancillas", "0",
        "--solution", str(solution), "--results-file", "/dev/null",
    )
    assert result.returncode == 0, result.stderr
    assert "3x3:" in result.stdout


def test_from_config_subcommand_runs_the_shipped_official_config(tmp_path):
    solution = tmp_path / "spectator.py"
    solution.write_text(_SPECTATOR_SOLUTION)
    results_file = tmp_path / "challenge_results.tsv"

    result = _run(
        "from-config", "challenges/official.json", "--name", "square_6x6_a4",
        "--solution", str(solution), "--results-file", str(results_file),
    )
    assert result.returncode == 0, result.stderr
    assert "6x6:" in result.stdout

    lines = results_file.read_text().splitlines()
    assert len(lines) == 2


def test_from_config_unknown_name_fails_cleanly():
    result = _run(
        "from-config", "challenges/official.json", "--name", "no-such-challenge",
        "--solution", "baselines/jw.py",
    )
    assert result.returncode != 0
    assert "no-such-challenge" in result.stderr


def test_crashing_encoder_fails_cleanly_not_with_a_traceback(tmp_path):
    solution = tmp_path / "broken.py"
    solution.write_text("def encode(spec):\n    raise RuntimeError('nope')\n")
    results_file = tmp_path / "challenge_results.tsv"

    result = _run(
        "ancillas", "--max-weight", "3", "--sizes", "3x3",
        "--solution", str(solution), "--results-file", str(results_file),
    )
    assert result.returncode == 0  # a bad *submission* isn't a CLI failure
    assert "Traceback" not in result.stdout
    assert "ineligible" in result.stdout
