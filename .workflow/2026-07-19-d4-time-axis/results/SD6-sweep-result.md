# SD6 Series D Sweep Result

**Date:** 2026-07-19  
**Status:** DONE_WITH_CONCERNS (exit 0)  
**Calibrated claim:** **NOT CALIBRATED** — new Series D baseline only.

## Command

```powershell
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
python scratch/run_series_d_sweep.py
```

## Exit code

`0` (wall ~437s / ~7.3 min)

## Artifacts

| Path | Present |
|------|---------|
| `scratch/series_d_metrics.json` | yes |
| `alter_ego_calibrate_series_d.db` | yes |
| `docs/calibration_series_d_metrics.json` | yes (governance copy) |

## Headline @ anomaly_threshold=45 (seed 42, config 2.2)

| Metric | Value |
|--------|------:|
| Precision | 0.010745 |
| Recall | 0.504274 |
| F1 | 0.021041 |
| TP | 59 |
| FP | 5432 |
| FN | 58 |
| TN | 13925 |
| drift_alerts | 19 |
| active_alert_workflow_rows | 3241 |

## Per-scenario recall (S1→S5)

| Scenario | Recall | TP | FN |
|----------|-------:|---:|---:|
| scenario_1_sharp_misuse | 1.0 | 1 | 0 |
| scenario_2_slow_roll | 0.714 | 25 | 10 |
| scenario_3_subtle | 0.444 | 20 | 25 |
| scenario_4_service_abuse | 0.0 | 0 | 1 |
| scenario_5_patient_cycle | 0.371 | 13 | 22 |

## S2 `drift_alert` raw trajectory

**Victim entity:** `user_engineer_4`  
**Attack events:** 35 malicious S2 events; **26/35** with nonzero `drift_alert.raw_value`.

D4 engaged on **all 35/35** S2 attack decisions (`drift_source_profile_version:*` present).  
Early events show D4 flags while `drift_alert_raw=0` (shadow version mismatch logged before shadow cumulative drift feeds scorer).

Stepped plateaus (by sim timestamp):

| Window (sim) | Events | drift_alert_raw | Notes |
|--------------|-------:|----------------:|-------|
| 2026-01-10 07:00 – 2026-01-11 08:30 | 9 | 0.0 | D4 flags only; score 0–4 |
| 2026-01-11 08:40 – 2026-01-12 09:40 | 6 | 1.796 | First shadow drift in scorer; anomalies from 2026-01-12 09:00 |
| 2026-01-13 10:00 – 10:40 | 5 | 4.412 | Rising |
| 2026-01-14 10:00 – 10:40 | 5 | 11.064 | Rising |
| 2026-01-15 10:00 – 10:40 | 5 | 14.581 | Rising |
| 2026-01-16 10:00 – 10:40 | 5 | 16.860 | Max decision raw; all anomalies |

**Shadow profile cumulative_drift ladder (19 shadows):**  
0×8 → 1.80 → 4.41 → 11.06 → 14.58 → 16.86 → 18.11 → 24.10 → 24.33 (peak) → decay.

Series C contrast: S2 `drift_alert_raw` stayed **0.0** on all attack events (D4 never engaged).

## Fallback-flag count

| Scope | Count |
|-------|------:|
| Global `drift_shadow_fallback:no_shadow` | **1084** |
| S2 attack events | 0 |

**Expectation:** ~0 after first shadow per block. Global count **exceeds** expectation — fleet-wide fallback still fires on blocked entities before shadow becomes as-of eligible. S2 victim path is clean (0 fallback).

## auto_resolved

| Field | Value |
|-------|------:|
| auto_resolved_count (global) | 2269 |
| S2 victim workflow `auto_resolved` rows | 18 |
| S2 victim active `new` at sweep end | 137 |

## promotion_coverage (dual metrics)

| Metric | Value |
|--------|------:|
| **promotion_coverage_ever** | 1.0 (55/55 entities) |
| **promotion_coverage_in_window** (N=5) | 0.413 (376/860 entity-days fresh; 484 stale) |

In-window metric exposes staleness that ever-promoted hides (Series C counterexample preserved).

## ATTEST peak-drift gate outcomes for S2

**Question:** With shadow drift visible in scorer, does S2 stay blocked?

**Answer: Yes.** At sweep end S2 has **137 active `new` alerts** (`s2_stays_blocked=true`).

| Observation | Detail |
|-------------|--------|
| Shadow max cumulative_drift | 24.33 (profiles) |
| Max decision drift_alert_raw | 16.86 |
| Auto-resolve audit rows (S2) | 18 |
| peak_drift_ok in all 18 audits | **true** (peak_drift ≤ 1.80 at resolve instants) |
| peak_drift_ok=false audits | **0** (auto-resolve only fires when ATTEST passes) |

Interpretation: Early QUIET∧ATTEST cycles cleared low-peak blocks (peak_drift < 5.0). As attack progressed, shadow drift rose (11→16→24 in profiles; 11→16 in decision raw). Entity **re-alerted** and remained build-blocked — high shadow drift prevented further auto-resolve (peak_drift gate would fail at 24.33). Drift-necessary TPs on S2: **100%** (25/25).

## D4 engagement count (vs Series C = 0)

| Series | `drift_source_profile_version` flag count |
|--------|------------------------------------------:|
| Series C | 0 |
| Series D | **12840** |
| S2 attack events only | 35/35 |

**Allowed C→D claim:** engagement 0 → nonzero. D4 time-axis fix is working.

## Honesty

- **Not CALIBRATED.**
- No FP/P/R improvement or regression claims vs Series C (invalid cross-series).
- Only permitted C→D comparison: D4 engagement count.
- `config/scoring_config.yaml` untouched (`knobs_changed: false`).
- SD7 governance / EXIT gate **not** run (per operator scope).

## Concerns

1. **Fallback storm:** 1084 global `drift_shadow_fallback:no_shadow` flags — above SD2 expectation of ~0 post-first-shadow.
2. **Precision collapse:** P=0.011 with FP=5432 — detection topology changed materially; not a calibration claim.
3. **S2 partial recall:** 0.714 (25/35) — improved from Series C 0.0 but not full catch.
