"""Run one scheme's search1 suite on a custom query file: python run_with.py <repo> <queries.jsonl> <scheme> args...
Replaces amtp_dataset.search_single_queries (the loader every scheme uses) before the scheme's main()."""
import json, os, runpy, sys
repo, qfile, scheme, args = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
sys.path.insert(0, os.path.join(repo, "baselines"))
import amtp_dataset
qs = [json.loads(l) for l in open(qfile) if l.strip()]
amtp_dataset.search_single_queries = lambda: [dict(q) for q in qs]
if scheme == "amtp":
    os.chdir(os.path.join(repo, "amtp_code"))
    sys.path.insert(0, os.getcwd())
    sys.argv = ["experiments.py", "search1"] + args
    runpy.run_module("bench.experiments", run_name="__main__")
else:
    script = {"secollab": "se_collab_sim.py", "chen": "chen_et_al_sim.py", "du": "du_et_al_sim.py"}[scheme]
    os.chdir(os.path.join(repo, "baselines"))
    sys.argv = [script, "search1"] + args
    runpy.run_path(script, run_name="__main__")
