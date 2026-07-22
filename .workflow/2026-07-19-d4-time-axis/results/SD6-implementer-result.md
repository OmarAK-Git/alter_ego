# SD6 implementer result — Series D sweep

**Packet:** SD6  
**Workflow:** `.workflow/2026-07-19-d4-time-axis/`  
**Status:** DONE_WITH_CONCERNS

## What ran

Full seed-42 Series D sweep via `scratch/run_series_d_sweep.py` (config v2.2, anomaly_threshold=45, R-INTERLOCK + D4 time-axis).

```powershell
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
python scratch/run_series_d_sweep.py
```

**Exit:** 0 (~437s wall)

## Files changed

| File | Rationale |
|------|-----------|
| `docs/calibration_series_d_metrics.json` | Promoted governance metrics from sweep |
| `.workflow/2026-07-19-d4-time-axis/results/SD6-sweep-result.md` | Full sweep report with required fields |
| `.workflow/2026-07-19-d4-time-axis/results/SD6-implementer-result.md` | This packet completion record |

**Not touched:** `config/scoring_config.yaml`, Series C metrics, SD7/EXIT gate.

## Verification

| Check | Result |
|-------|--------|
| Sweep exit code | 0 |
| `scratch/series_d_metrics.json` | written |
| `alter_ego_calibrate_series_d.db` | written |
| `docs/calibration_series_d_metrics.json` | promoted |

## Headlines

| Field | Value |
|-------|------:|
| D4 engagement | **12840** (Series C = 0) |
| P / R / F1 | 0.011 / 0.504 / 0.021 |
| S1→S5 recall | 1.0 / 0.714 / 0.444 / 0.0 / 0.371 |
| auto_resolved | 2269 |
| promotion_coverage_ever | 1.0 |
| promotion_coverage_in_window (N=5) | 0.413 |
| fallback_flag_count | 1084 |

## Acceptance signals

- [x] D4 engagement 0 → nonzero (only allowed C→D claim)
- [x] S2 drift_alert raw trajectory shows rising shadow-sourced drift (max 16.86 decision raw)
- [x] S2 stays blocked with visible shadow drift (137 active alerts at end)
- [x] Dual promotion_coverage metrics present
- [ ] Fallback count ~0 — **failed** (1084 global)

## Concerns

1. Global fallback-flag storm (1084) — revisit SD2 observability vs builder shadow timing.
2. Very low precision / high FP — topology shift, not claimed as calibrated improvement.
3. S2 recall 0.714 not full catch.

## Out of scope (not run)

- SD7 governance record
- EXIT gate (pytest + ruff + skeptic)

## Report back

**Status:** DONE_WITH_CONCERNS  
**Engagement:** 12840  
**P/R:** P=0.011, R=0.504  
**Paths:** `docs/calibration_series_d_metrics.json`, `.workflow/2026-07-19-d4-time-axis/results/SD6-sweep-result.md`
