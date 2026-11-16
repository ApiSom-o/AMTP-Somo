#!/bin/bash
# Start plan "prune" (scripts/cloud_worker.sh, PLAN=prune) on one cloud machine, from the Mac:
#   git bundle create newamtp.bundle 7485556..main     # the machines have no GitHub access: origin = ~/newamtp.bundle
#   BUNDLE=newamtp.bundle WANT=<short commit> bash scripts/cloud_helpers/start_prune.sh <plan worker 1..5> <ip>
# Copies the bundle, checks out main, refuses if a job is running, the commit differs or tracked files changed,
# runs pytest, then starts the plan and scripts/watch_stop.sh. CHECK_ONLY=1: everything except the start.
# Log on the machine: ~/prune_w<N>.log; results: ~/NewAMTP/baselines/results/runs/paper_prune_v/
set -u
w=$1; ip=$2; K=${KEY:-$HOME/Downloads/amtp-key.pem}; WANT=${WANT:?set WANT to the expected short commit}
BUNDLE=${BUNDLE:-newamtp.bundle}
scp -q -i $K -o BatchMode=yes -o ConnectTimeout=10 "$BUNDLE" ubuntu@${ip}:newamtp.bundle || { echo "w$w: copy of the bundle failed"; exit 1; }
ssh -i $K -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new ubuntu@${ip} bash -s -- "$w" "$WANT" "${CHECK_ONLY:-}" <<'REMOTE'
set -u; w=$1; want=$2; check_only=${3:-}
cd ~/NewAMTP || { echo "w$w: no ~/NewAMTP"; exit 1; }
if pgrep -f '[c]loud_worker[.]sh|[b]ench[.]ablation|[b]ench[.]experiments' > /dev/null; then echo "w$w: a job is already running, not touching it"; exit 1; fi
git fetch -q origin 2>&1 && git checkout -q -B main origin/main || { echo "w$w: git update failed"; exit 1; }
head=$(git rev-parse --short HEAD); dirty=$(git status --porcelain --untracked-files=no | wc -l)
echo "w$w: commit $head dirty=$dirty cpus=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G disk_free=$(df -h ~ | awk 'NR==2{print $4}') data=$(ls data 2>/dev/null | tr '\n' ' ')"
[ "$head" = "$want" ] || { echo "w$w: expected $want"; exit 1; }
[ "$dirty" = 0 ] || { echo "w$w: tracked files changed, not starting"; exit 1; }
(cd amtp_code && ../.venv/bin/python -m pytest -q 2>&1 | tail -1)
[ -n "$check_only" ] && exit 0
pkill -f '[w]atch_stop[.]sh' ; rm -f ~/watch_stop.log
nohup setsid bash -c "PLAN=prune RUN_NAME=paper_prune bash scripts/cloud_worker.sh $w > ~/prune_w$w.log 2>&1" < /dev/null > /dev/null 2>&1 &
sleep 2
nohup setsid bash scripts/watch_stop.sh > ~/watch_stop.out 2>&1 < /dev/null &
sleep 3; echo "w$w: started: $(pgrep -fc '[c]loud_worker[.]sh') worker, $(pgrep -fc '[w]atch_stop[.]sh') watch_stop"; head -3 ~/prune_w$w.log
REMOTE
