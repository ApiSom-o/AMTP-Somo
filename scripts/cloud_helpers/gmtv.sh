#!/bin/bash
# Global-MT(v) + Global-MT split / merge, θ = 64, γ with v; same settings as w1 (commit 7485556) apart from --variants
cd ~/NewAMTP/amtp_code
OUT=~/NewAMTP/baselines/results/runs/paper_v_gmtv/amtp/splitmerge_n100000_t64
mkdir -p "$OUT"
echo "[$(date '+%F %T')] start gmtv_t64 commit $(git rev-parse --short HEAD) dirty=$(git status --porcelain | wc -l)"
s=$(date +%s)
if ../.venv/bin/python -m bench.ablation --source arxiv --n 100000 --theta-max 64 --theta-min 16 \
     --batches 1000 --batch-size 100 --delete-frac 0 --fresh-source initial --skews 0.95 --runs 1 \
     --hot-delete-frac 0.65 --query-every 100 --variants "Global-MT(v),Global-MT" --out "$OUT"; then
  echo "[$(date '+%F %T')] done  gmtv_t64 ($(( $(date +%s) - s )) s)"; echo "worker done: gmtv"
else
  echo "[$(date '+%F %T')] FAIL gmtv_t64"; echo "failed: gmtv"
fi
