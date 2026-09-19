# S1-4 review / verify packet

**Task:** Theater detector registry (plan Task 4)
**Files:** `batch/eval/theater.py`, `batch/eval/scenario_loader.py`, `tests/eval/test_theater.py`

## Required products
- `THEATER_DETECTOR_NAMES` — exactly the ten spec §8 names
- `TheaterContext`, `run_theater_detector(name, ctx) -> (tripped, detail)`
- `scenario_loader` imports `THEATER_DETECTOR_NAMES` (local `ALLOWED_THEATER` deleted)
- Plan tests in `tests/eval/test_theater.py`

## Constraints
- No scoring_config edits, no /api/ingest, no Series J, no usefulness claim
- Loader tests must still pass

## Controller evidence
```
pytest tests/eval/test_theater.py tests/eval/test_scenario_loader.py -v --tb=short
16 passed
ruff check batch/eval/theater.py batch/eval/scenario_loader.py tests/eval/test_theater.py
All checks passed
```
