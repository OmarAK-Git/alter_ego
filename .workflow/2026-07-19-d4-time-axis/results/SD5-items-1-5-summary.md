# SD5 — Items 1–5 operator summary (D4 time-axis)

**Gate:** SD5-REVIEW-GATE  
**Date:** 2026-07-19  
**Scope:** Items 1–5 only. **STOP before SD6.** Series D sweep not started.

---

## Verdict (items 1–5)

Ready for operator approval to unblock SD6. See `SD5-REVIEW-GATE-verifier-result.md`.

---

## Checklist

| Item | Status | Evidence |
|------|--------|----------|
| **SD0** C2 red (wall/sim seam) | Done | `.workflow/2026-07-19-d4-time-axis/results/SD0-C2-red.txt` — FAIL: `drift_alert.raw_value=0.0` vs shadow `3.0` |
| **SD1** `data_window_end` as-of + `created_at DESC` tie-break; `count_shadow_profiles`; audit | Done | `worker/profile_store.py`; `SD1-C2-green.txt`; `SD1-profile-store-audit.md` |
| **SD2** blocked miss → WARN + `drift_shadow_fallback:no_shadow` via ProfileStore | Done | `worker/scorer.py` D4 branch; `test_blocked_shadow_miss_emits_fallback_flag` |
| **SD3** wall-future + tie-break regressions | Done | three tests in `tests/worker/test_shadow_drift_under_block.py` |
| **SD4** dual `promotion_coverage` (ever + in_window **N=5**) + Series D harness skeleton | Done | `scratch/run_series_d_sweep.py`; `tests/batch/test_promotion_coverage_metrics.py` |
| **No YAML / scoring_config writes** | Confirmed | `git diff` / status clean for `config/scoring_config.yaml` |
| **Series D not run** | Confirmed | `docs/calibration_series_d_metrics.json` absent; no `series_d*metrics*` artifacts |

---

## Named artifacts (operator quick refs)

| Kind | Path / name |
|------|-------------|
| C2 **red** | `.workflow/2026-07-19-d4-time-axis/results/SD0-C2-red.txt` |
| C2 **green** | `.workflow/2026-07-19-d4-time-axis/results/SD1-C2-green.txt` |
| ProfileStore **audit verdict** | `SD1-profile-store-audit.md` — as-of on `data_window_end`; `created_at` tie-break only; `get_active_profile` on `promoted_at` (sim-safe in eval); Series C S2 `shadow_ever=19` / attack-window-by-`created_at`=0 |
| Fallback **flag** | `drift_shadow_fallback:no_shadow` |
| In-window staleness | **N=5** (`IN_WINDOW_STALENESS_DAYS = 5`) |

---

## Fresh verify (SD5)

```
PYTHONPATH=. pytest tests/worker/test_shadow_drift_under_block.py tests/batch/test_promotion_coverage_metrics.py -v --tb=short
→ 9 passed (5 shadow + 4 promotion_coverage)

ruff check worker/profile_store.py worker/scorer.py tests/worker/test_shadow_drift_under_block.py
→ All checks passed
```

---

## STOP

- **Do not start SD6** until explicit operator ACK.
- SD6 remains **blocked** in `state.json`.
- Next packet after approval: **SD6** (Series D seed-42 sweep).
