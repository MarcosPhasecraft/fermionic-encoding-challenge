"""Tests for harness.loading.load_submission."""

import pytest

from harness.loading import load_submission


def test_missing_file_raises_cleanly():
    with pytest.raises(SystemExit, match="no such file"):
        load_submission("no/such/file.py")


def test_file_without_encode_raises_cleanly(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def not_encode(spec):\n    pass\n")
    with pytest.raises(SystemExit, match="has no encode"):
        load_submission(str(f))


def test_encode_without_order_returns_none_for_order_fn(tmp_path):
    f = tmp_path / "no_order.py"
    f.write_text("def encode(spec):\n    return {}\n")
    encode_fn, order_fn = load_submission(str(f))
    assert callable(encode_fn)
    assert order_fn is None


def test_encode_with_order_returns_both(tmp_path):
    f = tmp_path / "with_order.py"
    f.write_text(
        "def order(Lx, Ly):\n    return list(range(Lx * Ly))\n\n"
        "def encode(spec):\n    return {}\n"
    )
    encode_fn, order_fn = load_submission(str(f))
    assert callable(encode_fn)
    assert order_fn(2, 2) == [0, 1, 2, 3]
