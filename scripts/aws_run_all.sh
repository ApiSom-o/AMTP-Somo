#!/usr/bin/env bash
# Run the advisor's experiment plan (dataset-v4) for every scheme on one machine, one job at a time.
#
#   bash scripts/aws_run_all.sh                 # every step below, in order
#   bash scripts/aws_run_all.sh search1 tamper  # only these steps
#
# Steps (each scheme writes baselines/results/<scheme>/<scheme>_<suite>.csv + .manifest.json):
#   check       dataset-v4 present, unit tests, selftests
#   search1     Search 1.1 / 1.2   single domain, AND queries, files/domain 10k..125k      (4 schemes)
#   verify1     Verify 1.1         single domain, real keywords with ~10..10,000 results    (4 schemes)
#   tamper      Verify 1.2         server modifies / hides / injects / sends old versions of t of ~2,000
#                                  results; early-abort and full-check time, files named      (4 schemes)
#   xsearch     Search 2.1         Boolean AND / OR queries over the 4 domains               (AMTP, SE-COLLAB)
#   xverify     Verify 2.1         multi-domain keywords with ~10..10,000 results            (AMTP, SE-COLLAB)
#   xdomains    Search / Verify 2.2  the same files as D = 1..32 domains, kQ = XD_KQ, shapes XD_SHAPES (AMTP, SE-COLLAB)
#   update      update cost at N = UPDATE_SIZES: one epoch of b signed requests, b in UPDATE_B;
#               AMTP times CS prepare / owner Validator / anchor apart                     (AMTP, Chen)
#   theta       θ sweep: query vs update cost
#   splitmerge  split / merge: start with SM_N files, insert as many again (95% into one hot group), then delete
#               65% of the hot group; θ_max = 64/128/256; layout + queries every SM_QUERY_EVERY batches
#               (AMTP vs Static-MT vs Global-MT); one batch of SM_B updates = one epoch (b, recorded in the CSV)
#
# Settings (environment variables, defaults below). Commit the code first: every manifest records the
# git commit and git_dirty. Logs go to $LOGS; a failed step is reported at the end, the others still run.
set -u
cd "$(dirname "$0")/.."
REPO=$(pwd)
PY=${PY:-$REPO/.venv/bin/python}
REPS=${REPS:-30}
WARMUP=${WARMUP:-3}
LOGS=${LOGS:-$HOME/amtp_logs}
CHEN_OPTS=${CHEN_OPTS:---scope full --edb memory}     # full index in RAM; use "--scope auto" if RAM runs out
SE_OPTS=${SE_OPTS:---proof-mode multi}
UPDATE_SIZES=${UPDATE_SIZES:-100000}                   # N (files from all 4 domains in one AMTP domain)
UPDATE_B=${UPDATE_B:-1 10 100 1000}                    # b = signed requests per epoch
XD_KQ=${XD_KQ:-4}                                      # xdomains: query kQ kept
XD_SHAPES=${XD_SHAPES:-AND}                            # xdomains: query shapes kept
THETA_N=${THETA_N:-200000}                           # needs shared exp1_queries.json at this N (10k..200k)
THETA_VALUES=${THETA_VALUES:-64 128 256}
SM_N=${SM_N:-100000}                                   # split / merge: initial files (all 4 domains, one AMTP domain)
SM_B=${SM_B:-100}                                      # b: updates per batch = per epoch (b = 1 is ~2.4x slower)
SM_BATCHES=${SM_BATCHES:-1000}                         # x SM_B files inserted = SM_N (+100%), from the next initial files
SM_SKEWS=${SM_SKEWS:-0.95}                             # share of new files forced into the hot group
SM_RUNS=${SM_RUNS:-3}
SM_HOT_DELETE=${SM_HOT_DELETE:-0.65}                   # then delete this share of the hot group's files
SM_THETAS=${SM_THETAS:-64 128 256}
SM_QUERY_EVERY=${SM_QUERY_EVERY:-100}
mkdir -p "$LOGS"
COMMON="--reps $REPS --warmup $WARMUP"
FAILED=()

run() {                     # run <name> <dir> <command...>: log to $LOGS/<name>.log, keep going on failure
  local name=$1 dir=$2; shift 2
  echo "[$(date '+%F %T')] start $name"
  if (cd "$REPO/$dir" && "$@") > "$LOGS/$name.log" 2>&1; then
    echo "[$(date '+%F %T')] done  $name"
  else
    echo "[$(date '+%F %T')] FAIL  $name (see $LOGS/$name.log)"
    FAILED+=("$name")
  fi
}

step_check() {
  run check_dataset baselines "$PY" amtp_dataset.py
  run check_pytest amtp_code "$PY" -m pytest -q
  run check_chen baselines "$PY" chen_et_al_sim.py selftest
  run check_secollab baselines "$PY" se_collab_sim.py selftest
  run check_du baselines "$PY" du_et_al_sim.py demo
}
step_search1() {
  run search1_amtp amtp_code "$PY" -m bench.experiments search1 $COMMON
  run search1_chen baselines "$PY" chen_et_al_sim.py search1 $COMMON $CHEN_OPTS
  run search1_du baselines "$PY" du_et_al_sim.py search1 $COMMON
  run search1_secollab baselines "$PY" se_collab_sim.py search1 $COMMON
}
step_verify1() {
  run verify1_amtp amtp_code "$PY" -m bench.experiments verify1 $COMMON
  run verify1_chen baselines "$PY" chen_et_al_sim.py verify1 $COMMON $CHEN_OPTS
  run verify1_du baselines "$PY" du_et_al_sim.py verify1 $COMMON
  run verify1_secollab baselines "$PY" se_collab_sim.py verify1 $COMMON $SE_OPTS
}
step_tamper() {
  run tamper_amtp amtp_code "$PY" -m bench.experiments tamper $COMMON
  run tamper_chen baselines "$PY" chen_et_al_sim.py tamper $COMMON $CHEN_OPTS
  run tamper_du baselines "$PY" du_et_al_sim.py tamper $COMMON
  run tamper_secollab baselines "$PY" se_collab_sim.py tamper $COMMON $SE_OPTS
}
step_xsearch() {
  run xsearch_amtp amtp_code "$PY" -m bench.experiments xsearch $COMMON
  run xsearch_secollab baselines "$PY" se_collab_sim.py xsearch $COMMON $SE_OPTS
}
step_xverify() {
  run xverify_amtp amtp_code "$PY" -m bench.experiments xverify $COMMON
  run xverify_secollab baselines "$PY" se_collab_sim.py xverify $COMMON $SE_OPTS
}
step_xdomains() {
  run xdomains_amtp amtp_code "$PY" -m bench.experiments xdomains $COMMON --x-kq $XD_KQ --shapes $XD_SHAPES
  run xdomains_secollab baselines "$PY" se_collab_sim.py xdomains $COMMON $SE_OPTS --x-kq $XD_KQ --shapes $XD_SHAPES
}
step_update() {
  run update_amtp amtp_code "$PY" -m bench.experiments exp3 $COMMON --sizes $UPDATE_SIZES --batches $UPDATE_B
  run update_chen baselines "$PY" chen_et_al_sim.py exp3 $COMMON --sizes $UPDATE_SIZES --batches $UPDATE_B
}
step_theta() {
  run theta_amtp amtp_code "$PY" -m bench.experiments theta $COMMON --n "$THETA_N" --theta-values $THETA_VALUES
}
step_splitmerge() {
  local t
  for t in $SM_THETAS; do
    run "splitmerge_t$t" amtp_code "$PY" -m bench.ablation --source arxiv --n "$SM_N" \
      --theta-max "$t" --theta-min $((t / 4)) --batches "$SM_BATCHES" --batch-size "$SM_B" --delete-frac 0 \
      --fresh-source initial --skews "$SM_SKEWS" --runs "$SM_RUNS" --hot-delete-frac "$SM_HOT_DELETE" \
      --query-every "$SM_QUERY_EVERY" \
      --out "../baselines/results/amtp/splitmerge_n${SM_N}_t${t}"
  done
}

STEPS=("$@")
[ ${#STEPS[@]} -eq 0 ] && STEPS=(check search1 verify1 tamper xsearch xverify xdomains update theta splitmerge)
echo "commit $(git rev-parse --short HEAD), uncommitted changes: $(git status --porcelain --untracked-files=no | wc -l)"
for s in "${STEPS[@]}"; do
  "step_$s"
done
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "all steps finished"
else
  echo "failed: ${FAILED[*]}"
  exit 1
fi
