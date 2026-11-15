"""AND pruning (study flag, amtp/server.py): the server sends one keyword's full posting list and, for every
other keyword, only its components in the partitions that list covers, plus adjacent-γ proofs that it has
no component in the others. The user accepts it only if the answer is still exact: honest answers are
accepted and exact, every attack is still caught, and random changes are rejected or harmless."""
import copy
import itertools
import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "baselines"))
import wire_sizes as W                                        # noqa: E402  (the one size rule)
from amtp.adversary import ATTACKS
from amtp.core import boolean
from amtp.core.hashing import H, enc_posting
from amtp.core.merkle import merkle_root
from amtp.index import and_prune_on, gamma, set_and_prune
from amtp.scenario import DOCS, World
from test_phase5_fuzz import _cheat, _mutate, _result

VOCAB = ["alpha", "beta", "gamma", "delta", "omega"]
QUERIES = (["alpha AND beta", "alpha AND delta", "beta AND delta", "beta AND gamma AND delta",
            "alpha AND beta AND gamma", "(alpha AND beta) OR omega", "(alpha OR beta) AND delta",
            "alpha AND nosuchword", "alpha OR beta"])


@pytest.fixture
def prune():
    old = and_prune_on()
    set_and_prune(True)
    yield
    set_and_prune(old)


def _world():
    """The demo world plus 40 synthetic files in domain A (12 partitions), so keywords span many partitions."""
    w = World()
    rnd = random.Random(1)
    policy = DOCS["A"][0][3]
    words = {}
    docs = []
    for i in range(40):
        ws = rnd.sample(VOCAB, rnd.randint(1, 3))
        words[f"S-{i:02d}"] = set(ws)
        docs.append({"id": f"S-{i:02d}", "title": " ".join(ws), "body": "synthetic note " + " ".join(ws),
                     "policy": policy})
    w.owners["A"].add_documents(docs)
    return w, words


def _truth(words, text):
    ast = boolean.parse(text)
    sets = {k: {d for d, ws in words.items() if k in ws} for k in boolean.leaves(ast)}
    return boolean.evaluate(ast, sets)


def _ask(w, user, text):
    t_q, ctx = user.make_query("A", text, w.anchor)
    out = w.server.search(t_q)
    assert out["status"] == "ok"
    return ctx, json.loads(json.dumps(out["response"]))


def _focus(resp):
    return [e for e in resp["proof"]["evidence"] if e.get("mode") == "focus"]


@pytest.fixture(scope="module")
def rich():
    old = and_prune_on()
    set_and_prune(True)          # the world's snapshots keep their R^post trees
    try:
        yield _world()
    finally:
        set_and_prune(old)


def test_focus_rule():
    a, b, c = ("leaf", "a"), ("leaf", "b"), ("leaf", "c")
    known = {"a": {1, 2}, "b": {2, 3}}
    assert boolean.focus(("AND", [a, c]), known) == {1, 2}
    assert boolean.focus(("AND", [a, b]), known) == {2}
    assert boolean.focus(("OR", [a, b]), known) == {1, 2, 3}
    assert boolean.focus(("OR", [a, c]), known) is None
    assert boolean.focus(c, known) is None


@pytest.mark.skipif(os.environ.get("AMTP_AND_PRUNE", "0") == "1", reason="suite run with AMTP_AND_PRUNE=1")
def test_default_is_off():
    assert not and_prune_on()
    w = World()
    _, resp = _ask(w, w.users["mali"], "insulin AND diabetes")
    assert not _focus(resp)


@pytest.mark.parametrize("text", QUERIES)
def test_honest_answers_are_accepted_and_exact(prune, rich, text):
    w, words = rich
    user = w.users["mali"]
    ctx, resp = _ask(w, user, text)
    rep = user.verify(ctx, resp)
    assert rep["accepted"], (text, rep["failed"], rep["checks"])
    synthetic = {o["doc"] for o in user.decrypt(resp) if o["doc"].startswith("S-")}
    assert synthetic == _truth(words, text)
    if text == "alpha OR beta":
        assert not _focus(resp)                      # an OR needs every list in full: nothing is pruned


def test_absence_proofs_and_smaller_proofs(prune, rich):
    w, _ = rich
    user = w.users["mali"]
    used_nb, n_pruned, total_p, total_f = False, 0, 0, 0
    old = and_prune_on()
    for k in (2, 3):
        for combo in itertools.combinations(VOCAB, k):
            text = " AND ".join(combo)
            set_and_prune(True)
            ctx, pruned = _ask(w, user, text)
            assert user.verify(ctx, pruned)["accepted"], text
            set_and_prune(False)
            ctx, full = _ask(w, user, text)
            assert user.verify(ctx, full)["accepted"], text
            assert not _focus(full)
            assert {r["cid"] for r in pruned["R_ct"]} == {r["cid"] for r in full["R_ct"]}
            # fewer opened slots in a partition can need a few more sibling hashes in its slot multiproof
            p_bytes, f_bytes = W.amtp_proof_bytes(pruned["proof"]), W.amtp_proof_bytes(full["proof"])
            assert p_bytes <= f_bytes * 1.05, (text, p_bytes, f_bytes)
            total_p, total_f = total_p + p_bytes, total_f + f_bytes
            n_pruned += bool(_focus(pruned))
            used_nb |= any(e["nb"] for e in _focus(pruned))
    set_and_prune(old)
    assert n_pruned >= 10                            # most of the 20 AND queries use the focus form
    assert total_p < total_f
    assert used_nb                                   # some query needed an adjacent-γ absence proof


@pytest.mark.parametrize("mode", sorted(set(ATTACKS) - {"honest", "storage_loss"}))
def test_every_attack_is_still_caught(prune, mode):
    w, _ = _world()
    user = w.users["mali"]
    query = "beta AND gamma AND delta"
    t_q, _ = user.make_query("A", query, w.anchor)
    assert w.adversary.search(t_q)["status"] == "ok"
    t_q, ctx = user.make_query("A", query, w.anchor)
    out = w.adversary.search(t_q, mode)
    assert out["attack"]["applied"], mode
    rep = user.verify(ctx, json.loads(json.dumps(out["response"])))
    assert not rep["accepted"], mode


def _answer(rich, text="beta AND delta"):
    w, _ = rich
    user = w.users["mali"]
    ctx, resp = _ask(w, user, text)
    assert user.verify(ctx, copy.deepcopy(resp))["accepted"]
    return user, ctx, resp


def _rejected(user, ctx, resp):
    return not user.verify(ctx, resp)["accepted"]


def test_withheld_component_is_caught(prune, rich):
    user, ctx, resp = _answer(rich)
    e = next(e for e in _focus(resp) if e["segs"])
    e["segs"].pop()
    assert _rejected(user, ctx, resp)


def test_component_turned_into_neighbour_is_caught(prune, rich):
    """The server opens a focus partition only as a neighbour, i.e. claims the keyword is absent there."""
    user, ctx, resp = _answer(rich)
    e = next(e for e in _focus(resp) if e["segs"])
    j, pid, comp = e["segs"].pop()
    v = next(d["v"] for d in resp["proof"]["partitions"] if d["pid"] == pid)
    e["nb"] = sorted(e["nb"] + [[j, pid, v, H(enc_posting(comp)).hex()]])
    assert _rejected(user, ctx, resp)


def test_dropped_neighbour_is_caught(prune, rich):
    user, ctx, resp = _answer(rich)
    e = next(e for e in _focus(resp) if e["nb"])
    e["nb"].pop()
    assert _rejected(user, ctx, resp)


def test_changed_component_is_caught(prune, rich):
    user, ctx, resp = _answer(rich)
    e = next(e for e in _focus(resp) if e["segs"])
    e["segs"][0][2].pop()
    assert _rejected(user, ctx, resp)


def test_wrong_tree_size_is_caught(prune, rich):
    user, ctx, resp = _answer(rich)
    _focus(resp)[0]["n_sel"] += 1
    assert _rejected(user, ctx, resp)


def test_no_full_keyword_is_rejected(prune, rich):
    """Every keyword in a valid focus form, but none in full: nothing bounds where a match can lie."""
    user, ctx, resp = _answer(rich)
    descs = {d["pid"]: d["v"] for d in resp["proof"]["partitions"]}
    descs.update((pid, v) for pid, v in resp["proof"].get("versions", []))   # result-only part check form
    for e in resp["proof"]["evidence"]:
        if e["status"] == "present" and e.get("mode") != "focus":
            L = e.pop("L")
            e.update(mode="focus", n_sel=len(L), nb=[], post_proof=[],
                     segs=[[j, pid, comp] for j, (pid, comp) in enumerate(L)],
                     R_post=merkle_root([gamma(pid, descs[pid], comp) for pid, comp in L]).hex())
            e["post_proof"] = []                     # every leaf opened: the multiproof is empty
    assert all(e.get("mode") == "focus" for e in resp["proof"]["evidence"] if e["status"] == "present")
    rep = user.verify(ctx, resp)
    assert not rep["accepted"] and rep["failed"] == "papc"


@pytest.mark.parametrize("seed", range(3))
def test_random_changes_are_rejected_or_harmless(prune, rich, seed):
    rnd = random.Random(seed)
    w, _ = rich
    user = w.users["mali"]
    for text in QUERIES:
        ctx, honest = _ask(w, user, text)
        assert user.verify(ctx, copy.deepcopy(honest))["accepted"], text
        truth = _result(honest)
        for i in range(120):
            resp = copy.deepcopy(honest)
            if i % 4 == 0:
                _cheat(rnd, resp)
            for _ in range(rnd.randint(0 if i % 4 == 0 else 1, 3)):
                _mutate(rnd, resp)
            rep = user.verify(ctx, resp)                     # must not raise
            if rep["accepted"]:
                assert _result(resp) == truth, (text, rep)
