#!/bin/bash
# Local watcher (bash 3.2): every 3 min, report new done / FAIL lines of each worker's calibration and real logs;
# when a worker's real run has finished, copy all its run folders and logs here (before it powers itself off).
K=~/Desktop/amtp_cloud/amtp-key.pem
DEST=${REPO:-$HOME/Desktop/newAMTP/NewAMTP}/baselines/results/runs/cloud
IPS=(43.208.153.230 43.210.202.226 43.211.65.129 43.210.74.245 43.211.35.247 43.209.191.246 43.209.127.240 43.208.93.209 43.208.200.8 43.210.145.9)
mkdir -p "$DEST"
seen=(0 0 0 0 0 0 0 0 0 0 0); pulled=(0 0 0 0 0 0 0 0 0 0 0); unr=("" "" "" "" "" "" "" "" "" "" "")
for w in 1 2 3 4 5 6 7 8 9 10; do                     # state survives a restart of this watcher
  [ -f "$DEST/.seen_w$w" ] && seen[$w]=$(cat "$DEST/.seen_w$w")
  [ -f "$DEST/.pulled_w$w" ] && pulled[$w]=1
done
while true; do
  left=0
  for i in 0 1 2 3 4 5 6 7 8 9; do
    w=$((i + 1)); ip=${IPS[$i]}
    [ "${pulled[$w]}" = 1 ] && continue
    left=$((left + 1))
    out=$(ssh -i $K -o BatchMode=yes -o ConnectTimeout=8 ubuntu@$ip \
      "cat ~/calib_w$w.log ~/real_w$w.log 2>/dev/null | grep -E 'done |FAIL|worker done|failed:' | grep -v ' check_'; echo JOBS=\$(pgrep -fc 'cloud_worker[.]sh') REAL=\$(grep -cE 'worker done|failed:' ~/real_w$w.log 2>/dev/null)" 2>/dev/null) || {
      [ -z "${unr[$w]:-}" ] && echo "worker $w: unreachable (powered off, or SSH blocked)"; unr[$w]=1; continue; }
    unr[$w]=""
    body=$(grep -v '^JOBS=' <<< "$out")
    n=$(grep -c . <<< "$body")
    if [ "$n" -gt "${seen[$w]}" ]; then
      tail -n $((n - ${seen[$w]})) <<< "$body" | sed "s/^/worker $w: /"
      seen[$w]=$n; echo $n > "$DEST/.seen_w$w"
    fi
    if grep -q 'JOBS=0 REAL=[1-9]' <<< "$out"; then
      mkdir -p "$DEST/w$w"
      if rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@$ip:NewAMTP/baselines/results/runs/" "$DEST/w$w/" \
         && rsync -aq -e "ssh -i $K -o BatchMode=yes" "ubuntu@$ip:calib_w$w.log" "ubuntu@$ip:real_w$w.log" "$DEST/w$w/"; then
        pulled[$w]=1; touch "$DEST/.pulled_w$w"
        echo "worker $w: ALL DONE, results copied to runs/cloud/w$w (machine powers off in ~10 min)"
      else
        echo "worker $w: finished but copy failed, retrying"
      fi
    fi
  done
  [ "$left" -eq 0 ] && { echo "all 10 workers finished and copied"; exit 0; }
  sleep 180
done
