# S1-1 skeptic-verifier result (re-verify)

**Task:** S1-1 / Plan Task 1 — Scorecard schema + Pydantic
**Claim:** complete after added honesty / frozen / `validate_scorecard_row` tests
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `8ab4178`
**Date:** 2026-09-18

## Claim restated

S1-1 remains complete, and the prior holes (pending-on-old_build, error+none, realm mismatch, frozen, `validate_scorecard_row`) are now locked in tests.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_scorecard_schema.py -v --tb=short
ruff check core/schemas/scorecard.py core/schemas/__init__.py tests/eval/test_scorecard_schema.py
```

**pytest:** 8 passed, 0 failed (0.15s)

```
tests/eval/test_scorecard_schema.py::test_locked_ids_are_exactly_the_fifteen_from_spec_section_5 PASSED
tests/eval/test_scorecard_schema.py::test_extra_field_is_rejected PASSED
tests/eval/test_scorecard_schema.py::test_unknown_scenario_id_is_rejected PASSED
tests/eval/test_scorecard_schema.py::test_pending_only_on_allowed_quality_and_sanctuary_new_build PASSED
tests/eval/test_scorecard_schema.py::test_failure_class_none_only_when_pass_or_pending PASSED
tests/eval/test_scorecard_schema.py::test_fixture_must_be_deterministic PASSED
tests/eval/test_scorecard_schema.py::test_realm_must_match_locked_id PASSED
tests/eval/test_scorecard_schema.py::test_row_is_frozen_and_validate_scorecard_row_round_trips PASSED
============================== 8 passed in 0.15s ==============================
```

**ruff:** All checks passed (exit 0)

## Files re-read

- `tests/eval/test_scorecard_schema.py` (now 163 lines; 8 tests)
- `core/schemas/scorecard.py`
- `core/schemas/__init__.py`

## Refutation attempts (named holes)

| Hole | Test evidence | Runtime probe | Refuted as missing? |
|---|---|---|---|
| pending-on-old_build | `test_scorecard_schema.py:93-107` loops all 3 allowed IDs with `arm="old_build"` + `status="pending"` and expects `ValidationError` | all 3 rejected | no — covered |
| error+none | `test_scorecard_schema.py:113-114` | rejected | no — covered |
| realm mismatch | `test_realm_must_match_locked_id` (`:141-143`): `des.no_llm_in_score` + `realm="capability"` | rejected | no — covered |
| frozen | `test_row_is_frozen_and_validate_scorecard_row_round_trips` (`:162-163`) assigns `row.status = "fail"` | `ValidationError` | no — covered |
| `validate_scorecard_row` | imported `:8`; called `:147-161`; asserts `status=="pass"` | happy path works; invalid `cap.attributed_s3` also rejected via `model_validate` | no — covered |

## Residual nits (not enough to REJECT)

- `validate_scorecard_row` is still not in `core/schemas/__all__`. Plan Task 1 export list never included it.
- Invalid-input path for the wrapper is not a dedicated test; wrapper is `ScorecardRow.model_validate` and rejects independently.
- Positive pending `new_build` row is still only constructed for `cap.attributed_s2_s3_s5`, not the other two allowed IDs. `PENDING_ALLOWED` exact-set check plus old_build rejects remain.

## Verdict

**ACCEPT.** The five named holes are now in the test file and hold at runtime. Completion claim survives.
