"""Your fermion-to-qubit encoding. See the repo's README.md ("How to play")
and solution/README.md for the full contract and how to test this.

spec is a dict with (at least) "M" (mode count), "Lx", "Ly", "edges" (the
fermionic interaction graph), and "coords" -- everything you need is
already in it; no other arguments are allowed.

Return a mapping:
{
    "n_qubits":    int,           # N >= M
    "majoranas":   [str] * 2M,    # Pauli strings, length N, chars from IXYZ
    "stabilizers": [],            # ancilla-free for now: leave empty
}
"""


def encode(spec: dict) -> dict:
    raise NotImplementedError("write your encoding here")
