# Series G Cloud Sweep Status

| Field | Value |
|-------|-------|
| Branch | `feature/drift-capability-expansion` |
| Tip commit | `8989f15` |
| Started | 2026-08-01T20:26:00Z |
| Completed | 2026-08-01T23:10:00Z |
| Mode | chunked (`--chunked`, 1 window/invocation) |
| Chunks | 21 / 22 |
| Metrics | `scratch/series_g_metrics.json` |
| DB | `alter_ego_calibrate_series_g.db` (isolated from F/H) |
| Governance | `docs/scoring-config-governance-series-g.md` |

## Summary

Series G calibration sweep completed successfully in cloud (~2h 44m wall time).

**Enabled flags (harness-only):** `fleet_drift_enabled=true`, `geo_velocity.enabled=true`. Committed YAML unchanged (`false`).

**Headline @ thr=45 (Series G only — do not compare to A/B/C/D/E/F):**
- P/R/F1: 0.0067 / 0.4615 / 0.0132
- TP/FP/FN: 54 / 7995 / 63

**Scenario recall:** S1=1.0, S2=0.74, S3=0.11, S4=1.0, S5=0.60

**Phase 3–4 signals:**
- `fleet_cohort_drift_decision_count`: 60
- `geo_velocity` mean delta_last_build: 0.0 (max 0.0, n=1300)
- `blocked_entity_count`: 53
- `active_alert_workflow_rows`: 6270

**S3 recall:** 0.111 (residual-risk baseline 0.667 — cross-series caution applies)

`config/scoring_config.yaml` enabled flags unchanged.

## Artifacts copied

- `.workflow/2026-07-30-drift-capability-expansion/results/series_g_metrics.json`
- `.workflow/2026-07-30-drift-capability-expansion/results/scoring-config-governance-series-g.md`
- `.workflow/2026-07-30-drift-capability-expansion/results/series_g_sweep.log`

## Log

- **2026-08-01T20:26:00Z** — Clean start; chunked sweep launched.
- **2026-08-01T20:27:00Z** — Chunk 0 complete; fixed loop (`PIPESTATUS[0]` for exit code). Resuming from checkpoint `2026-01-02`.
- **2026-08-01T23:10:00Z** — **COMPLETE.** Metrics written; governance doc generated.
