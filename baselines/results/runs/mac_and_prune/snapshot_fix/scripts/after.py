import argparse, gc, statistics as st, sys, time, tracemalloc
N = int(sys.argv[1])
sys.argv = ["experiments.py", "search1", "--s-domains", "D1", "--fpd", str(N)]
import bench.experiments as E
from amtp.index import set_and_prune
cap = {}
orig = argparse.ArgumentParser.parse_args
def grab(self, *a, **k):
    cap["a"] = orig(self, *a, **k); raise SystemExit
argparse.ArgumentParser.parse_args = grab
try: E.main()
except SystemExit: pass
argparse.ArgumentParser.parse_args = orig
a = cap["a"]; corpus = E.Corpus(a)
src = corpus.D.domain_docs("D1", N, a.data)
dom, state, lay = E.setup("D1", corpus, src, a)
del state; gc.collect()
for mode in ("off", "on"):
    set_and_prune(mode == "on")
    ts = []
    for _ in range(3):
        t = time.perf_counter(); s = dom.eng.snapshot(); ts.append(time.perf_counter() - t); del s; gc.collect()
    gc.collect(); tracemalloc.start(); s = dom.eng.snapshot(); gc.collect()
    cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    print(f"{mode}: build {st.median(ts):.2f}s {[round(x,2) for x in ts]} | retained {cur/2**20:.0f} MB, peak {peak/2**20:.0f} MB, kept trees {len(s._post_trees)} of {len(s.rho)}")
    del s; gc.collect()
