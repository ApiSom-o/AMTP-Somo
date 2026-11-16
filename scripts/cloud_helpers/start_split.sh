#!/bin/bash
# Start the search-only run (amtp_code/bench_split/run_cloud.sh, then exp5 through bench_split.run) on one cloud
# machine, from the Mac:   WANT=<short commit of main> BUNDLE=<bundle> bash scripts/cloud_helpers/start_split.sh <ip>      (CHECK_ONLY=1: no start)
# The job runs inside ~/split_cloud_worker.sh so that scripts/watch_stop.sh (which looks for "cloud_worker.sh")
# keeps the machine on while it runs and powers it off 10 min after it ends. Log: ~/split.log
set -u
ip=$1; K=${KEY:-$HOME/Downloads/amtp-key.pem}; WANT=${WANT:?set WANT}
BUNDLE=${BUNDLE:-$(dirname "$0")/newamtp_split.bundle}
scp -q -i $K -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$BUNDLE" ubuntu@${ip}:newamtp.bundle || { echo "copy of the bundle failed"; exit 1; }
ssh -i $K -o BatchMode=yes -o ConnectTimeout=10 ubuntu@${ip} bash -s -- "$WANT" "${CHECK_ONLY:-}" <<'REMOTE'
set -u; want=$1; check_only=${2:-}
cd ~/NewAMTP || { echo "no ~/NewAMTP"; exit 1; }
if pgrep -f '[c]loud_worker[.]sh|[b]ench[.]ablation|[b]ench[.]experiments|[b]ench_split' > /dev/null; then echo "a job is already running, not touching it"; exit 1; fi
git fetch -q origin 2>&1 && git checkout -q -B main origin/main || { echo "git update failed"; exit 1; }
head=$(git rev-parse --short HEAD); dirty=$(git status --porcelain --untracked-files=no | wc -l)
echo "commit $head dirty=$dirty cpus=$(nproc) mem=$(free -g | awk '/Mem/{print $2}')G disk_free=$(df -h ~ | awk 'NR==2{print $4}') data=$(ls data 2>/dev/null | tr '\n' ' ') matplotlib=$(.venv/bin/python -c 'import matplotlib;print(matplotlib.__version__)' 2>/dev/null || echo no)"
[ "$head" = "$want" ] || { echo "expected $want"; exit 1; }
[ "$dirty" = 0 ] || { echo "tracked files changed, not starting"; exit 1; }
ls amtp_code/bench_split/run_cloud.sh > /dev/null || { echo "no bench_split"; exit 1; }
[ -e baselines/results/runs/paper_split ] && { echo "runs/paper_split already exists, not overwriting"; exit 1; }
[ -n "$check_only" ] && { (cd amtp_code && ../.venv/bin/python -m pytest -q 2>&1 | tail -1); exit 0; }
cat > ~/split_cloud_worker.sh <<'JOB'
#!/bin/bash
cd ~/NewAMTP
RUN_NAME=paper_split bash amtp_code/bench_split/run_cloud.sh
rc=$?
if [ $rc -eq 0 ]; then
  cd amtp_code; R=../baselines/results/runs/paper_split; t0=$SECONDS
  echo "[$(date -u '+%F %T')] start exp5"
  if AMTP_PLACEMENT=fill AMTP_AND_PRUNE=1 AMTP_PART_RESULTS=1 AMTP_AND_GREEDY=1 ../.venv/bin/python -m bench_split.run exp5 --reps 15 --warmup 3 --out $R/amtp > $R/logs/exp5.log 2>&1; then
    echo "[$(date -u '+%F %T')] done  exp5 ($((SECONDS - t0)) s)"
  else
    echo "[$(date -u '+%F %T')] FAIL  exp5 (see logs/exp5.log)"; rc=1
  fi
fi
echo "split finished rc=$rc"
JOB
pkill -f '[w]atch_stop[.]sh' ; rm -f ~/watch_stop.log
nohup setsid bash ~/split_cloud_worker.sh > ~/split.log 2>&1 < /dev/null &
sleep 2
nohup setsid bash scripts/watch_stop.sh > ~/watch_stop.out 2>&1 < /dev/null &
sleep 4; echo "started: $(pgrep -fc '[c]loud_worker[.]sh') job, $(pgrep -fc '[w]atch_stop[.]sh') watch_stop"; head -4 ~/split.log
REMOTE
