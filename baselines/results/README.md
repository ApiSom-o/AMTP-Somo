# Results

One folder per paper. Every scheme runs on arXiv dataset-v4 with `--reps 30 --warmup 3`.

```
results/
  exp1_queries.json   shared Exp. 1 queries, replayed by every scheme (stays at this level)
  exp2_layouts.json   shared Exp. 2 layouts: which files get the marker keyword (clustered / dispersed / partition_spread)
  exp5_workload.json  shared Exp. 5 workload: 32 domains x 5,000 files, queries of the target domain, update files
  amtp/               AMTP (amtp_code/bench/experiments.py)  amtp_<suite>.csv  + figures/
  chen/               Chen et al. [40]   chen_<suite>.csv      + figures/
  du/                 Du et al. [7]      du_<suite>.csv        + figures/
  secollab/           SE-COLLAB [37]     secollab_<suite>.csv  + figures/
  compare/            every scheme of an experiment in one graph (compare_*, see ../README.md "Figures")
  runs/<run>/         one run of scripts/aws_run_all.sh (git-ignored): <scheme>/ CSVs, amtp/splitmerge_*/, logs/,
                      figures/ from  python3 baselines/plot_paper.py baselines/results/runs/<run>
```

| Paper | Exp. 1 search | Exp. 2 proof / verify | Exp. 3 update | Exp. 5 domains | other |
|---|---|---|---|---|---|
| AMTP (`amtp/`) | ✓ all shapes | ✓ 3 shared layouts | ✓ | ✓ 1..32 domains | Exp. 4 ablation (`exp4*/`), θ sweep |
| Chen [40] (`chen/`) | ✓ AND only | ✓ 3 shared layouts | ✓ | – (one data owner, no domains) | |
| Du [7] (`du/`) | ✓ AND only | ✓ reference (3 shared layouts) | N/A | – (one data owner, no domains) | `du_clouds_sensitivity.csv`: 4..32 clouds, N = 10k |
| SE-COLLAB [37] (`secollab/`) | ✓ all shapes | ✓ 3 shared layouts | N/A | ✓ 1 owner = 1 domain (update N/A) | |

- The simulators write to their own folder by default (`--out` overrides it).
- `python3 plot_results.py amtp chen du secollab` writes each scheme's figures to `<scheme>/figures/` and the
  cross-scheme figures to `compare/`.
- `chen/figures/` files without the `chen_` prefix (including the Exp. 3 figures) came from Chen's original plot
  script and are kept as they are.
