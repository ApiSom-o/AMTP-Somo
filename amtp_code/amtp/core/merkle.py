"""Positional Merkle tree with multiproofs (one proof for many leaves).

Leaf hash  : H(0x00 ‖ value)
Inner node : H(0x01 ‖ left ‖ right)
Padding    : H(0x02), used to fill the tree up to a power of two.

A multiproof contains only the sibling hashes the verifier cannot compute
itself, so leaves that share a path share hashes. This is the building block
of ASPA (Authenticated Selective Proof Assembly).
"""
import hashlib

from .hashing import H, HashCounter

PAD = H(b"\x02")

# Fast paths for bytes input: the same length-prefixed byte string H builds (4-byte length ‖ tag,
# then 4-byte length ‖ each part), hashed in one call, counted exactly as H counts. Anything that is
# not bytes goes through H itself, so its behaviour (encoding, errors) is unchanged.
_sha256 = hashlib.sha256
_LEAF_TAG = (1).to_bytes(4, "big") + b"\x00"
_NODE_TAG = (1).to_bytes(4, "big") + b"\x01"
_LEN32 = (32).to_bytes(4, "big")


def leaf_hash(value: bytes) -> bytes:
    if type(value) is not bytes:
        return H(b"\x00", value)
    k = len(value)
    HashCounter.calls += 1
    HashCounter.bytes += 9 + k
    return _sha256(_LEAF_TAG + (_LEN32 if k == 32 else k.to_bytes(4, "big")) + value).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    if type(left) is not bytes or type(right) is not bytes:
        return H(b"\x01", left, right)
    a, b = len(left), len(right)
    HashCounter.calls += 1
    HashCounter.bytes += 13 + a + b
    return _sha256(_NODE_TAG + (_LEN32 if a == 32 else a.to_bytes(4, "big")) + left
                   + (_LEN32 if b == 32 else b.to_bytes(4, "big")) + right).digest()


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

    def set_leaf(self, i: int, value: bytes, undo: list = None):
        """Replace leaf i and recompute only its path to the root (log n hashes).
        undo: if given, an action that restores the old path is appended to it."""
        if undo is not None:
            saved, j = [], i
            for level in self.levels:
                saved.append(level[j])
                j //= 2
            undo.append(lambda leaf=i: self._restore_path(leaf, saved))   # i changes below
        self.levels[0][i] = leaf_hash(value)
        for d in range(1, len(self.levels)):
            i //= 2
            below = self.levels[d - 1]
            self.levels[d][i] = node_hash(below[2 * i], below[2 * i + 1])

    def _restore_path(self, i: int, saved: list):
        for level, old in zip(self.levels, saved):
            level[i] = old
            i //= 2

    def try_append(self, value: bytes, undo: list = None) -> bool:
        """Fill the next padding slot in place. False if the tree is full
        (the caller then rebuilds with a doubled size)."""
        if self.n >= len(self.levels[0]):
            return False
        n_old = self.n
        self.set_leaf(self.n, value, undo)
        self.n += 1
        if undo is not None:
            undo.append(lambda: setattr(self, "n", n_old))
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
    return root_from_proof(_size(n), {i: leaf_hash(v) for i, v in leaves.items()}, proof) == root


def root_from_proof(size: int, known: dict, proof: list):
    """Root of a padded tree of `size` leaves (a power of two) from known leaf HASHES
    {position: hash} and the sibling hashes of MerkleTree.multiproof(sorted(known)).
    None if the proof does not have exactly the expected shape. Known positions may lie in
    the padding (their hash is then PAD), which lets an updater replay appends."""
    if not known or any(not (0 <= i < size) for i in known):
        return None
    # One sort, then each level is walked left to right: a node is paired with its known sibling
    # or with the next proof hash, parents come out already in position order. Siblings are taken
    # from the proof in exactly the order of the previous per-level sorted scan.
    level = sorted(known.items())
    remaining = list(proof)
    k, total = 0, len(remaining)
    while size > 1:
        nxt = []
        i, m = 0, len(level)
        while i < m:
            pos, h = level[i]
            if pos % 2 == 0:
                if i + 1 < m and level[i + 1][0] == pos + 1:
                    right = level[i + 1][1]
                    i += 2
                elif k < total:
                    right = remaining[k]
                    k += 1
                    i += 1
                else:
                    return None
                nxt.append((pos // 2, node_hash(h, right)))
            else:
                if k >= total:
                    return None
                nxt.append((pos // 2, node_hash(remaining[k], h)))
                k += 1
                i += 1
        level = nxt
        size //= 2
    return level[0][1] if k == total and level[0][0] == 0 else None


def pad_root(size: int) -> bytes:
    """Root of a subtree of `size` padding leaves."""
    h = PAD
    while size > 1:
        h = node_hash(h, h)
        size //= 2
    return h


def sparse_root(size: int, known: dict) -> bytes:
    """Root of a subtree of `size` leaves where only `known` {position: leaf hash} are set
    and every other leaf is padding."""
    if not known:
        return pad_root(size)
    if size == 1:
        return known[0]
    half = size // 2
    return node_hash(sparse_root(half, {i: h for i, h in known.items() if i < half}),
                     sparse_root(half, {i - half: h for i, h in known.items() if i >= half}))


def grown_root(old_size: int, left_root: bytes, new_size: int, appended: dict) -> bytes:
    """Root after a tree of old_size leaves (root left_root) grows to new_size by doubling;
    appended {position >= old_size: leaf hash} are the only real leaves beyond old_size."""
    root, size = left_root, old_size
    while size < new_size:
        root = node_hash(root, sparse_root(size, {i - size: h for i, h in appended.items()
                                                  if size <= i < 2 * size}))
        size *= 2
    return root


def root_of_leaf_hashes(hashes) -> bytes:
    """Root of a tree whose leaf hashes are given (padding added as MerkleTree does)."""
    return sparse_root(_size(len(hashes)), dict(enumerate(hashes)))


tree_size = _size
