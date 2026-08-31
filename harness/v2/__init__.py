"""Ancilla/stabilizer extension (Phases 1-3): additive to harness/, never
imports back into it in a way that would change its behavior.

Lives in its own subpackage rather than as new files directly under
harness/ so that scripts/submission_lib.py's harness_fingerprint() --
which hashes every harness/*.py file's content, non-recursively, to gate
the whole legacy score cache -- never sees this code and no existing
baseline's cached score is invalidated by its existence. See
harness/v2/verify.py's docstring for the fuller rationale.
"""
