#!/usr/bin/env bash
# Run Series F calibration sweep one day-window per invocation until complete.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LOG="scratch/series_f_chunked_run.log"
SCRIPT="scratch/run_series_f_sweep.py"

echo "=== Series F chunked sweep started $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"

for i in $(seq 0 39); do
  echo "=== Chunk $i $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  python3 "$SCRIPT" --chunked 2>&1 | tee -a "$LOG"
  code=${PIPESTATUS[0]}
  if [[ $code -eq 0 ]]; then
    echo "Series F complete at chunk $i $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
    exit 0
  fi
  if [[ $code -ne 2 ]]; then
    echo "Series F failed with exit $code at chunk $i" | tee -a "$LOG"
    exit "$code"
  fi
done

echo "Exceeded max chunks for Series F" | tee -a "$LOG"
exit 1
