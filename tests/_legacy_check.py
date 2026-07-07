"""
Shared assertion helper for tests ported verbatim from the old flat tests.py
runner. Preserves the exact (description, actual, expected, tol) call shape
so the original check() call sites could be copied over unmodified.
"""


def check(description: str, actual, expected, tol: float = None) -> None:
    if tol is not None:
        ok = abs(float(actual) - float(expected)) <= tol
    else:
        ok = actual == expected
    assert ok, f"{description}: expected {expected!r}, got {actual!r}"
