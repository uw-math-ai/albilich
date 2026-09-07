#!/bin/zsh
# Evaluate Albilich on the staged RealMath Math_arXiv problems.
# Model gpt-5.6-sol @ xhigh, hard_problem mode. Runs are intentionally sequential.
set -euo pipefail

SCRIPT_DIR=${0:A:h}
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
cd "$REPO_ROOT"
BASE="$SCRIPT_DIR"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$BASE/results" "$BASE/logs"
for md in "$BASE"/problems/realmath_*.md; do
  id=$(basename "$md" .md)
  pid="benchmarks/realmath_matharxiv_10/$id"
  report="$BASE/results/${id}_report.md"
  [ -f "$report" ] && { echo "[skip] $id (already collected)"; continue; }
  echo "[init] $id  $(date +%H:%M:%S)"
  python3 -m agents.generation.phase2.cli init "$md" --problem-id "$pid" \
      --total-token-budget 50000000 --reserved-verification-budget 6000000 \
      > "$BASE/logs/${id}_init.json" 2>&1
  echo "[run ] $id  $(date +%H:%M:%S)"
  python3 -m agents.generation.phase2.cli run "$pid" --execute --steps 10 \
      --model gpt-5.6-sol --reasoning-effort xhigh --research-mode hard_problem \
      --write-report --no-dashboard --no-stop-on-rejection \
      > "$BASE/logs/${id}_run.json" 2> "$BASE/logs/${id}_run.log"
  src="agents/generation/results/$pid/phase2/phase2_report.md"
  if [ -f "$src" ]; then
    cp "$src" "$report"
    echo "[done] $id -> $report"
  else
    echo "[warn] $id produced no report"
  fi
done
echo "BENCH SWEEP COMPLETE $(date)"
