import argparse, gc, statistics as st, sys, time
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
res = {}
for rep in range(2):
    for mode in ("off", "on", "off+nogc", "on+nogc"):
        set_and_prune(mode.startswith("on"))
        if "nogc" in mode: gc.disable()
        t = time.perf_counter(); s = dom.eng.snapshot(); dt = time.perf_counter() - t
        gc.enable(); del s; gc.collect()
        res.setdefault(mode, []).append(dt)
for m, v in res.items():
    print(f"{m:10s} {st.median(v):.2f}s  {[round(x,2) for x in v]}")
