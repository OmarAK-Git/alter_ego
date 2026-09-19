# S1-P2-GATE verdict

**Judge:** skeptic-verifier / `in_session_grok` (`cursor-grok-4.6-high-fast`, never Opus)
**Phase:** capability rows S1-17..S1-19
**Branch:** `gsd/eval-kernel-sprint1` @ `179408d6242e5c02ed1164a8eaec3e6c5bfca619`
**Date:** 2026-09-18

## Verdict

**ACCEPT**

S1-P2-GATE may open S1-20. Official commands are green on a fresh judge re-run. All six load-bearing checks hold. Residuals below do not block S1-20.

## Claim restated

S1-P2-GATE may open S1-20 only if:

1. S1-17 / S1-18 / S1-19 have skeptic-verifier ACCEPT evidence under `.workflow/2026-09-18-eval-kernel-sprint1/results/`
2. Official P2 pytest + ruff are green
3. Capability quality `new_build` is pending for attributed + drift-vs-point; `cap.no_n1_headline` both arms pass
4. `observed.corpus` is `ci_compact_seed42_shaped` (not Series I TP=54)
5. No usefulness claim; Series I remains `calibrated: false`
6. No `scoring_config.yaml` edits

Vague “capability done” without those checks is unverifiable. This verdict is from independent file reads plus a fresh re-run of the official commands, not the controller packet or implementer notes.

## Fresh official commands (re-run by judge)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/eval/test_cap_attributed_s2_s3_s5.py tests/eval/test_cap_drift_vs_point_axes.py tests/eval/test_cap_no_n1_headline.py -v --tb=short
ruff check .
```

**pytest:** 5 passed, 0 failed (116.44s), exit 0

```
tests/eval/test_cap_attributed_s2_s3_s5.py::test_attributed_s2_s3_s5_old_recorded_new_pending PASSED
tests/eval/test_cap_drift_vs_point_axes.py::test_axes_split_old_recorded_new_pending PASSED
tests/eval/test_cap_no_n1_headline.py::test_formatter_refuses_s1_s4_only PASSED
tests/eval/test_cap_no_n1_headline.py::test_formatter_accepts_s2_s3_s5_with_n PASSED
tests/eval/test_cap_no_n1_headline.py::test_cap_no_n1_headline_both_arms_pass PASSED
================= 5 passed, 822 warnings in 116.44s (0:01:56) =================
PYTEST_EXIT:0
```

Controller packet (`.workflow/2026-09-18-eval-kernel-sprint1/results/S1-P2-GATE-packet.txt`, 5 passed / ruff clean, 112.22s) was **not** trusted. Judge re-ran both commands.

**ruff:** All checks passed (exit 0)

```
All checks passed!
RUFF_EXIT:0
```

Warnings are `datetime.utcnow()` deprecations in `batch/profile_builder/builder.py:691` and SQLAlchemy schema defaults. Not failures. Not a REJECT.

## Evidence table

| # | Check | Required evidence | What was gathered | Holds? |
|---|---|---|---|---|
| 1 | S1-17/18/19 skeptic ACCEPT | Files under `results/` with **Verdict: ACCEPT** | `S1-17-verifier-result.md` ACCEPT @ `aed7b3d`; `S1-18-verifier-result.md` ACCEPT @ `63752bc`; `S1-19-verifier-result.md` ACCEPT @ `179408d`. All three restated load-bearing claims and named refutation holes. | yes |
| 2 | Official P2 pytest + ruff green | Fresh exit 0, 0 failures | Judge re-run: 5 passed / 0 failed, ruff clean. Packet not used as proof. | yes |
| 3 | quality `new_build` pending on attributed + drift-vs-point; `cap.no_n1_headline` both arms pass | Kernel + YAML + official tests | Attributed/drift: `status="pending"`, `observed.quality="pending"`, YAML `new_build.expected: {quality: pending}`, `PENDING_ALLOWED` includes both `new_build` triples and **not** `cap.no_n1_headline`. Official tests assert attributed/drift `new.status == "pending"` and no_n1 both `status == "pass"` / `!= "pending"`. Kernel `_eval_cap_no_n1_headline` copies one pass onto both arms. | yes |
| 4 | `observed.corpus == ci_compact_seed42_shaped`; not Series I TP=54 | Kernel + tests; no `54` comparison | Kernel writes that corpus string on attributed old+new, drift old+new, and no_n1 observed. Official attributed + drift tests assert `old.observed["corpus"] == "ci_compact_seed42_shaped"`. Grep of the three official test files: no `54` / `Series I` / `useful` / `calibrated`. `tests/eval/` has no `TP=54` comparison. | yes |
| 5 | No usefulness claim; Series I `calibrated: false` | SoT files + theater pins | `docs/eval-kernel.md:12-13` Series I `calibrated: false`, “does not claim usefulness.” Series I `STATUS.md`: **Calibrated:** false; “Do not claim CALIBRATED.” `memory-bank/activeContext.md`: `calibrated: false`; “Do not claim usefulness.” Attributed/drift theater is `f1_only_usefulness` with hardcoded `f1_treated_as_primary=False`; official tests assert that flag is False. F1@45 is recorded on drift and is not the pass pin (`e2e_kernel.py:1014`). | yes |
| 6 | No `scoring_config.yaml` edits | git diffs empty on this branch | `git diff HEAD -- config/scoring_config.yaml` empty. `git diff origin/main...HEAD -- config/scoring_config.yaml` empty. `git log origin/main..HEAD -- config/scoring_config.yaml` empty. P2 commits `aed7b3d`..`179408d` touch eval kernel/tests/workflow only. Working tree: workflow packets/state only; no scoring-config path. | yes |

## Files re-read (not implementer notes)

- `.workflow/2026-09-18-eval-kernel-sprint1/results/S1-17-verifier-result.md`
- `.workflow/2026-09-18-eval-kernel-sprint1/results/S1-18-verifier-result.md`
- `.workflow/2026-09-18-eval-kernel-sprint1/results/S1-19-verifier-result.md`
- `.workflow/2026-09-18-eval-kernel-sprint1/packets/S1-P2-GATE-brief.md`
- `tests/eval/test_cap_attributed_s2_s3_s5.py`
- `tests/eval/test_cap_drift_vs_point_axes.py`
- `tests/eval/test_cap_no_n1_headline.py`
- `tests/eval/scenarios/cap.attributed_s2_s3_s5.yaml`
- `tests/eval/scenarios/cap.drift_vs_point_axes.yaml`
- `tests/eval/scenarios/cap.no_n1_headline.yaml`
- `batch/eval/e2e_kernel.py` (`_eval_cap_no_n1_headline` `:873-896`; `_eval_cap_attributed_s2_s3_s5` `:902-967`; `_eval_cap_drift_vs_point_axes` `:970-1031`)
- `core/schemas/scorecard.py` (`PENDING_ALLOWED` `:45-51`)
- `docs/eval-kernel.md`
- `.workflow/2026-08-02-series-i-serial-calibration/STATUS.md`
- `memory-bank/activeContext.md`

## Refutation attempts

| Hole | What would REJECT | Evidence | Hole stands? |
|---|---|---|---|
| Official commands fail / packet is stale | pytest or ruff nonzero | Fresh judge re-run: pytest 5/5 exit 0; ruff exit 0 | no |
| Verifier ACCEPT files missing or REJECT | no file, or verdict ≠ ACCEPT | Three ACCEPT files present and explicit | no |
| quality `new_build` marked pass | `new.status=="pass"` or `observed.quality=="pass"` on attributed/drift | Kernel hardcodes pending + `quality: pending`. Official tests assert pending. YAML expected is pending. | no |
| `cap.no_n1_headline` pending or one-arm only | pending illegal or one fail | Official `test_cap_no_n1_headline_both_arms_pass` passed. `PENDING_ALLOWED` excludes this id. | no |
| Corpus is Series I / compared to TP=54 | other corpus string, or `54` pin | Compact corpus string asserted. No TP=54 in official tests. | no |
| Usefulness claimed / Series I flipped calibrated | docs or scorecard treat F1 as primary, or SoT says calibrated true | SoT still `calibrated: false`. F1 not the pin. Kernel docs forbid usefulness. | no |
| `scoring_config.yaml` edited | nonempty diff vs HEAD or vs `origin/main` | All scoring-config diffs/logs empty on this branch | no |

## Residual nits (do not block S1-20)

- Official attributed/drift tests assert `new.status == "pending"` and do not assert `new.observed["quality"] == "pending"`. Kernel + YAML already record `quality: pending`. Schema would reject a pending row on a disallowed triple.
- Official attributed/drift tests assert corpus on `old_build` only. Kernel also writes the same corpus on `new_build`.
- S1-18 ACCEPT was at `63752bc`; corpus recording for drift-vs-point landed in follow-up `b5afbcf`. That strengthens check 4; it does not reopen S1-18.
- 822 `utcnow` deprecation warnings. Not a fail.
- Working tree at judge time: staged/untracked workflow packets (`S1-19-brief`, `S1-P2-GATE-brief`, `S1-19-verifier-result`, `S1-P2-GATE-packet.txt`) plus `state.json` / `autopilot-queue.json`. No product-code or scoring-config dirt.

## Decision

**ACCEPT.** Official P2 pytest and ruff are green. The six checks hold. S1-20 may open. Do not flip attributed or drift-vs-point `new_build` off pending. Do not claim usefulness. Series I remains `calibrated: false`.
