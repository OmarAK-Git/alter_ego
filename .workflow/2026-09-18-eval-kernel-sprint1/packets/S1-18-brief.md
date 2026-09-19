# S1-18 implement / review / verify packet

**Task:** `cap.drift_vs_point_axes`
**Plan:** Task 18 (~2614–2705)
**Claim:** old_build emits `drift_alerts` and `point_anomaly_fp` as separate fields plus recorded `f1_at_45` that is not the pin; `f1_treated_as_primary` is False; new_build pending. Reuse Task 17 compact fixture.

## Files
- Create: `tests/eval/scenarios/cap.drift_vs_point_axes.yaml`
- Create: `tests/eval/test_cap_drift_vs_point_axes.py`
- Modify: `batch/eval/e2e_kernel.py` only (reuse `write_compact_seed42_s2_s3_s5_jsonl`)

## Locked
- Point-anomaly FP = `is_anomaly` ∧ not malicious ∧ `drift_necessary` is False
- `drift_alerts` = decisions where `drift_necessary` is True **or** `"drift_alert"` is in `flags` (`list[str]`). Do not use `json_extract($.drift_alert)`
- Theater `f1_only_usefulness` with `f1_treated_as_primary=False`
- `new_build` pending; no scoring_config edits; no usefulness claim

## Controller
```
PYTHONPATH=. pytest tests/eval/test_cap_drift_vs_point_axes.py -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_cap_drift_vs_point_axes.py
```

## Commit
`Split drift vs point-anomaly axes on the eval scorecard; F1@45 not the pin`
