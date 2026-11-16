#!/bin/bash
# Mac watcher for plan "prune": every 3 min report new done / FAIL lines; when a worker has finished, copy its
# paper_prune_v folder and log to runs/cloud/prune_w<N>/ (before it powers itself off).  IPS="ip1 ip2 ip3 ip4 ip5"
K=${KEY:-$HOME/Downloads/amtp-key.pem}
DEST=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}/baselines/results/runs/cloud
read -r -a IPS <<< "$IPS"
while true; do
  left=0
  for i in 0 1 2 3 4; do
    w=$((i + 1)); ip=${IPS[$i]}
    [ -f "$DEST/.pulled_prune_w$w" ] && continue
    left=$((left + 1))
    out=$(ssh -n -i $K -o BatchMode=yes -o ConnectTimeout=8 ubuntu@${ip} \
      "grep -E 'done |FAIL|worker done|failed:' ~/prune_w$w.log | grep -v ' check_'; echo JOBS=\$(pgrep -fc '[c]loud_worker[.]sh') END=\$(grep -cE 'worker done|failed:' ~/prune_w$w.log)" 2>/dev/null) || {
      [ -z "$(eval echo \${unr$w:-})" ] && echo "$(date '+%H:%M') worker $w: unreachable"; eval unr$w=1; continue; }
    eval unr$w=""
    body=$(grep -v '^JOBS=' <<< "$out"); n=$(grep -c . <<< "$body")
    s=$(cat "$DEST/.seen_prune_w$w" 2>/dev/null || echo 0)
    if [ "$n" -gt "$s" ]; then
      tail -n $((n - s)) <<< "$body" | sed "s/^/worker $w: /"; echo $n > "$DEST/.seen_prune_w$w"
    fi
    if grep -q 'JOBS=0 END=[1-9]' <<< "$out"; then
      mkdir -p "$DEST/prune_w$w"
      if rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${ip}:NewAMTP/baselines/results/runs/paper_prune_v" "$DEST/prune_w$w/" \
         && rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${ip}:prune_w$w.log" "$DEST/prune_w$w/"; then
        touch "$DEST/.pulled_prune_w$w"; echo "$(date '+%H:%M') worker $w: FINISHED, copied to runs/cloud/prune_w$w (powers off in ~10 min)"
      else
        echo "worker $w: finished but copy failed, retrying"
      fi
    fi
  done
  [ "$left" -eq 0 ] && { echo "plan prune: all 5 workers finished and copied"; exit 0; }
  sleep 180
done
