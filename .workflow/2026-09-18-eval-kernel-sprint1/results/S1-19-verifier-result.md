# S1-19 skeptic-verifier result

**Task:** S1-19 / Plan Task 19 — `cap.no_n1_headline`
**Claim:** Kernel-owned `format_capability_headline` refuses S1/S4-only text and requires S2/S3/S5 with n. Both scorecard arms pass with `n1_headline_rejected` True and status not pending. Live headline includes S2+S3+S5. Theater `n1_headline` does not trip on the live headline. An S1/S4-only headline would fail the suite as theater. `scoring_config.yaml` untouched.
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `179408d6242e5c02ed1164a8eaec3e6c5bfca619`
**Date:** 2026-09-18

## Claim restated

Load-bearing claim: `format_capability_headline` returns a `REFUSED:` string for S1/S4-only cells and a non-refused S2/S3/S5-with-n string otherwise; theater `n1_headline` trips on the stripped S1/S4 refuse text and does not trip on the accepted formatter output. `evaluate_scenario("cap.no_n1_headline")` emits two `ScorecardRow`s, both `status=="pass"` (not `pending`) with `observed["n1_headline_rejected"] is True`. The live observed headline contains S2, S3, and S5. Feeding an S1/S4-only headline to theater trips, which is the evaluate fail path (`failure_class=theater_detector`). `config/scoring_config.yaml` is unchanged vs HEAD and vs `179408d`.

Vague “tests passed” without those five behaviors is unverifiable; this verdict is from independent re-runs and a second live `evaluate_scenario` dump, not the implementer transcript.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/eval/test_cap_no_n1_headline.py -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_cap_no_n1_headline.py
git diff HEAD -- config/scoring_config.yaml
```

**pytest:** 3 passed, 0 failed (41.56s), exit 0

```
tests/eval/test_cap_no_n1_headline.py::test_formatter_refuses_s1_s4_only PASSED
tests/eval/test_cap_no_n1_headline.py::test_formatter_accepts_s2_s3_s5_with_n PASSED
tests/eval/test_cap_no_n1_headline.py::test_cap_no_n1_headline_both_arms_pass PASSED
====================== 3 passed, 274 warnings in 41.56s =======================
```

**ruff:** All checks passed (exit 0)

**git diff HEAD -- config/scoring_config.yaml:** empty (no output)

HEAD `179408d6242e5c02ed1164a8eaec3e6c5bfca619` (“Refuse S1/S4-only headlines as an eval-kernel theater pin”). Commit name-only: `batch/eval/e2e_kernel.py`, `tests/eval/scenarios/cap.no_n1_headline.yaml`, `tests/eval/test_cap_no_n1_headline.py`. `git diff 179408d^..179408d -- config/scoring_config.yaml` also empty. `git status --short` empty at verify time.

## Files re-read

- Plan Task 19: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:2709-2826`
- `tests/eval/test_cap_no_n1_headline.py` (refuse / accept / both-arms)
- `tests/eval/scenarios/cap.no_n1_headline.yaml` (`theater_detector: n1_headline`, both arms `expected.n1_headline_rejected: true`, pins `[n1_headline_rejected, headline]`)
- `batch/eval/e2e_kernel.py` (`format_capability_headline` `:827-841`; `_eval_cap_no_n1_headline` `:844-897`; dispatch `:1323-1325`)
- `batch/eval/theater.py` (`_n1_headline` `:36-45`)
- `core/schemas/scorecard.py` (`LOCKED_SCENARIO_IDS` includes this id; `PENDING_ALLOWED` does **not** — pending would be schema-illegal)
- `tests/eval/test_theater.py` (`n1_headline` S1/S4-only trips; S2+S3+S5 does not)

## Independent probes (not the pytest file)

Imported `format_capability_headline`, `evaluate_scenario`, and `run_theater_detector` in a fresh process (second live run after pytest).

Formatter / theater:

| case | text | starts REFUSED | theater raw | theater stripped |
|---|---|---|---|---|
| S1+S4 only | `REFUSED: S1/S4-only headline is not a decision criterion` | True | True | True |
| S2+S3+S5 n≥1 | `attributed S2 n=35 R=0.74; S3 n=45 R=0.11; S5 n=35 R=0.6` | False | False | False |
| empty / S2-only / S2S3S5 n=0 | `REFUSED: S2/S3/S5 with n are required` | True | False | False |
| S1-only / S4-only / S1+S2+S3 no S5 | `REFUSED: S1/S4-only headline is not a decision criterion` | True | True | True |

Theater alts (not the formatter): `'S1 recall 1.0, S4 recall 1.0 — operating point accepted'`, `'Decision criterion: S1 and S4 only'`, `'S1 and S4 only'` all `True`.

Live `evaluate_scenario("cap.no_n1_headline")`:

| arm | status | failure_class | n1_headline_rejected | headline |
|---|---|---|---|---|
| old_build | pass | none | True (bool) | `attributed S2 n=35 R=0.8571428571428571; S3 n=45 R=0.6666666666666666; S5 n=35 R=0.7142857142857143` |
| new_build | pass | none | True (bool) | same |

`N_ROWS 2`. Both `scenario_id == cap.no_n1_headline`. Live headline HAS_S2/S3/S5 True, HAS_S1/S4 False, not `REFUSED:`. Theater on that live string: `False`. Recalls are live `tp/n` floats, not the unit-test 0.74/0.11/0.60 fixture.

S1/S4-only as live headline (simulated through the evaluate branch): theater True → `failure_class=theater_detector`. Same for the formatter’s REFUSED S1/S4 string used as live text.

## Refutation attempts (named holes)

| # | Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|---|
| 1 | format(S1+S4) does not start REFUSED; theater misses stripped text | independent call returns accepted / theater False | `REFUSED: S1/S4-only…`; theater True on raw and stripped | no |
| 2 | format(S2+S3+S5 with n) is REFUSED or theater trips | independent call refused or theater True | non-REFUSED `attributed S2…S3…S5…`; theater False | no |
| 3 | evaluate arms not both pass / rejected not True / pending | live statuses wrong | Live 2 rows, both `pass` / `none` / `n1_headline_rejected True` / not pending. Pytest asserts the same. Pending is schema-illegal for this id. | no |
| 4 | live headline lacks S2 or S3 or S5 | dump missing tokens or is REFUSED / hardcoded unit-test recalls | Live string has S2 n=35, S3 n=45, S5 n=35 and live recalls 0.857/0.667/0.714; no S1/S4; theater False | no |
| 5 | S1/S4-only would not fail as theater | theater False on S1/S4 decision text, or evaluate ignores theater | Theater True on plan-style S1/S4 text and on REFUSED S1/S4 string. Evaluate `:878-879` sets `fail` / `theater_detector` when tripped. | no |
| 6 | `scoring_config.yaml` edited | git diff nonempty vs HEAD or in `179408d` | Both diffs empty. Commit touches 3 eval files only. | no |

## Residual nits (not enough to REJECT)

- Controller `test_cap_no_n1_headline_both_arms_pass` does not assert headline tokens or theater-on-live. Independent dump did.
- `live_has_s2_s3_s5` is `not headline.startswith("REFUSED:")`, not a token check. Current formatter has only one non-REFUSED shape, and that shape always includes S2/S3/S5; live dump matched.
- Empty / S2-only refuse text contains the tokens S2+S3+S5, so theater does not trip on those strings. Evaluate would then fail via `n1_headline_rejected=False` / `harness`, not theater. The named claim is S1/S4-only → theater.
- Refuse wording says “S1/S4-only” whenever S1 or S4 is present after the S2/S3/S5-with-n gate fails (including S1+S2+S3 missing S5). Behavior is still refuse.
- Both arms are copies of one evaluation. Matches Sprint 1 theater-pin “both arms pass.”
- Evaluate never injects an S1/S4-only *pipeline* headline (compact fixture is S2/S3/S5 only). Fail-as-theater is wired and independently simulated, not exercised as a pytest fail-path.

## Verdict

**ACCEPT.** All five named checks survived independent re-run: S1/S4-only formatter refuse + theater trip on stripped text; S2+S3+S5-with-n accepted and theater quiet; both scorecard arms `pass` with `n1_headline_rejected True` and not pending; live headline contains S2+S3+S5 (and theater does not trip); `scoring_config.yaml` untouched. Residual nits are test thinness and refuse-message wording, not missing pin behaviors.
