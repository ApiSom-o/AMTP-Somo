#!/bin/bash
# Local watcher for the AMTP ex1-2 runs with γ without v (w3, w5, w6, run folder paper_v_exp3fix):
# every 3 min report new done / FAIL lines; when a worker's job has ended, copy paper_v_exp3fix and its log here.
K=~/Desktop/amtp_cloud/amtp-key.pem
DEST=${REPO:-$HOME/Desktop/newAMTP/NewAMTP}/baselines/results/runs/cloud
WS=(4); IPS=(43.209.20.195)
while true; do
  left=0
  for i in 0; do
    w=${WS[$i]}; ip=${IPS[$i]}
    [ -f "$DEST/.pulled_exp3fix_w$w" ] && continue
    left=$((left + 1))
    out=$(ssh -n -i $K -o BatchMode=yes -o ConnectTimeout=8 ubuntu@$ip \
      "grep -E 'done |FAIL|worker done|failed:' ~/exp3fix_w$w.log | grep -v ' check_'; echo JOBS=\$(pgrep -fc '[/]exp3fix[.]sh') END=\$(grep -cE 'worker done|failed:' ~/exp3fix_w$w.log)" 2>/dev/null) || {
      [ -z "${unr[$w]:-}" ] && echo "worker $w (ex3 fix): unreachable"; unr[$w]=1; continue; }
    unr[$w]=""
    body=$(grep -v '^JOBS=' <<< "$out"); n=$(grep -c . <<< "$body")
    s=$(cat "$DEST/.seen_exp3fix_w$w" 2>/dev/null || echo 0)
    if [ "$n" -gt "$s" ]; then
      tail -n $((n - s)) <<< "$body" | sed "s/^/worker $w (ex3 fix): /"
      echo $n > "$DEST/.seen_exp3fix_w$w"
    fi
    if grep -q 'JOBS=0 END=[1-9]' <<< "$out"; then
      mkdir -p "$DEST/w$w"
      if rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${ip}:NewAMTP/baselines/results/runs/paper_v_exp3fix" "$DEST/w$w/" \
         && rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@${ip}:exp3fix_w$w.log" "$DEST/w$w/"; then
        touch "$DEST/.pulled_exp3fix_w$w"
        echo "worker $w (ex3 fix): FINISHED, copied to runs/cloud/w$w/paper_v_exp3fix (powers off in ~10 min)"
      else
        echo "worker $w (ex3 fix): finished but copy failed, retrying"
      fi
    fi
  done
  [ "$left" -eq 0 ] && { echo "ex3 fix: worker 4 finished and copied"; exit 0; }
  sleep 180
done
