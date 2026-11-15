"""A/B: user.verify with the current merkle code vs a fast prototype that gives identical digests,
identical hash counts and identical accept/reject. Same queries, same responses, interleaved."""
import copy, hashlib, json, statistics, sys, time
OUT = sys.argv[1]
sys.argv = ["x", "search1", "--s-domains", "D1", "--fpd", "100000", "--reps", "1", "--warmup", "0", "--out", OUT]
import bench.experiments as E
import amtp.core.merkle as M
from amtp.core.hashing import HashCounter
OLD = {"node_hash": M.node_hash, "leaf_hash": M.leaf_hash, "root_from_proof": M.root_from_proof}
P_NODE, P_LEAF, L32 = b"\x00\x00\x00\x01\x01", b"\x00\x00\x00\x01\x00", b"\x00\x00\x00\x20"
def node_fast(l, r):
    if len(l) != 32 or len(r) != 32:
        return OLD["node_hash"](l, r)
    HashCounter.calls += 1; HashCounter.bytes += 77
    return hashlib.sha256(P_NODE + L32 + l + L32 + r).digest()
def rfp_fast(size, known, proof):
    if not known or any(not (0 <= i < size) for i in known):
        return None
    items = sorted(known.items()); k, n = 0, len(proof)
    while size > 1:
        nxt, i, m = [], 0, len(items)
        while i < m:
            pos, h = items[i]
            if not pos & 1:
                if i + 1 < m and items[i + 1][0] == pos + 1:
                    right = items[i + 1][1]; i += 2
                else:
                    if k >= n: return None
                    right = proof[k]; k += 1; i += 1
                nxt.append((pos >> 1, node_fast(h, right)))
            else:
                if k >= n: return None
                nxt.append((pos >> 1, node_fast(proof[k], h))); k += 1; i += 1
        items = nxt; size //= 2
    return items[0][1] if k == n and items and items[0][0] == 0 else None
def use(fast):
    M.node_hash = node_fast if fast else OLD["node_hash"]
    M.root_from_proof = rfp_fast if fast else OLD["root_from_proof"]
cases = []
orig_measure = E.measure
def capture(dom, state, user, text, a):
    t_q, ctx = user.make_query(dom.name, text, dom.anchor)
    from amtp.server import build_response as BR
    from amtp.core import boolean
    resp = BR(state, boolean.from_json(t_q["B_Q"]), t_q["nonce"], dom.server.dht)
    for d in resp["proof"]["partitions"]:
        d.pop("_positions", None)
    resp = json.loads(json.dumps(resp))
    times = {}; res = {}
    for fast in (False, True) * 4:                      # interleaved, 4 each
        use(fast); r = copy.deepcopy(resp); h0 = HashCounter.calls
        t = time.perf_counter(); rep = user.verify(ctx, r); dt = (time.perf_counter() - t) * 1e3
        assert rep["accepted"], rep
        times.setdefault(fast, []).append(dt); res.setdefault(fast, set()).add(HashCounter.calls - h0)
    use(False)
    assert res[False] == res[True] and len(res[False]) == 1, res
    cases.append((statistics.median(times[False]), statistics.median(times[True])))
    return orig_measure(dom, state, user, text, a)
E.measure = capture
E.main()
old = sum(o for o, _ in cases); new = sum(n for _, n in cases)
print(f"queries {len(cases)}  verify total old {old:.0f} ms  fast {new:.0f} ms  speed-up {old/new:.2f}x")
print("median per-query speed-up", round(statistics.median(o / n for o, n in cases), 2))
