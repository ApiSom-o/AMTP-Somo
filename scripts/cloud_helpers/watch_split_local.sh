#!/bin/bash
# Mac watcher for the search-only run: every 3 min report new done / FAIL lines of ~/split.log; when the job has
# ended, copy runs/paper_split and the log to runs/cloud/split_w1/ (before the machine powers itself off).  IP=<ip>
K=${KEY:-$HOME/Downloads/amtp-key.pem}
DEST=${REPO:?set REPO}/baselines/results/runs/cloud
seen=0; unr=""
while true; do
  out=$(ssh -n -i $K -o BatchMode=yes -o ConnectTimeout=8 ubuntu@${IP} \
    "grep -E 'done |FAIL|worker done|failed:|split finished' ~/split.log; echo JOBS=\$(pgrep -fc '[c]loud_worker[.]sh') END=\$(grep -c 'split finished' ~/split.log)" 2>/dev/null) || {
    [ -z "$unr" ] && echo "$(date '+%H:%M') split: unreachable"; unr=1; sleep 180; continue; }
  [ -n "$unr" ] && echo "$(date '+%H:%M') split: reachable again"; unr=""
  body=$(grep -v '^JOBS=' <<< "$out"); n=$(grep -c . <<< "$body")
  if [ "$n" -gt "$seen" ]; then tail -n $((n - seen)) <<< "$body" | sed "s/^/split: /"; seen=$n; fi
  if grep -q 'JOBS=0 END=[1-9]' <<< "$out"; then
    mkdir -p "$DEST/split_w1"
    if rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${IP}:NewAMTP/baselines/results/runs/paper_split" "$DEST/split_w1/" \
       && rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${IP}:split.log" "$DEST/split_w1/"; then
      echo "$(date '+%H:%M') split: FINISHED, copied to runs/cloud/split_w1 (powers off in ~10 min)"; exit 0
    fi
    echo "split: finished but copy failed, retrying"
  fi
  sleep 180
done
