# Series H Cloud Sweep Status

| Field | Value |
|-------|-------|
| Branch | `feature/drift-capability-expansion` |
| Tip commit | `8989f15` |
| Started | 2026-08-01T20:26:28Z |
| Completed | 2026-08-01T23:05:00Z |
| Mode | chunked (`--chunked`, 1 window/invocation) |
| Chunks | 21 / 21 |
| DB | `alter_ego_calibrate_series_h.db` (isolated from F/G) |
| Metrics | `scratch/series_h_metrics.json` |
| Governance | `docs/scoring-config-governance-series-h.md` |

## Summary

Series H calibration sweep completed successfully in cloud (~2h 39m wall time).

**Harness flags (subprocess only):** `precision_gate.enabled=true`, `staged_drift.enabled=true`  
**Committed YAML:** both remain `false` (verified post-sweep).

**Headline @ thr=45 (Series H only — do not compare to A/B/C/D/E/F/G):**
- P/R/F1: 0.0067 / 0.4615 / 0.0132
- TP/FP/FN: 54 / 7995 / 63
- `drift_alerts`: 31
- `blocked_entity_count`: 53
- `active_alert_workflow_rows`: 6270
- `auto_resolved_count`: 1810

**Scenario recall:** S1=1.0, S2=0.74, S3=0.11, S4=1.0, S5=0.60

**Signal-family agreement (Stage-B evidence):**
- benign FP: n=8026, mean=0.84, histogram {0: 1273, 1: 6753}
- TP: n=54, mean=1.0, histogram {1: 54}

## Artifacts copied

- `.workflow/2026-07-30-drift-capability-expansion/results/series_h_metrics.json`
- `.workflow/2026-07-30-drift-capability-expansion/results/scoring-config-governance-series-h.md`
- `.workflow/2026-07-30-drift-capability-expansion/results/series_h_sweep.log`

## Log

- **2026-08-01T20:26:28Z** — Clean start; chunked sweep launched (parallel with F/G, separate DB).
- **2026-08-01T20:32:00Z** — Chunks 0–2 complete (~2.5 min/chunk early windows).
- **2026-08-01T21:43:00Z** — Chunk 13 complete; ~8–10 min/chunk in attack-heavy windows.
- **2026-08-01T22:40:00Z** — Chunk 18 complete; final windows in progress.
- **2026-08-01T23:05:00Z** — **COMPLETE.** Metrics written at chunk 20; governance doc generated.
