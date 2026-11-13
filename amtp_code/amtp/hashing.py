"""Hashing and canonical encoding used everywhere in AMTP.

H(a ‖ b ‖ ...) is SHA-256 over length-prefixed parts, so two different
tuples can never produce the same byte string (no concatenation ambiguity).
Enc(x) is a canonical JSON encoding: the same value always gives the same bytes.
"""
import hashlib
import json


def to_bytes(part) -> bytes:
    if isinstance(part, bytes):
        return part
    if isinstance(part, str):
        return part.encode("utf-8")
    if isinstance(part, int):
        return part.to_bytes(8, "big", signed=False)
    raise TypeError(f"cannot hash {type(part)}")


class HashCounter:
    """Counts hash calls and hashed bytes: a machine-independent cost measure
    reported next to wall-clock time in the benchmarks."""
    calls = 0
    bytes = 0

    @classmethod
    def snapshot(cls):
        return cls.calls, cls.bytes


def H(*parts) -> bytes:
    """H(p1 ‖ p2 ‖ ...) with 4-byte length prefixes."""
    h = hashlib.sha256()
    n = 0
    for p in parts:
        b = to_bytes(p)
        h.update(len(b).to_bytes(4, "big"))
        h.update(b)
        n += 4 + len(b)
    HashCounter.calls += 1
    HashCounter.bytes += n
    return h.digest()


def enc(value) -> bytes:
    """Canonical encoding Enc(·): sorted keys, no whitespace, bytes as hex."""
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":")).encode()


def _plain(v):
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def short(b: bytes, n: int = 8) -> str:
    """Short hex for display."""
    return b.hex()[:n]
