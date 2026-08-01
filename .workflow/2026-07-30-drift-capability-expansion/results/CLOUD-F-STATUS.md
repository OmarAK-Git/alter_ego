# Series F Cloud Sweep Status

| Field | Value |
|-------|-------|
| Branch | `feature/drift-capability-expansion` |
| Tip commit | `8989f15` |
| Started | 2026-08-01T20:26:22Z |
| Completed | 2026-08-01T23:08:34Z |
| Mode | chunked (`--chunked`, 1 window/invocation) |
| Chunks | 21 / 21 |
| Metrics | `scratch/series_f_metrics.json` |
| Governance | `docs/scoring-config-governance-series-f.md` |

## Summary

Series F calibration sweep completed successfully in cloud (~2h 42m wall time).

**Phases 1–2 enabled in harness only (cadence + total_volume_delta):**
- `blocked_entity_count`: 53
- `active_alert_workflow_rows`: 6270
- `auto_resolved_count`: 1810

**Headline @ thr=45 (Series F only — do not compare to A/B/C/D/E):**
- P/R/F1: 0.0067 / 0.4615 / 0.0132
- TP/FP/FN: 54 / 7995 / 63

**Scenario recall:** S1=1.0, S2=0.74, S3=0.11, S4=1.0, S5=0.60

**H4 cadence dominance check (per_dimension_drift_decomposition mean):**
- cadence: 0.288 (max 1.0)
- embedding: 0.019 (max 0.164)
- total_volume_delta: 0.041 (max 0.264)
- cadence/embedding mean ratio: ~14.9

`config/scoring_config.yaml` enabled flags unchanged (harness restores after sweep).

## Artifacts copied

- `.workflow/2026-07-30-drift-capability-expansion/results/series_f_metrics.json`
- `.workflow/2026-07-30-drift-capability-expansion/results/scoring-config-governance-series-f.md`
- `.workflow/2026-07-30-drift-capability-expansion/results/series_f_sweep.log`

## Log

- **2026-08-01T20:26:22Z** — Clean start; chunked sweep launched.
- **2026-08-01T20:32:00Z** — Chunks 0–2 complete (~3 min/chunk).
- **2026-08-01T20:55:00Z** — Chunk 7 complete; ~5 min/chunk.
- **2026-08-01T21:16:00Z** — Chunk 9 complete; ~7 min/chunk.
- **2026-08-01T21:46:00Z** — Chunk 13 complete; ~8–9 min/chunk.
- **2026-08-01T22:26:00Z** — Chunk 16 complete; ~10 min/chunk.
- **2026-08-01T23:08:34Z** — **COMPLETE.** Metrics written; governance doc generated.
- **2026-08-01T20:57:00Z** — Cloud agent F relaunch; STARTED heartbeat pushed (`f89c738`).
- **2026-08-01T23:37:00Z** — Relaunch sweep complete (20 chunks, ~2h 40m); metrics identical to prior run; `scratch/series_f_metrics.json` verified.
