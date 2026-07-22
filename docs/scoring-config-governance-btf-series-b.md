# Scoring-config governance — BTF Series B (2026-07-18)

**Packet:** BTF remediation (`.workflow/2026-07-18-boil-the-frog-invariants/`)  
**Status:** No weight/threshold change. **Not CALIBRATED.**

## What changed (non-knob)

| Change | Location |
|---|---|
| S2 ladder inject | `batch/synthetic/generator.py` + ladder YAML |
| S2/S3 feed builder | `batch/profile_builder/builder.py` |
| §5.5 alert arming on anomaly | `worker/recorder.py` `open_active_alert_if_needed`; builder drift path |
| Design 1 invariants (B3a/B3b/B4) | `tests/test_boil_the_frog_invariants.py` |

## Knobs

`config/scoring_config.yaml` v2.2 @ thr=45 **unchanged**.

## Series B baseline (with attribution)

Artifact: `docs/calibration_series_b_metrics.json` — includes `drift_necessary_tp_fraction`, `pre_absorption_tp_fraction`, `early_below_threshold_fraction`, `caught_before_absorption_proxy` per governance rule.

**Headline:** S2 R=0.0 under full mix after §5.5 arming. **S2 R alone does not reclaim boil-the-frog — B4 is the license**, scoped to Design 1 fixture conditions only.

## §5.5 investigation answer

Build-blocking **is** implemented, but previously **did not arm** because anomalies never opened `AlertWorkflowState`. Fixed; B3b is the acceptance test and is green on the Design 1 fixture.

## Degenerate-regime caveat (added 2026-07-18, post-§2.7 confirmation)

**All Series B non-S2 metrics — FP counts, PR curve, S3 numbers, cohort medians — were measured under a degenerate frozen-builds regime and are NOT the system's characteristic rates.** Confirmed by DB queries (residual-risk §2.7): 45/55 entities went shadow-only at the third build (sim Jan 4) and 50/55 (90.9%) were frozen by sweep end, with all 2324 workflow rows terminating in state `new`. Consequences: benign events scored against ~Jan-3 baselines for the rest of the sweep; blocked entities were excluded from cohort histograms (builder Fix #6), so cohort baselines were computed from as few as 5–10 entities; frozen baselines staleness-inflated raw drift fleet-wide (48 of 87 builder drift alerts fired on non-attack entities). None of these rates characterize a system with functioning promotion.

**Next sweep after the §5.5 blocking-scope/lifecycle design lands = Series C.** The A→B cross-series comparison prohibition applies identically to B→C: Series C establishes a new baseline; no FP/P/R deltas across the boundary may be cited as improvement or regression.

## Standing rule

No knob edits without sweep + governance. Headline recall requires attribution decomposition (this Series B JSON complies).
