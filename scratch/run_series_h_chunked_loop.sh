#!/usr/bin/env bash
# Run Series H chunked sweep until complete (exit 0) or hard failure.
set -u
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin:${PATH}"
LOG=".workflow/2026-07-30-drift-capability-expansion/results/series_h_sweep.log"
mkdir -p "$(dirname "$LOG")"
: >"$LOG"
for i in $(seq 0 39); do
  echo "=== Chunk $i $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  python3 scratch/run_series_h_sweep.py --chunked 2>&1 | tee -a "$LOG"
  code=${PIPESTATUS[0]}
  if [[ "$code" -eq 0 ]]; then
    echo "Series H complete at chunk $i" | tee -a "$LOG"
    exit 0
  fi
  if [[ "$code" -ne 2 ]]; then
    echo "Series H failed with exit $code at chunk $i" | tee -a "$LOG"
    exit "$code"
  fi
done
echo "Exceeded max chunks for Series H" | tee -a "$LOG"
exit 1
