# Scoring-config governance — S3 attestation

**Date:** 2026-07-13  
**Packet:** S3.6  
**Status:** No knob change — attestation only. **Not CALIBRATED.**

## Attestation

S3 (packets S3.1–S3.5) performed integrity fixes, one full re-sweep, and operating-point documentation. **No feature weight or threshold in `config/scoring_config.yaml` was changed during S3.**

| Field | Value | Changed in S3? |
|---|---|---|
| `version` | `"2.2"` | No |
| `anomaly_threshold` | 45.0 | No |
| `drift_threshold` | 5.0 | No |
| Feature weights | per YAML v2.2 | No |
| `drift_weights` | per YAML v2.2 | No |

The S3.1 re-sweep used this config unchanged. Sweep evidence:

- `docs/calibration_final_metrics.json` — `config_version: "2.2"`, `anomaly_threshold: 45.0`, `sweep: "S3.1"`, seed 42
- `.workflow/2026-07-12-v1-portfolio-ready/results/S3.1-implementer-result.md` — sweep commands and per-scenario recall
- `.workflow/2026-07-12-v1-portfolio-ready/results/S3.2-implementer-result.md` — metrics JSON refresh

## thr=55 diagnostic — not applied

S3.2/S3.4 PR-curve analysis identified best-F1 at **anomaly_threshold=55** (P≈0.041, R≈0.585, FP=1136, FN=34). This was **diagnostic only**.

- **Not written** to `config/scoring_config.yaml`
- **Not** recorded via `worker/config_store.py` `save_config`
- Operating point remains **thr=45** per `docs/phase2-s3-operating-point.md`

PR-curve artifact: `docs/calibration_pr_curve.json`

## Standing rule

**No weight or threshold change without:**

1. A recorded full calibration sweep (`batch/eval/runner.py` or documented scratch path with fixed seed)
2. Refreshed `docs/calibration_*.json` artifacts
3. A governance record (this doc pattern, or `ConfigStore.save_config` with `author` + `change_reason` for runtime promotion)

Ad hoc YAML edits without sweep evidence are prohibited. See `OPS.md` and SPEC §9 (Scoring Config Governance).

## Infrastructure note

`worker/config_store.py` supports hash-chained `save_config` records for future knob changes. S3 did not invoke it — YAML on disk matches pre-S3 values.
