# Series G Cloud Sweep Status

| Field | Value |
|-------|-------|
| Branch | `cursor/series-g-calibration-20a2` (from `feature/drift-capability-expansion`) |
| Tip commit | `4a7eeb5` |
| Started | 2026-08-01T20:57:00Z |
| Completed | 2026-08-01T23:39:00Z |
| Mode | chunked (`--chunked`, 1 window/invocation) |
| Chunks | 20 / 20 |
| Metrics | `scratch/series_g_metrics.json` |
| Governance | `docs/scoring-config-governance-series-g.md` |

## Status

**DONE** — Series G calibration sweep completed successfully in cloud (~2h 42m wall time).

**Headline @ thr=45 (Series G only — do not compare to A/B/C/D/E/F):**
- P/R/F1: 0.0067 / 0.4615 / 0.0132
- TP/FP/FN: 54 / 7995 / 63

**Scenario recall:** S1=1.0, S2=0.74, S3=0.11, S4=1.0, S5=0.60

**Phase 3–4 signals:**
- `fleet_cohort_drift_decision_count`: 60
- `geo_velocity` mean delta_last_build: 0.0 (enabled in harness; no geo-velocity drift observed in this mix)
- S3 recall with fleet cohort drift: 0.111 (Series D archival baseline 0.444 — informational only, cross-series)

`config/scoring_config.yaml` enabled flags unchanged (harness used temporary sweep flags only).

## Artifacts copied

- `.workflow/2026-07-30-drift-capability-expansion/results/series_g_metrics.json`
- `.workflow/2026-07-30-drift-capability-expansion/results/scoring-config-governance-series-g.md`
- `.workflow/2026-07-30-drift-capability-expansion/results/series_g_sweep.log`

## Log

- **2026-08-01T20:57:00Z** — Relaunch after prior agent stall; STARTED status committed.
- **2026-08-01T20:57:47Z** — Chunked sweep launched (`run_series_g_chunked_loop.sh`).
- **2026-08-01T23:39:00Z** — **COMPLETE.** Metrics written; governance doc generated.
