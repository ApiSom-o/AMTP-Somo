"""Domain state: partitions, Search Tree postings, PAPC and IMT (Phases 2-3).

DomainState is the Cloud Server's read-only query snapshot of one finalized epoch. The Engine
(engine.py) maintains the commitments incrementally and the owner's Validator checks each
transition on its dirty paths; Engine.snapshot() then rebuilds this snapshot in full and the
server checks that its R_D equals the incremental one.
"""
import re
from dataclasses import dataclass, field

from .bptree import BPlusTree
from .core.hashing import H, enc_posting
from .cuckoo import CuckooFilter
from .core.merkle import MerkleTree, merkle_root

EMPTY_SLOT = b""
SENTINEL_LO = b"\x00" * 32
SENTINEL_HI = b"\xff" * 32
ZERO = b"\x00" * 32

STOPWORDS = set("""
a an and are as at be been but by for from has have in into is it its of on or
our the their this to was were will with we after before during under over per
all any can more most new not no only other same than then these those very
""".split())


def extract_keywords(text: str) -> set:
    """Simple keyword extractor for the demo (the prototype uses RAKE)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS and not w.isdigit()}


@dataclass
class Partition:
    pid: str
    v: int
    slots: list = field(default_factory=list)  # slot ℓ -> cid (bytes) or EMPTY_SLOT

    @property
    def count(self) -> int:
        return sum(1 for s in self.slots if s != EMPTY_SLOT)

    def tree(self) -> MerkleTree:
        return MerkleTree(self.slots)


def gamma(pid: str, v: int, component) -> bytes:
    """γ_{w,j} = H(PID ‖ v ‖ H(Enc(L_{w,j}))) with the binary posting encoding enc_posting
    (entries (cid, ℓ) in slot order; cid as bytes or hex)."""
    return H(pid, v, H(enc_posting(component)))


def rho(h: bytes, n_sel: int, r_post: bytes) -> bytes:
    """ρ_w = H(h_w ‖ |Sel(h_w)| ‖ R^post)  (written σ_h in AMTP_6)"""
    return H(h, n_sel, r_post)


def imt_leaf(h: bytes, r: bytes, nxt: bytes) -> bytes:
    """I_w = H(h_w ‖ ρ_w ‖ next(h_w)): indexed Merkle tree leaf. next(h_w) is the smallest
    indexed key above h_w (SENTINEL_HI for the largest key), so a single authenticated
    leaf with h_lo < h < next(h_lo) proves that h is not indexed."""
    return H(h, r, nxt)


IMT_EMPTY = H("imt-empty")      # value of a freed IMT position (deleted key)


def sorted_imt_layout(keys) -> list:
    """Initial IMT layout: lower sentinel, then the keys in ascending order.
    Later keys are appended (or fill freed positions), so positions are NOT sorted."""
    return [SENTINEL_LO] + sorted(keys)


def imt_next(keys) -> dict:
    """next(h) for the lower sentinel and every key, from the sorted key list."""
    order = [SENTINEL_LO] + sorted(keys) + [SENTINEL_HI]
    return {order[i]: order[i + 1] for i in range(len(order) - 1)}


class DomainState:
    """One finalized snapshot of a domain at one epoch."""

    def __init__(self, domain: str, epoch: int, partitions, fwd: dict, imt_layout=None):
        self.domain = domain
        self.epoch = epoch
        self.partitions = partitions            # ordered: position in partition tree
        self.fwd = fwd                          # cid -> set of keyword keys h
        self.imt_layout = imt_layout            # IMT position -> key h / None (freed); None = sorted
        self._build()

    def _build(self):
        # Loc_i: where every cid lives
        self.loc = {}
        self.part_trees = {}
        for p in self.partitions:
            self.part_trees[p.pid] = p.tree()
            for slot, cid in enumerate(p.slots):
                if cid != EMPTY_SLOT:
                    self.loc[cid] = (p.pid, slot)
        self.by_pid = {p.pid: p for p in self.partitions}
        self.part_pos = {p.pid: i for i, p in enumerate(self.partitions)}

        # Partition tree: leaves A_{i,j} = H(PID ‖ v ‖ R_P)
        self.A = [H(p.pid, p.v, self.part_trees[p.pid].root) for p in self.partitions]
        self.part_tree = MerkleTree(self.A)

        # Search Tree postings: h -> [(PID, [(cid, ℓ), ...]), ...]
        groups = {}
        for cid, keys in self.fwd.items():
            pid, slot = self.loc[cid]
            for h in keys:
                groups.setdefault(h, {}).setdefault(pid, []).append((cid, slot))
        # B+ Search Tree T^S_i over the protected keys, plus the Cuckoo filter in front of it
        self.postings = BPlusTree.from_sorted(
            (h, [(pid, sorted(entries, key=lambda e: e[1])) for pid, entries in sorted(groups[h].items())])
            for h in sorted(groups))
        self.cuckoo = CuckooFilter.from_keys(self.postings.keys())

        # PAPC per keyword, then the indexed IMT: leaf H(h ‖ ρ ‖ next(h)) at its position
        self.rho = {}
        for h, L in self.postings.items():
            gammas = [gamma(pid, self.by_pid[pid].v, comp) for pid, comp in L]
            self.rho[h] = rho(h, len(L), merkle_root(gammas))
        layout = self.imt_layout or sorted_imt_layout(self.rho)
        if set(layout) - {None, SENTINEL_LO} != set(self.rho) or layout[0] != SENTINEL_LO:
            raise ValueError("IMT layout does not hold exactly the indexed keys")
        self.imt_next = imt_next(self.rho)
        self.imt_rho = {**self.rho, SENTINEL_LO: ZERO}
        self.imt_pos = {h: i for i, h in enumerate(layout) if h is not None}
        self.imt_n = len(layout)
        self.imt = MerkleTree([IMT_EMPTY if h is None else imt_leaf(h, self.imt_rho[h], self.imt_next[h])
                               for h in layout])

        self.R_part = self.part_tree.root
        self.R_idx = self.imt.root
        self.R_D = domain_root(self.domain, self.epoch, self.R_part, self.R_idx)


def domain_root(domain: str, epoch: int, r_part: bytes, r_idx: bytes) -> bytes:
    """R_D^(e) = H(i ‖ e ‖ R^part ‖ R^idx)"""
    return H(domain, epoch, r_part, r_idx)
