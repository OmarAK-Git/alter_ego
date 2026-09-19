# S1-20 skeptic-verifier result

**Task:** S1-20 / Plan Task 20 — GitHub Actions + suite completeness
**Claim:** GHA owns the 15-ID deterministic suite. `evaluate_all` emits 30 rows. CLI `--assert-complete` exits 0. pending only on `(cap.attributed_s2_s3_s5, new_build)`, `(cap.drift_vs_point_axes, new_build)`, `(thr.fp_block_sanctuary, new_build)`. `cap.no_n1_headline` and `use.demo_honesty` both pass. `tests/live` stays skipped (not this job). `scoring_config.yaml` untouched.
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `e774854ff972755bbb9863573d7ce5b2be5b90d6`
**Date:** 2026-09-18

## Claim restated

Load-bearing claim: the 15 YAML stems in `tests/eval/scenarios/` equal `LOCKED_SCENARIO_IDS`. A live `evaluate_all` / CLI scorecard has exactly 30 unique `(scenario_id, arm)` pairs. The only `pending` rows are the three allowed triples. Both arms of `cap.no_n1_headline` and `use.demo_honesty` are `pass`. `python -m batch.eval.e2e_kernel --scorecard-out artifacts/eval-kernel-scorecard.jsonl --assert-complete` exits 0. `.github/workflows/eval-kernel.yml` and `.github/workflows/ci.yml` each have a scorecard step; those jobs do not run `--live`, Vertex, or SIEM. Default pytest skips `tests/live`. `config/scoring_config.yaml` is unchanged vs HEAD.

Vague “tests passed” without a live 30-row parse and CLI exit code is unverifiable. Artifact `artifacts/eval-kernel-scorecard.jsonl` was **absent** on this tree; this verdict is from an independent CLI re-run (~201s), not the implementer transcript.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/eval/test_suite_completeness.py::test_fifteen_scenario_files_exist_and_stems_match -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_suite_completeness.py tests/eval/test_e2e_kernel.py
git diff HEAD -- config/scoring_config.yaml
python -m batch.eval.e2e_kernel --scorecard-out artifacts/eval-kernel-scorecard.jsonl --assert-complete
pytest tests/live -q --tb=line
```

**pytest stems:** 1 passed, 0 failed (0.17s), exit 0

```
tests/eval/test_suite_completeness.py::test_fifteen_scenario_files_exist_and_stems_match PASSED
```

**ruff:** All checks passed (exit 0)

**git diff HEAD -- config/scoring_config.yaml:** empty (no output) before and after evaluate_all. `git diff main -- config/scoring_config.yaml` also empty. Commit `e774854` name-only: `.github/workflows/ci.yml`, `.github/workflows/eval-kernel.yml`, `batch/eval/e2e_kernel.py`, `tests/eval/test_e2e_kernel.py`, `tests/eval/test_suite_completeness.py`.

**CLI `--assert-complete`:** exit 0 (`EXIT:0`), ~201465 ms. Wrote `artifacts/eval-kernel-scorecard.jsonl`.

**tests/live without `--live`:** `ssssssss` — 8 skipped in 0.03s, exit 0.

HEAD `e774854ff972755bbb9863573d7ce5b2be5b90d6` (“Give GitHub Actions ownership of the 15-ID eval kernel suite”) on `gsd/eval-kernel-sprint1`.

## Files re-read

- Plan Task 20: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:2831-2993`
- Packet: `.workflow/2026-09-18-eval-kernel-sprint1/packets/S1-20-brief.md`
- `core/schemas/scorecard.py` (`LOCKED_SCENARIO_IDS` 15 IDs; `PENDING_ALLOWED` exactly the three triples)
- `tests/eval/scenarios/*.yaml` — 15 files, stems listed below
- `tests/eval/test_suite_completeness.py`
- `batch/eval/e2e_kernel.py` (`evaluate_all` `:1280-1286`; CLI `:1341-1365`; hardcoded `pending` for the three new_build arms `:916-930`, `:979-990`, `:1043-1054`)
- `batch/eval/scorecard.py` (`assert_scorecard_complete` missing-pair + fail/error)
- `batch/eval/scenario_loader.py` (`load_all_scenarios` glob `*.yaml`)
- `.github/workflows/eval-kernel.yml` (Scorecard completeness step `:29-32`; Upload scorecard `:33-38`)
- `.github/workflows/ci.yml` (Eval kernel scorecard step `:35-38`; comment that default suite skips live)
- `tests/conftest.py` (`--live` opt-in; unmarked live items skipped)
- `tests/live/conftest.py` (`pytestmark = pytest.mark.live`)

## Independent scorecard parse (live CLI output)

YAML stems vs `LOCKED_SCENARIO_IDS` (both size 15, set-equal):

`cap.attributed_s2_s3_s5`, `cap.drift_vs_point_axes`, `cap.no_n1_headline`, `des.ngram_mismatch_halts`, `des.no_llm_in_score`, `des.production_call_shape`, `gov.anomaly_opens_workflow`, `gov.integrity_job_sees_decisions`, `gov.no_knob_without_sweep`, `thr.api_key_required`, `thr.cmdline_injection_survives`, `thr.fp_block_sanctuary`, `use.demo_honesty`, `use.pipeline_to_triage`, `use.ui_sends_api_key`

Live JSONL: `N_ROWS 30`, `N_UNIQUE_PAIRS 30`, `PAIRS_EQ_EXPECTED True`. Statuses only `{pass, pending}`. `FAIL_ERROR []`.

| pending triple | live status |
|---|---|
| `(cap.attributed_s2_s3_s5, new_build)` | pending |
| `(cap.drift_vs_point_axes, new_build)` | pending |
| `(thr.fp_block_sanctuary, new_build)` | pending |

`PENDING_ONLY_ALLOWED True` (exactly those three; no extras).

| id | old_build | new_build |
|---|---|---|
| `cap.no_n1_headline` | pass | pass |
| `use.demo_honesty` | pass | pass |

## Refutation attempts (named holes)

| # | Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|---|
| 1 | YAML stems ≠ `LOCKED_SCENARIO_IDS` | extra/missing stem or id | 15 files; stems == locked set; pytest stem test PASSED | no |
| 2 | scorecard ≠ exactly 30 unique expected pairs | extra/duplicate/missing row | Live JSONL 30/30 unique; set equals 15×2 expected | no |
| 3 | pending outside the three triples, or those three not pending | other pending / fail, or those three pass | Exactly those three pending; all other 27 pass | no |
| 4 | `no_n1` or `demo_honesty` not both-arm pass | pending/fail/error on either arm | Both IDs both arms `pass` in live JSONL | no |
| 5 | CLI `--assert-complete` nonzero | exit ≠ 0 | `EXIT:0` after ~201s write of the JSONL | no |
| 6 | missing scorecard step, or job runs `--live` / Vertex / SIEM | no step, or those flags/services in the yml run lines | Both workflows have the CLI scorecard step. `eval-kernel.yml` has no `--live`/Vertex/SIEM. `ci.yml` mentions `--live` only in a skip comment. Default `pytest tests/live` → 8 skipped | no |
| 7 | `scoring_config.yaml` edited | nonempty git diff vs HEAD or in `e774854` | HEAD diff empty; vs `main` empty; commit does not list the file | no |

## Residual nits (not enough to REJECT)

- Artifact was missing; verifier produced `artifacts/eval-kernel-scorecard.jsonl` by re-running the CLI on this tree. That is evidence, not prior implementer output.
- `assert_scorecard_complete` does not reject extra rows (set-missing + fail/error only). Live file had no extras.
- `test_cli_assert_complete_exits_zero` only asserts exit 0 + file exists. Completeness test + this live parse cover the 30-row / pending / both-arm pins.
- Completeness test allows the three triples to be `pass`; live they are actually `pending` as claimed.
- Workflows trigger on `main` push/PR only (as the plan wrote). “GHA owns” is file wiring, not a green Actions run on this branch.
- `pytest tests/live --collect-only` still lists 8 tests; they are skip-marked and skip at runtime without `--live`.

## Verdict

**ACCEPT.** All seven named checks survived independent re-run: 15 YAML stems == `LOCKED_SCENARIO_IDS`; live scorecard is exactly 30 expected `(id, arm)` pairs; pending is only the three allowed new_build triples; `cap.no_n1_headline` and `use.demo_honesty` both arms pass; CLI `--assert-complete` exit 0; both workflow scorecard steps exist without `--live` / Vertex / SIEM; `scoring_config.yaml` untouched. Residual nits are test thinness and trigger-branch scope, not missing Task 20 behaviors.
