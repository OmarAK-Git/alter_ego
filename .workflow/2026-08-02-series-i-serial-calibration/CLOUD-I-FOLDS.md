# Series I Cloud Fold Chain Launch Brief

**Branch:** `series-i-serial-calibration`
**Phase:** B additive folds (main campaign)
**Harness:** `scratch/run_series_i_sweep.py --chunked` via `scratch/run_series_i_chunked.ps1`
**Seed:** 42 · **thr:** 45 · **config:** 2.2 (isolated per-step YAML)

## Policy

- **Folds are priority.** Serial additive — next fold starts only after prior metrics JSON lands.
- **Weight/solo probes** (`ws_volume_*`, `ws_fleet`, `ws_staged_drift`, local `ws_feat_volume`, `ws_precision_gate`): **do not kill.** Let in-flight lanes finish; DBs/logs/metrics are archival evidence for post-fold review. **Not a gate** for folds.
- **No new weight-search launches** until flag folds complete (volume-drift fold deferred last).
- **Cadence/geo:** skipped (aborted). Stay disabled.
- **calibrated:** false always. Do not merge to main.

## Fold order (flag folds first)

| # | Step | Overrides (additive on prior accepted) |
|---|---|---|
| 1 | `fold_02_feature_volume` | `features.total_volume_delta.enabled=true` |
| 2 | `fold_06_precision_gate` | + `precision_gate.enabled=true` |
| 3 | `fold_05_fleet` | + `cohort_gating_constants.fleet_drift_enabled=true` |
| 4 | `fold_07_staged_drift` | + `staged_drift.enabled=true` |
| 5 | `fold_03_drift_volume` | + `drift_weights.total_volume_delta.enabled=true` `weight=5.0` (provisional; confirm vs cloud `ws_volume_*` metrics after flag folds) |

Skipped: `fold_01_cadence`, `fold_04_geo`.

## One fold per cloud VM (full 21-day)

Launch **one agent per fold step**, serially. Do not start fold N+1 until `series_i_fold_*_metrics.json` exists for fold N.

### Example — fold 1

```bash
git fetch && git checkout series-i-serial-calibration
pip install -e ".[dev]"

while python scratch/run_series_i_sweep.py --step fold_02_feature_volume --chunked \
  --set features.total_volume_delta.enabled=true; test $? -eq 2; do :; done
```

### Example — fold 2 (after fold 1 accepted + metrics committed)

```bash
while python scratch/run_series_i_sweep.py --step fold_06_precision_gate --chunked \
  --set features.total_volume_delta.enabled=true \
  --set precision_gate.enabled=true; test $? -eq 2; do :; done
```

## Deliverables per fold

- `.workflow/2026-08-02-series-i-serial-calibration/results/series_i_<step>_metrics.json`
- Log: `.workflow/.../results/series_i_<step>_sweep.log`
- Governance: `results/scoring-config-governance-series-i-<step>.md` (accept/reject vs prior accepted baseline)

## Orchestrator (local watcher, optional)

```bash
python scratch/series_i_fold_chain.py --watch
```

Polls for metrics JSON, runs governance, chains next fold locally if cloud dispatch is manual.
