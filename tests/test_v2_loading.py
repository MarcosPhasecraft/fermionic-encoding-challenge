"""Tests for harness.v2.loading.load_submission_extended -- adds the
optional represent() hook on top of harness.loading.load_submission's
(encode_fn, order_fn) pair without changing that function's own signature.
"""

from pathlib import Path

from harness.v2.loading import load_submission_extended

_WITH_REPRESENT = '''
def encode(spec):
    raise NotImplementedError

def order(Lx, Ly):
    return list(range(Lx * Ly))

def represent(term, raw_pauli, spec, mapping):
    return raw_pauli
'''

_WITHOUT_REPRESENT = '''
def encode(spec):
    raise NotImplementedError
'''


def test_loads_represent_hook_when_declared(tmp_path):
    path = tmp_path / "submission.py"
    path.write_text(_WITH_REPRESENT)
    encode_fn, order_fn, represent_fn = load_submission_extended(str(path))
    assert callable(encode_fn)
    assert callable(order_fn)
    assert callable(represent_fn)
    assert represent_fn("term", "XYZ", {}, {}) == "XYZ"


def test_represent_hook_is_none_when_not_declared(tmp_path):
    path = tmp_path / "submission.py"
    path.write_text(_WITHOUT_REPRESENT)
    encode_fn, order_fn, represent_fn = load_submission_extended(str(path))
    assert callable(encode_fn)
    assert order_fn is None
    assert represent_fn is None


def test_missing_encode_raises_systemexit(tmp_path):
    path = tmp_path / "submission.py"
    path.write_text("x = 1\n")
    try:
        load_submission_extended(str(path))
        assert False, "expected SystemExit"
    except SystemExit:
        pass


def test_missing_file_raises_systemexit():
    try:
        load_submission_extended(str(Path("/no/such/file.py")))
        assert False, "expected SystemExit"
    except SystemExit:
        pass
