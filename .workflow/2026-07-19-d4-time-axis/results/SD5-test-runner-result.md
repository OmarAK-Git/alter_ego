# SD5 test-runner result

**Gate:** SD5-REVIEW-GATE (fresh verify)

## Pytest

| Metric | Count |
|--------|-------|
| Passed | 9 |
| Failed | 0 |
| Skipped | 0 |
| Exit code | 0 |

**Status:** PASS

## Ruff

| Metric | Value |
|--------|-------|
| Exit code | 0 (anomalous — 1 violation reported) |
| Violations | 1 |

**Status:** FAIL (content violation despite exit 0)

- `scratch/run_series_d_sweep.py:35` — F401 unused import `core.database.SessionLocal`

## Gate verify

**RED** — pytest green; ruff has 1 fixable F401 in `scratch/run_series_d_sweep.py`.
