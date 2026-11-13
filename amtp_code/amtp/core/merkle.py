"""Positional Merkle tree with multiproofs (one proof for many leaves).

Leaf hash  : H(0x00 ‖ value)
Inner node : H(0x01 ‖ left ‖ right)
Padding    : H(0x02), used to fill the tree up to a power of two.

A multiproof contains only the sibling hashes the verifier cannot compute
itself, so leaves that share a path share hashes. This is the building block
of ASPA (Authenticated Selective Proof Assembly).
"""
from .hashing import H

PAD = H(b"\x02")


def leaf_hash(value: bytes) -> bytes:
    return H(b"\x00", value)


def node_hash(left: bytes, right: bytes) -> bytes:
    return H(b"\x01", left, right)


def _size(n: int) -> int:
    size = 1
    while size < max(n, 1):
        size *= 2
    return size


class MerkleTree:
    def __init__(self, values):
        self.n = len(values)
        size = _size(self.n)
        level = [leaf_hash(v) for v in values] + [PAD] * (size - self.n)
        self.levels = [level]
        while len(level) > 1:
            level = [node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
            self.levels.append(level)

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    def set_leaf(self, i: int, value: bytes):
        """Replace leaf i and recompute only its path to the root (log n hashes)."""
        self.levels[0][i] = leaf_hash(value)
        for d in range(1, len(self.levels)):
            i //= 2
            below = self.levels[d - 1]
            self.levels[d][i] = node_hash(below[2 * i], below[2 * i + 1])

    def try_append(self, value: bytes) -> bool:
        """Fill the next padding slot in place. False if the tree is full
        (the caller then rebuilds with a doubled size)."""
        if self.n >= len(self.levels[0]):
            return False
        self.set_leaf(self.n, value)
        self.n += 1
        return True

    def multiproof(self, indices) -> list:
        """Sibling hashes needed to rebuild the root from the given leaf positions."""
        known = set(indices)
        proof = []
        for level in self.levels[:-1]:
            parents = sorted({i // 2 for i in known})
            for p in parents:
                for child in (2 * p, 2 * p + 1):
                    if child not in known:
                        proof.append(level[child])
            known = set(parents)
        return proof


def merkle_root(values) -> bytes:
    return MerkleTree(values).root


def multiverify(root: bytes, n: int, leaves: dict, proof: list) -> bool:
    """Check that leaves {position: value} sit at those positions in a tree of
    n leaves whose root is `root`. Positions must be real (0 <= pos < n)."""
    if not leaves or any(not (0 <= i < n) for i in leaves):
        return False
    known = {i: leaf_hash(v) for i, v in leaves.items()}
    remaining = list(proof)
    size = _size(n)
    while size > 1:
        parents = sorted({i // 2 for i in known})
        nxt = {}
        for p in parents:
            pair = []
            for child in (2 * p, 2 * p + 1):
                if child in known:
                    pair.append(known[child])
                elif remaining:
                    pair.append(remaining.pop(0))
                else:
                    return False
            nxt[p] = node_hash(pair[0], pair[1])
        known = nxt
        size //= 2
    return not remaining and known.get(0) == root
