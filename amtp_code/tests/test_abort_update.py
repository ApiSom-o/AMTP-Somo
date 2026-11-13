"""Rejected candidates are discarded (Phase 2, Step 5: "obsolete proposals must be regenerated
against the current predecessor").

  1. a candidate rejected by the owner's Validator or by the Root Anchor is rolled back: the
     Cloud Server's engine returns exactly to the finalized predecessor, and the next update passes
  2. a batch that fails half-way (an invalid second request) leaves no trace either
  3. ciphertexts stored only for a discarded candidate are removed; deleted ones are kept
  4. random histories with splits, merges and random rejections: after every rollback the engine
     equals its state before the candidate, and every accepted epoch is validated and anchored
"""
import copy
import random

import pytest

from amtp.core.hashing import H
from amtp.validator import Invalid
from tests.test_update_protocol import make_owner, random_requests


def engine_state(eng) -> dict:
    """Every mapping and commitment of the engine, as plain values."""
    def tree(t):
        return (t.n, [list(level) for level in t.levels])
    return {
        "epoch": eng.epoch, "R_D": eng.R_D, "pid_counter": eng._pid_counter,
        "parts": {p: (q.v, list(q.slots)) for p, q in eng.parts.items()},
        "trees": {p: tree(t) for p, t in eng.trees.items()},
        "lineage": dict(eng.lineage), "by_bucket": {b: sorted(s) for b, s in eng.by_bucket.items()},
        "live": dict(eng.live), "free": {p: list(f) for p, f in eng.free.items()},
        "loc": dict(eng.loc), "fwd": dict(eng.fwd),
        "comp": {h: {p: dict(e) for p, e in v.items()} for h, v in eng.comp.items()},
        "keys_in": {p: dict(c) for p, c in eng.keys_in.items()},
        "gam": {h: dict(g) for h, g in eng.gam.items()}, "rho": dict(eng.rho),
        "post": {h: (dict(o), tree(t)) for h, (o, t) in eng.post.items()},
        "part_pos": dict(eng.part_pos), "part_tree": tree(eng.part_tree),
        "imt": tree(eng.imt), "imt_layout": list(eng.imt_layout), "imt_sorted": list(eng.imt_sorted),
        "imt_nxt": dict(eng.imt_nxt), "imt_pos": dict(eng.imt_pos), "imt_free": list(eng.imt_free),
        "cuckoo_count": eng.cuckoo.count,
    }


def assert_finalized(owner):
    """The CS engine, its query snapshot, the validator and the anchor agree on one epoch."""
    eng = owner.server.engines["A"]
    e_star, r_star = owner.anchor.latest("A")
    assert not eng.in_progress and not eng.pending_ops
    assert (eng.epoch, eng.R_D) == (e_star, r_star) == (owner.validator.epoch, owner.validator.R_D)
    assert owner.server.current("A").R_D == r_star
    assert all(eng.cuckoo.might_contain(h) for h in eng.comp.keys())
    eng.comp.check()


def history(seed, b=3, rounds=15):
    rnd = random.Random(seed)
    owner = make_owner(b=b)
    live, k = [], [0]
    for _ in range(rounds):
        owner.update(random_requests(owner, rnd, b, live, k))
    return owner, rnd, live, k


def test_validator_rejection_rolls_back_and_the_next_update_passes(monkeypatch):
    owner, rnd, live, k = history(1)
    eng = owner.server.engines["A"]
    before = engine_state(eng)
    reqs = random_requests(owner, rnd, 3, live, k)

    def reject(proposal, requests):
        raise Invalid("Δ (or Aff_i) differs from the validated update")
    monkeypatch.setattr(owner.validator, "check", reject)
    with pytest.raises(Invalid):
        owner.update(reqs)
    assert engine_state(eng) == before
    assert_finalized(owner)

    monkeypatch.undo()
    owner.update(reqs)                                   # regenerated against the same predecessor
    assert_finalized(owner)
    assert owner.anchor.latest("A")[0] == before["epoch"] + 1


def test_tampered_proposal_is_discarded_and_regenerated():
    owner, rnd, live, k = history(2)
    eng = owner.server.engines["A"]
    before = engine_state(eng)
    reqs = random_requests(owner, rnd, 3, live, k)
    prop = owner.server.prepare_update("A", reqs)
    bad = copy.deepcopy(prop)
    bad["delta"] = bytes(32)
    with pytest.raises(Invalid):
        owner.validator.check(bad, reqs)
    owner.server.abort_update("A")
    assert engine_state(eng) == before
    with pytest.raises(KeyError):                        # nothing left to abort
        owner.server.abort_update("A")
    prop2 = owner.server.prepare_update("A", reqs)
    assert prop2["R_new"] == prop["R_new"] and prop2["delta"] == prop["delta"]
    sig = owner.validator.check(prop2, reqs)
    owner.anchor.submit("A", prop2["epoch_new"], prop2["R_new"], sig, prop2["delta"], prev=prop2["R_old"])
    owner.validator.advance()
    owner.server.finalize_update("A")
    assert_finalized(owner)


def test_anchor_rejection_rolls_back(monkeypatch):
    owner, rnd, live, k = history(3)
    eng = owner.server.engines["A"]
    before = engine_state(eng)
    reqs = random_requests(owner, rnd, 3, live, k)

    def refuse(*args, **kwargs):
        raise ValueError("predecessor root is not the current anchored root")
    monkeypatch.setattr(owner.anchor, "submit", refuse)
    with pytest.raises(ValueError):
        owner.update(reqs)
    assert engine_state(eng) == before
    monkeypatch.undo()
    assert_finalized(owner)
    owner.update(reqs)
    assert_finalized(owner)


def test_batch_failing_half_way_leaves_no_trace():
    owner, rnd, live, k = history(4)
    eng, dht = owner.server.engines["A"], owner.server.dht
    before = engine_state(eng)
    good = random_requests(owner, rnd, 1, live, k)[0]
    bad = copy.deepcopy(good)                            # same nonce: rejected at admission
    with pytest.raises(ValueError):
        owner.server.prepare_update("A", [good, bad])
    assert engine_state(eng) == before
    assert not dht.has(H(good["U"]["ct"]))
    owner.update([good])
    assert_finalized(owner)


def test_storage_follows_the_finalized_state():
    owner, rnd, live, k = history(5, b=2)
    dht = owner.server.dht
    victim = live[0]
    old_cid = owner.doc[victim]
    ins = random_requests(owner, rnd, 1, [], k)[0]       # an insert only
    new_cid = H(ins["U"]["ct"])
    prop = owner.server.prepare_update("A", [owner.delete_request(victim), ins])
    assert dht.has(new_cid) and dht.has(old_cid)
    owner.server.abort_update("A")
    assert not dht.has(new_cid)                          # stored only for the discarded candidate
    assert dht.has(old_cid)                              # its delete was never finalized
    assert prop["epoch_new"] == owner.anchor.latest("A")[0] + 1
    assert_finalized(owner)


@pytest.mark.parametrize("seed", range(5))
def test_random_rejections_with_split_and_merge(seed):
    rnd = random.Random(1000 + seed)
    b = rnd.choice([1, 2, 5])
    owner = make_owner(b=b)
    eng = owner.server.engines["A"]
    live, k = [], [0]
    rejected = accepted = 0
    for _ in range(60):
        snap_live, snap_k = list(live), list(k)
        reqs = random_requests(owner, rnd, b, live, k)
        if rnd.random() < 0.35:
            before = engine_state(eng)
            prop = owner.server.prepare_update("A", reqs)
            assert prop["epoch_new"] == before["epoch"] + 1
            owner.server.abort_update("A")
            assert engine_state(eng) == before
            live[:], k[:] = snap_live, snap_k                # the batch never happened
            rejected += 1
        else:
            owner.update(reqs)
            accepted += 1
        assert_finalized(owner)
    assert rejected and accepted
    full = eng.snapshot()
    assert full.R_D == eng.R_D
