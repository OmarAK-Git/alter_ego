# S1-1 review / verify packet

**Task:** Scorecard schema + Pydantic (plan Task 1)
**Commit:** `0c682d2` Add frozen ScorecardRow schema for the 15-ID eval kernel
**Files:** `core/schemas/scorecard.py`, `core/schemas/__init__.py`, `tests/eval/__init__.py`, `tests/eval/test_scorecard_schema.py`

## Required products
- `LOCKED_SCENARIO_IDS` — exactly the 15 spec §5 IDs; no `cap.attributed_s3`
- `PENDING_ALLOWED` — only `(cap.attributed_s2_s3_s5, new_build)`, `(cap.drift_vs_point_axes, new_build)`, `(thr.fp_block_sanctuary, new_build)`
- `ScorecardRow` with `extra="forbid"`, frozen
- `validate_scorecard_row()`
- Tests from the plan must exist and pass

## Constraints
- Do not change scoring_config.yaml
- Do not add /api/ingest, FakeProvider, Series J, or usefulness claims
- pending is illegal except the three pairs above
- failure_class none only for pass/pending; fail/error require a class

## Fresh evidence already gathered by controller
```
pytest tests/eval/test_scorecard_schema.py -v --tb=short
6 passed
ruff check core/schemas/scorecard.py core/schemas/__init__.py tests/eval/test_scorecard_schema.py
All checks passed
```

Do not trust this blindly. Re-read the files and, for the verifier, re-run the commands if you can.
