# Scoring-config governance — Series D (2026-07-19)

**Packet:** `.workflow/2026-07-19-d4-time-axis/` (SD6–SD7)  
**Status:** Series D baseline established. **Not CALIBRATED.** Detection knobs **unchanged**.

## What this sweep covers

| Item | Value |
|---|---|
| Seed | 42 |
| Config | v2.2 @ `anomaly_threshold=45` |
| Semantics | R-INTERLOCK (QUIET∧ATTEST + D4 time-axis fix) + `scenario_5_patient_cycle` on `eval_scenario_5` (feeds builder); S2/S3/S5 builder-visible |
| D4 fix | `ProfileStore.get_latest_shadow_profile` as-of on `data_window_end` (sim time); `created_at DESC` tie-break only |
| Artifact | [`docs/calibration_series_d_metrics.json`](calibration_series_d_metrics.json) |
| Harness | `scratch/run_series_d_sweep.py` |
| Knobs changed | **false** — attestation params remain code defaults (`core/attestation.py`); no YAML write |

## Headline (Series D only — not comparable to A/B/C)

| Metric @ thr=45 | Value |
|---|---|
| P / R / F1 | 0.011 / 0.504 / 0.021 |
| TP / FP / FN | 59 / 5432 / 58 |
| S1→S5 recall | 1.0 / 0.714 / 0.444 / 0.0 / 0.371 |
| auto_resolved | 2269 |
| promotion_coverage_ever | 1.0 (55/55 active promoted) |
| promotion_coverage_in_window (N=5) | 0.413 (376/860 entity-days fresh; 484 stale) |
| active_alert_workflow_rows | 3241 |
| d4_engagement_count | **12840** |
| fallback_flag_count | **1084** |

## Dual promotion coverage

| Metric | Value | Notes |
|---|---|---|
| **promotion_coverage_ever** | 1.0 (55/55) | Same headline as Series C — hides staleness |
| **promotion_coverage_in_window** (N=5) | 0.413 (376/860) | Exposes stale entity-days; Series C counterexample preserved |

## D4 engagement (only permitted C→D comparison)

| Series | `drift_source_profile_version` flag count |
|---|---:|
| Series C | 0 |
| Series D | **12840** |
| S2 attack events only | 35/35 |

**Allowed C→D claim:** engagement 0 → nonzero. D4 time-axis fix is working.

**Prohibited C→D claims:** FP, precision, recall, F1, or any “improvement/regression” narrative. Series D is a new baseline under fixed D4 semantics; topology changed materially (see concerns).

## S2 slow-roll under D4 (Series D only)

**Victim:** `user_engineer_4`  
**Attack events:** 35; **25/35** TP (recall **0.714**); drift-necessary TPs **100%** (25/25).

| Observation | Detail |
|---|---|
| D4 engaged | 35/35 attack decisions (`drift_source_profile_version` present) |
| Shadow max cumulative_drift | 24.33 (profiles) |
| Max decision drift_alert_raw | 16.86 |
| S2 stays blocked | **137** active `new` alerts at sweep end (`s2_stays_blocked=true`) |
| Auto-resolve audits (S2) | 18 rows; all `peak_drift_ok=true` (peak ≤ 1.80 at resolve instants) |
| S2 fallback flags | **0** (victim path clean) |

Series C contrast: S2 `drift_alert_raw` stayed **0.0** on all attack events (D4 never engaged).

## Cross-series rule

**C→D (and A/B→D) FP/P/R deltas are INVALID** as improvement or regression claims. Series D is a new baseline under D4 time-axis fix + dual coverage metrics.

Series C remains archived at [`calibration_series_c_metrics.json`](calibration_series_c_metrics.json) — do not overwrite.

## Honest reading

- **Not CALIBRATED.** Engagement success does not earn calibration.
- D4 fix unblocks shadow drift visibility under block; Series D S2 event recall is **0.714** (cite Series D framing only — no C→D recall-delta or "improvement" claim; the only permitted C→D comparison is the engagement count).
- S2 entity **re-alerted** and remained build-blocked as shadow drift rose (11→16→24 in profiles); high shadow drift prevented further auto-resolve.
- Precision collapsed (P≈0.011, FP=5432) — detection topology changed; not a knob-tuning success.
- Fallback storm: **1084** global `drift_shadow_fallback:no_shadow` flags — above SD2 expectation (~0 post-first-shadow per block); fleet-wide, not S2 victim.

## Standing rule

No knob edits without sweep + governance. Headline recall requires attribution decomposition. Do not reclaim boil-the-frog from Series D S2 R alone — B4 remains the scoped license.

## Follow-on (not executed here)

**Attestation YAML hygiene** — promote `core/attestation.py` defaults to `config/scoring_config.yaml` under a separate S6.3 record; acceptance = **zero behavioral diff**. Out of SD7 scope.
