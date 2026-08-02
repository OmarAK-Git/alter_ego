# Series I Cloud Probe Launch Brief

**Branch:** `series-i-serial-calibration` (push with `-u` before cloud checkout)
**Harness:** `scratch/run_series_i_sweep.py --chunked` via `scratch/run_series_i_chunked.ps1`
**Seed:** 42 · **thr:** 45 · **config:** 2.2 (isolated per-step YAML)

## One probe per VM (full 21-day, no screening)

| Step | Overrides | Resume checkpoint | Partial DB (copy from operator machine) |
|---|---|---|---|
| `ws_volume_1` | `drift_weights.total_volume_delta.enabled=true` `weight=1.0` | `scratch/series_i_ws_volume_1_checkpoint.json` → `2026-01-11` | `alter_ego_calibrate_series_i_ws_volume_1.db` |
| `ws_volume_5` | `drift_weights.total_volume_delta.enabled=true` `weight=5.0` | `scratch/series_i_ws_volume_5_checkpoint.json` | `alter_ego_calibrate_series_i_ws_volume_5.db` |
| `ws_volume_15` | `drift_weights.total_volume_delta.enabled=true` `weight=15.0` | `scratch/series_i_ws_volume_15_checkpoint.json` | `alter_ego_calibrate_series_i_ws_volume_15.db` |
| `ws_staged_drift` | `staged_drift.enabled=true` | `scratch/series_i_ws_staged_drift_checkpoint.json` | `alter_ego_calibrate_series_i_ws_staged_drift.db` |
| `ws_fleet` | `cohort_gating_constants.fleet_drift_enabled=true` | `scratch/series_i_ws_fleet_checkpoint.json` | `alter_ego_calibrate_series_i_ws_fleet.db` |

Local partial progress through sim-day **2026-01-10** (~10/21 windows). Copy DB + checkpoint to cloud workspace root to avoid redoing finished days.

## Example (Linux cloud VM)

```bash
git fetch && git checkout series-i-serial-calibration
pip install -e ".[dev]"
# copy partial DB + checkpoint from operator artifact bundle into repo root + scratch/

pwsh scratch/run_series_i_chunked.ps1 -Step ws_volume_1 -Set @(
  'drift_weights.total_volume_delta.enabled=true',
  'drift_weights.total_volume_delta.weight=1.0'
)
```

Or loop manually:

```bash
while python scratch/run_series_i_sweep.py --step ws_volume_1 --chunked \
  --set drift_weights.total_volume_delta.enabled=true \
  --set drift_weights.total_volume_delta.weight=1.0; test $? -eq 2; do :; done
```

## Deliverables per probe

- `.workflow/2026-08-02-series-i-serial-calibration/results/series_i_<step>_metrics.json`
- Log: `.workflow/.../results/series_i_<step>_sweep.log`

Do **not** merge to `main`. Do **not** claim CALIBRATED.
