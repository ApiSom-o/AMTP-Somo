import argparse, gc, sys, tracemalloc
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
    gc.collect(); tracemalloc.start()
    s = dom.eng.snapshot()
    gc.collect()
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    extra = sum(len(t.levels) for t in s._post_trees.values()) if s._post_trees else 0
    print(f"{mode}: snapshot retained {cur/2**20:.0f} MB, peak during build {peak/2**20:.0f} MB, kept trees {len(s._post_trees)}")
    del s; gc.collect()
