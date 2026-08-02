# Series E Cloud Sweep Status

| Field | Value |
|-------|-------|
| Branch | `feature/drift-capability-expansion` |
| Tip commit | `00b79b4` |
| Started | 2026-08-01T00:31:00Z |
| Completed | 2026-08-01T04:47:35Z |
| Mode | chunked (`--chunked`, 1 window/invocation) |
| Chunks | 22 / 22 |
| Metrics | `scratch/series_e_metrics.json` |
| Governance | `docs/scoring-config-governance-series-e.md` |

## Summary

Series E calibration sweep completed successfully in cloud (~4h 16m wall time).

**Phase 0 isolated metrics:**
- `blocked_entity_count`: 53
- `active_alert_workflow_rows`: 6270
- `point_baseline_shadow_engaged_count`: 13526
- `blocked_entity_anomaly_count`: 8023

**Headline @ thr=45 (Series E only — do not compare to A/B/C/D):**
- P/R/F1: 0.0067 / 0.4615 / 0.0132
- TP/FP/FN: 54 / 7995 / 63

**Scenario recall:** S1=1.0, S2=0.74, S3=0.11, S4=1.0, S5=0.60

`config/scoring_config.yaml` enabled flags unchanged. No commit of results (operator can pull from cloud workspace artifacts).

## Artifacts copied

- `.workflow/2026-07-30-drift-capability-expansion/results/series_e_metrics.json`
- `.workflow/2026-07-30-drift-capability-expansion/results/scoring-config-governance-series-e.md`
- `.workflow/2026-07-30-drift-capability-expansion/results/series_e_sweep.log`

## Log

- **2026-08-01T00:31:00Z** — Clean start; chunked sweep launched.
- **2026-08-01T00:38:00Z** — Fixed loop script (`python3`, `set -e` on exit 2).
- **2026-08-01T01:06:00Z** — Rewrote loop script; chunks advancing correctly.
- **2026-08-01T04:47:35Z** — **COMPLETE.** Metrics written; governance doc generated.
