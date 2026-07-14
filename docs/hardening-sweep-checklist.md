# Hardening sweep checklist (S6.1)

**Purpose:** Re-run empirical calibration sweeps after personal drift research or pipeline changes.  
**Status:** Phase 2A — **not CALIBRATED.** Residual FP/FN at `anomaly_threshold=45` are documented in [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) (3448 FP, 15 FN, precision ~1.9%).

## Canonical baseline (do not drift casually)

| Field | Value |
|---|---|
| Generator seed | **42** (`EventGenerator(seed=42)`) |
| Config version | **2.2** (`config/scoring_config.yaml`) |
| Operating threshold | **45.0** (`anomaly_threshold` in YAML) |
| Sweep evidence | `docs/calibration_final_metrics.json` |
| PR-curve artifact | `docs/calibration_pr_curve.json` |
| Harness | `batch/eval/runner.py` (day-window pipeline) |

## Prerequisites

```powershell
# from repo root
pip install -e ".[dev]"
$env:PYTHONPATH="."
```

Use a dedicated sqlite eval DB (not production). Local DB files (`alter_ego_calibrate_*.db`) are gitignored — do not commit.

## Step 1 — Full four-scenario sweep (~4 min)

Runs baseline + tooling rollout + S1–S4 attack injects, then day-window ingest → profile build → score.

```powershell
# from repo root
$env:PYTHONPATH="."
python scratch/run_s31_sweep.py
```

**Produces (local, not committed):**

| Output | Role |
|---|---|
| `alter_ego_calibrate_s31.db` | Sweep sqlite DB |
| `scratch/s31_events.jsonl` | Generated event stream |
| `scratch/s31_ground_truth.jsonl` | Ground-truth labels |
| `scratch/s31_metrics.json` | Raw metric JSON @ thr=45 |

**Verify before refreshing docs:**

- `partition_check.all_partitions_eval_scenario` is `true` (attacks in `eval_scenario_*` only).
- Per-scenario recall printed for `scenario_1_sharp_misuse` … `scenario_4_service_abuse`.
- Global metrics at **threshold 45.0** (not YAML-default `is_anomaly` alone).

### Lower-level harness (custom event files)

```powershell
$env:PYTHONPATH="."
python -m batch.eval.runner <events.jsonl> <ground_truth.jsonl>
```

Uses `calculate_metrics(db)` with DB `is_anomaly` flag. For governance comparisons, re-apply a fixed threshold via `calculate_metrics(db, threshold=45.0)` (as `run_s31_sweep.py` does).

## Step 2 — Refresh `docs/calibration_*.json`

Requires Step 1 DB on disk.

```powershell
# from repo root
$env:PYTHONPATH="."
$env:DATABASE_URL="sqlite:///alter_ego_calibrate_s31.db"
python scratch/s32_refresh_calibration_docs.py
```

**Refreshes:**

| Artifact | Contents |
|---|---|
| `docs/calibration_final_metrics.json` | Global + per-scenario metrics @ thr=45, metadata (`generator_seed`, `config_version`, `sweep`) |
| `docs/calibration_pr_curve.json` | Threshold sweep (diagnostic; thr=55 best-F1 is **not** applied to YAML) |

## Step 3 — Update human-facing records (as needed)

| Doc | When to touch |
|---|---|
| [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) | Residual modes, per-scenario recall, or operating-point narrative changed |
| [`scoring-config-governance-s3.md`](scoring-config-governance-s3.md) | Knob change attestation, or reaffirm “no change” after integrity-only work |
| `.workflow/.../results/S*.x-implementer-result.md` | T3 packet evidence trail |

If **only** re-validating unchanged YAML after drift research, Step 1–2 plus an operating-point pointer update may suffice; do **not** claim CALIBRATED.

## Optional diagnostics (`scratch/analyze_step*.py`)

Deeper FP/alert-rate/score-distribution analysis patterns live in `scratch/analyze_step1.py` … `analyze_step4.py`. These expect their own event/label inputs or a populated eval DB — use after the main sweep when investigating residual modes (see operating-point doc §Residual error modes).

## What must **not** change without governance

1. **Feature weights or thresholds** in `config/scoring_config.yaml` — no ad hoc edits.
2. **Promoting PR-curve alternate points** (e.g. thr=55 best-F1) to YAML without a recorded sweep + governance record.
3. **CALIBRATED / audit-grade claims** in SPEC, README, or metrics JSON.

**Required if knobs change:**

1. Full sweep (Step 1) with fixed seed **42** (or document a new seed and re-baseline everything).
2. Refresh `docs/calibration_*.json` (Step 2).
3. Governance record ([`scoring-config-governance-s3.md`](scoring-config-governance-s3.md) pattern, or `worker/config_store.py` `save_config` with `author` + `change_reason`).
4. Update [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) with new residual FP/FN tradeoffs.

Standing rule also in `OPS.md` and SPEC §9.

## Post-sweep sanity checks

```powershell
pytest -v --tb=short
ruff check .
```

Regression tests should stay green; sweep evidence is additive documentation, not a substitute for unit/integration tests.

## Quick AC self-check

- [ ] Sweep used seed **42** and config **v2.2** unchanged (unless governance packet authorized a knob change).
- [ ] `docs/calibration_final_metrics.json` reflects the new run (`generator_seed`, `config_version`, `anomaly_threshold`).
- [ ] `docs/calibration_pr_curve.json` regenerated from the same DB.
- [ ] Residual FP/FN honestly noted — pointer to [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md); **not CALIBRATED**.
- [ ] No undocumented YAML weight/threshold edits.
