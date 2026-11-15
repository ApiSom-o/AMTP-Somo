#!/bin/bash
# ex3 (update cost) AMTP, γ with v, after the Validator fix (a131032); same command as the paper_v run
cd ~/NewAMTP/amtp_code
OUT=~/NewAMTP/baselines/results/runs/paper_v_exp3fix/amtp
mkdir -p "$OUT"
echo "[$(date '+%F %T')] start exp3fix commit $(git rev-parse --short HEAD) dirty=$(git status --porcelain | wc -l)"
s=$(date +%s)
if ../.venv/bin/python -m bench.experiments exp3 --reps 15 --warmup 3 --sizes 100000 --batches 1 10 100 1000 --out "$OUT"; then
  echo "[$(date '+%F %T')] done  exp3fix ($(( $(date +%s) - s )) s)"; echo "worker done: exp3fix"
else
  echo "[$(date '+%F %T')] FAIL exp3fix"; echo "failed: exp3fix"
fi
