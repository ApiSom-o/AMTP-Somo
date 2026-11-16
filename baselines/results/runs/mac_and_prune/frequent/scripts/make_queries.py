"""AND queries on D1 (N = 100k) where EVERY keyword is common: tiers df >= 20, >= 200, >= 1000.
Tiers 20 / 200: keywords of one source file (so the AND has >= 1 result). Tier 1000: random keywords
among the most frequent ones (results may be empty). 20 queries per (tier, kQ), seed 42."""
import json, random, sys
sys.path.insert(0, sys.argv[1])
import amtp_dataset as D
N = 100000
docs = D.domain_docs("D1", N)
df = D.doc_freq(docs)
inv = D.inverted_index(docs)
rnd = random.Random(42)
out = []
def add(tier, kq, kws):
    res = len(D.ground_truth(inv, kws))
    qid = f"F{tier}_k{kq}_{len([q for q in out if q['tier'] == tier and q['kQ'] == kq]):02d}"
    out.append({"query_id": qid, "domain": "D1", "kQ": kq, "shape": "AND", "tier": tier,
                "expression": " AND ".join(kws), "text": " AND ".join(f'"{w}"' for w in kws),
                "keywords": kws, "min_df": min(df[w] for w in kws),
                "result_size": {str(N): res}})
for tier in (20, 200):
    for kq in (2, 3, 5):
        cands = [d for d in docs if sum(df[w] >= tier for w in d.keywords) >= kq]
        rnd.shuffle(cands)
        seen = set()
        for d in cands:
            kws = sorted(rnd.sample(sorted(w for w in d.keywords if df[w] >= tier), kq))
            if tuple(kws) in seen:
                continue
            seen.add(tuple(kws))
            add(tier, kq, kws)
            if len(seen) == 20:
                break
top = sorted(w for w, c in df.items() if c >= 1000)
for kq in (2, 3, 5):
    seen = set()
    while len(seen) < 20:
        kws = tuple(sorted(rnd.sample(top, kq)))
        if kws not in seen:
            seen.add(kws)
            add(1000, kq, list(kws))
with open(sys.argv[2], "w") as f:
    for q in out:
        f.write(json.dumps(q) + "\n")
import collections, statistics as st
g = collections.defaultdict(list)
for q in out:
    g[(q["tier"], q["kQ"])].append(q)
for k, qs in sorted(g.items()):
    print(k, "n", len(qs), "min_df median", st.median(q["min_df"] for q in qs),
          "rQ median", st.median(q["result_size"][str(N)] for q in qs),
          "sum df median", st.median(sum(df[w] for w in q["keywords"]) for q in qs))
