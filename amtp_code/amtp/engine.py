"""Incremental domain engine shared by AMTP and its ablation variants.

AMTP, Static-MT and Global-MT all run THIS code. They differ only in the
partition policy plugged in (see variants.py), so any difference in the
measurements comes from partitioning, not from different implementations.

Updates follow the report's Phase 2-3:
  * insert places cid in an active partition; delete leaves a tombstone ⊥
  * a modified partition bumps its version once per committed batch
  * every posting component whose content or partition version changed is
    re-committed (γ), then ρ, then the IMT leaf, then R^part and R_D
  * only dirty Merkle paths are recomputed (no full rebuild)
  * the IMT is an indexed Merkle tree: a new key is appended (or reuses a freed
    position) and its predecessor's next pointer is updated, a removed key frees
    its position and relinks its predecessor, so a key-set change costs O(log K)
"""
import bisect
import time
from collections import Counter

from .hashing import H, HashCounter
from .index import (EMPTY_SLOT, IMT_EMPTY, SENTINEL_LO, ZERO, DomainState, Partition,
                    domain_root, gamma, imt_leaf, imt_next, rho, sorted_imt_layout)
from .merkle import MerkleTree


class Engine:
    def __init__(self, domain: str, policy):
        self.domain, self.policy = domain, policy
        self.epoch = 0
        self._pid_counter = 0
        self.parts, self.trees = {}, {}       # pid -> Partition / slot MerkleTree
        self.lineage, self.by_bucket = {}, {}  # pid -> buckets served; bucket -> pids
        self.live, self.free = {}, {}          # pid -> live count / tombstoned slots
        self.loc, self.fwd = {}, {}            # cid -> (pid, slot) / keyword keys
        self.comp = {}                         # h -> {pid: {cid: slot}}
        self.keys_in = {}                      # pid -> Counter(h)
        self.gam, self.rho = {}, {}            # h -> {pid: γ} / h -> ρ
        self.post = {}                         # h -> (pid order, MerkleTree over γ) for R^post
        self._reset_dirty()
        for buckets in policy.initial_lineages():
            self._new_partition([], frozenset(buckets))
        self._reset_dirty()
        self._rebuild_part_tree()
        self._rebuild_imt()
        self.R_D = domain_root(domain, 0, self.part_tree.root, self.imt.root)

    # ------------------------------------------------------------ updates
    def insert(self, cid: bytes, keys, bucket: int):
        if cid in self.loc:
            raise ValueError("cid already live")
        self.fwd[cid] = frozenset(keys)
        pid = self.policy.place(self, bucket)
        p = self.parts[pid]
        if self.free[pid]:
            slot = self.free[pid].pop()
            p.slots[slot] = cid
            self.trees[pid].set_leaf(slot, cid)
        else:
            slot = len(p.slots)
            p.slots.append(cid)
            if not self.trees[pid].try_append(cid):
                self.trees[pid] = MerkleTree(p.slots)        # capacity doubled
        self.live[pid] += 1
        self._attach(cid, pid, slot)
        self._touch(pid)

    def delete(self, cid: bytes):
        pid, slot = self.loc[cid]
        self.parts[pid].slots[slot] = EMPTY_SLOT              # tombstone ⊥
        self.trees[pid].set_leaf(slot, EMPTY_SLOT)
        self.free[pid].append(slot)
        self.live[pid] -= 1
        self._detach(cid, pid)
        del self.loc[cid]
        del self.fwd[cid]
        self._touch(pid)

    def commit(self) -> dict:
        """Adapt (policy), repair commitments, advance the epoch. Returns cost stats."""
        t0 = time.perf_counter()
        c0, b0 = HashCounter.snapshot()
        touched = sorted((self._modified | self._new) & self.parts.keys())
        splits, merges = self.policy.adapt(self, touched)

        for pid in self._modified & self.parts.keys():
            if pid in self._new:
                continue
            if self.policy.versioned:
                self.parts[pid].v += 1
                for h in self.keys_in[pid]:
                    self._dirty_comp.add((h, pid))
        n_parts_changed = len(self._modified | self._new)

        if self._new or self._retired:
            self._rebuild_part_tree()
        else:
            for pid in self._modified:
                self.part_tree.set_leaf(self.part_pos[pid], self._A(pid))

        dirty_pids = {}
        for h, pid in self._dirty_comp:
            self._dirty_keys.add(h)
            dirty_pids.setdefault(h, set()).add(pid)
            entries = self.comp.get(h, {}).get(pid)
            if entries and pid in self.parts:
                comp = sorted(entries.items(), key=lambda e: e[1])
                self.gam.setdefault(h, {})[pid] = gamma(pid, self.parts[pid].v, comp)
            elif h in self.gam:
                self.gam[h].pop(pid, None)

        added, removed = [], []
        for h in self._dirty_keys:
            if self.comp.get(h):
                if h not in self.rho:
                    added.append(h)
                self.rho[h] = rho(h, len(self.comp[h]), self._post_root(h, dirty_pids[h]))
            else:
                self.comp.pop(h, None)
                self.gam.pop(h, None)
                self.post.pop(h, None)
                if self.rho.pop(h, None) is not None:
                    removed.append(h)
        self._update_imt(added, removed)

        self.epoch += 1
        self.R_D = domain_root(self.domain, self.epoch, self.part_tree.root, self.imt.root)
        c1, b1 = HashCounter.snapshot()
        stats = {
            "update_ms": (time.perf_counter() - t0) * 1000,
            "hash_calls": c1 - c0, "hash_bytes": b1 - b0,
            "splits": splits, "merges": merges,
            "partitions_changed": n_parts_changed,
            "posting_components_refreshed": len(self._dirty_comp),
            "keys_refreshed": len(self._dirty_keys),
        }
        self._reset_dirty()
        return stats

    # ------------------------------------------------------- restructuring
    def live_entries(self, pid):
        return [c for c in self.parts[pid].slots if c != EMPTY_SLOT]

    def split(self, pid):
        """Two contiguous halves with ||S_L| - |S_R|| <= 1, fresh PIDs, v = 0."""
        entries, lineage = self.live_entries(pid), self.lineage[pid]
        half = len(entries) // 2
        self._retire(pid)
        return [self._new_partition(entries[:half], lineage),
                self._new_partition(entries[half:], lineage)]

    def merge(self, a, b):
        """Concatenate live entries in increasing source-PID order into a fresh partition."""
        first, second = sorted((a, b))
        entries = self.live_entries(first) + self.live_entries(second)
        lineage = self.lineage[first] | self.lineage[second]
        self._retire(first)
        self._retire(second)
        return self._new_partition(entries, lineage)

    # -------------------------------------------------------------- views
    def snapshot(self) -> DomainState:
        """Full-rebuild view of the current epoch (used for queries and as a
        correctness check: its R_D must equal the incrementally maintained one)."""
        parts = [Partition(p.pid, p.v, list(p.slots)) for _, p in sorted(self.parts.items())]
        return DomainState(self.domain, self.epoch, parts, dict(self.fwd), list(self.imt_layout))

    def layout(self) -> dict:
        sizes = sorted(self.live.values())
        return {"partitions": len(sizes), "max_partition": sizes[-1] if sizes else 0,
                "min_partition": sizes[0] if sizes else 0, "keys": len(self.rho)}

    # ------------------------------------------------------------ helpers
    def _new_partition(self, cids, lineage):
        self._pid_counter += 1
        pid = H("pid", self.domain, self._pid_counter).hex()[:16]
        p = Partition(pid=pid, v=0, slots=list(cids))
        self.parts[pid] = p
        self.trees[pid] = MerkleTree(p.slots)
        self.lineage[pid] = lineage
        for b in lineage:
            self.by_bucket.setdefault(b, set()).add(pid)
        self.live[pid], self.free[pid], self.keys_in[pid] = len(cids), [], Counter()
        for slot, cid in enumerate(cids):
            self._attach(cid, pid, slot)
        self._new.add(pid)
        return pid

    def _retire(self, pid):
        for cid in self.live_entries(pid):
            self._detach(cid, pid)
        for b in self.lineage[pid]:
            self.by_bucket[b].discard(pid)
        for d in (self.parts, self.trees, self.lineage, self.live, self.free, self.keys_in):
            del d[pid]
        self._modified.discard(pid)
        if pid in self._new:
            self._new.discard(pid)          # created and retired in the same batch
        else:
            self._retired.add(pid)

    def _attach(self, cid, pid, slot):
        self.loc[cid] = (pid, slot)
        for h in self.fwd[cid]:
            self.comp.setdefault(h, {}).setdefault(pid, {})[cid] = slot
            self.keys_in[pid][h] += 1
            self._dirty_comp.add((h, pid))

    def _detach(self, cid, pid):
        for h in self.fwd[cid]:
            entries = self.comp[h][pid]
            del entries[cid]
            if not entries:
                del self.comp[h][pid]
            self.keys_in[pid][h] -= 1
            if not self.keys_in[pid][h]:
                del self.keys_in[pid][h]
            self._dirty_comp.add((h, pid))

    def _touch(self, pid):
        if pid not in self._new:
            self._modified.add(pid)

    def _post_root(self, h, changed):
        """R^post over γ in PID order. If the keyword still lives in the same
        partitions, only the changed γ paths are recomputed (dirty-path update)."""
        sel = self.comp[h]
        cached = self.post.get(h)
        if cached and len(cached[0]) == len(sel) and all(p in cached[0] for p in sel):
            order, tree = cached
            for pid in changed:
                if pid in order:
                    tree.set_leaf(order[pid], self.gam[h][pid])
            return tree.root
        pids = sorted(sel)
        tree = MerkleTree([self.gam[h][p] for p in pids])
        self.post[h] = ({p: i for i, p in enumerate(pids)}, tree)
        return tree.root

    def _A(self, pid):
        return H(pid, self.parts[pid].v, self.trees[pid].root)

    def _rebuild_part_tree(self):
        order = sorted(self.parts)
        self.part_pos = {pid: i for i, pid in enumerate(order)}
        self.part_tree = MerkleTree([self._A(pid) for pid in order])

    def _rebuild_imt(self):
        """Full build (only at start): lower sentinel, then the keys in ascending order."""
        self.imt_layout = sorted_imt_layout(self.rho)
        self.imt_sorted = sorted(self.rho)
        self.imt_nxt = imt_next(self.rho)
        self.imt_pos = {h: i for i, h in enumerate(self.imt_layout)}
        self.imt_free = []
        self.imt = MerkleTree([self._imt_value(h) for h in self.imt_layout])

    def _imt_value(self, h):
        if h is None:
            return IMT_EMPTY
        return imt_leaf(h, ZERO if h == SENTINEL_LO else self.rho[h], self.imt_nxt[h])

    def _update_imt(self, added, removed):
        """Indexed-IMT maintenance: O(log K) per changed key instead of a rebuild."""
        dirty = {self.imt_pos[h] for h in self._dirty_keys if h in self.rho and h in self.imt_pos}
        for h in sorted(removed):
            i = bisect.bisect_left(self.imt_sorted, h)
            prev = self.imt_sorted[i - 1] if i else SENTINEL_LO
            self.imt_nxt[prev] = self.imt_nxt.pop(h)
            del self.imt_sorted[i]
            pos = self.imt_pos.pop(h)
            self.imt_layout[pos] = None
            self.imt_free.append(pos)
            dirty |= {pos, self.imt_pos[prev]}
        appended = []
        for h in sorted(added):
            i = bisect.bisect_left(self.imt_sorted, h)
            prev = self.imt_sorted[i - 1] if i else SENTINEL_LO
            self.imt_nxt[h] = self.imt_nxt[prev]
            self.imt_nxt[prev] = h
            self.imt_sorted.insert(i, h)
            if self.imt_free:
                pos = self.imt_free.pop()
                self.imt_layout[pos] = h
                dirty.add(pos)
            else:
                pos = len(self.imt_layout)
                self.imt_layout.append(h)
                appended.append(pos)
            self.imt_pos[h] = pos
            dirty.add(self.imt_pos[prev])
        for pos in sorted(dirty - set(appended)):
            self.imt.set_leaf(pos, self._imt_value(self.imt_layout[pos]))
        for pos in appended:
            if not self.imt.try_append(self._imt_value(self.imt_layout[pos])):
                self.imt = MerkleTree([self._imt_value(h) for h in self.imt_layout])   # capacity doubled
                break

    def _reset_dirty(self):
        self._modified, self._new, self._retired = set(), set(), set()
        self._dirty_comp, self._dirty_keys = set(), set()
