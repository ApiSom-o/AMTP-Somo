"""Profile only DataUser.verify over the Search-1 queries of one domain at N = 100k (Mac)."""
import cProfile, pstats, sys, time
OUT = sys.argv[1]
sys.argv = ["x", "search1", "--s-domains", "D1", "--fpd", "100000", "--reps", "1", "--warmup", "0",
            "--out", OUT]
import bench.experiments as E
from amtp.user import DataUser
prof = cProfile.Profile()
orig = DataUser.verify
calls = {"n": 0, "t": 0.0}
def verify(self, ctx, resp):
    t = time.perf_counter(); prof.enable()
    try:
        return orig(self, ctx, resp)
    finally:
        prof.disable(); calls["n"] += 1; calls["t"] += time.perf_counter() - t
DataUser.verify = verify
E.main()
print("verify calls", calls["n"], "total s", round(calls["t"], 3))
prof.dump_stats(OUT + "/verify.prof")
pstats.Stats(prof).sort_stats("tottime").print_stats(25)
