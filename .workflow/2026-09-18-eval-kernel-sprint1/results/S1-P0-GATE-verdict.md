# S1-P0-GATE verdict

- **model:** `cursor-grok-4.6-high-fast` (`in_session_grok`, never Opus)
- **packet:** `S1-P0-GATE` (foundation phase exit)
- **branch:** `gsd/eval-kernel-sprint1` @ `78caae2`
- **timestamp:** `2026-09-18`
- **verdict:** `ACCEPT-WITH-GAPS`

---

## Verdict

**ACCEPT-WITH-GAPS**

Foundation phase is earned. S1-1..S1-4 are done with verifier ACCEPT, and the official P0 gate commands are green under a fresh independent re-run. The standing full suite is not green (229 passed, 1 failed). That single failure is pre-existing on `origin/main`, is outside Sprint 1 eval-kernel scope, and must not be “fixed” by reverting `config/scoring_config.yaml`. It is a recorded residual for later test alignment / `S1-EXIT-GATE`, not a P0 reject.

---

## Claim under review

S1-P0-GATE (foundation phase exit) can proceed because:

1. Queue packets S1-1..S1-4 are `done` with skeptic-verifier ACCEPT.
2. Official P0 commands pass (26 pytest / packet ruff clean).
3. Standing suite `229 passed, 1 failed` is a known Series I / test-contract mismatch, not a Sprint 1 regression.
4. This sprint must not edit scoring knobs and must not require a `scoring_config.yaml` revert.

Vague “foundation is done” without those four checks would be unverifiable. Those are the load-bearing checks.

---

## Fresh gate commands (re-run by this gate; not trusted from controller logs alone)

| Command | Result | Evidence |
|---|---|---|
| `pytest tests/eval/test_scorecard_schema.py tests/eval/test_e2e_kernel.py tests/eval/test_scenario_loader.py tests/eval/test_theater.py -v --tb=short` | **26 passed**, 3 warnings (`builder.py` `utcnow`), exit 0, 3.80s | this gate, 2026-09-18 |
| `ruff check core/schemas/scorecard.py batch/eval` | **All checks passed**, exit 0 | this gate |
| `ruff check .` | **All checks passed**, exit 0 | this gate |
| `pytest -v --tb=short --ignore=tests/live` | **229 passed, 1 failed**, 394 warnings, 29.95s | this gate |
| Isolated: `tests/worker/test_precision_gate_stage_a.py::test_precision_gate_disabled_does_not_change_containment_flag` | **FAILED** — `simulated_containment_queued` missing; flags are `volume_delta_deferred`, `containment_deferred_single_family` | this gate |

Controller transcripts `S1-P0-GATE-packet.txt` and `S1-P0-GATE-full-suite.txt` match these fresh results. They were not used as sole evidence.

---

## Foundation packets

| Packet | Queue / state | Verifier file | Verdict |
|---|---|---|---|
| S1-1 | `done` (`0c682d2`, `8ab4178`) | `results/S1-1-verifier-result.md` | ACCEPT |
| S1-2 | `done` (`81e99ae`, `c61eda0`) | `results/S1-2-verifier-result.md` | ACCEPT |
| S1-3 | `done` (`c39f75c`) | `results/S1-3-verifier-result.md` | ACCEPT |
| S1-4 | `done` (`78caae2`) | `results/S1-4-verifier-result.md` | ACCEPT |

HEAD is `78caae2` (S1-4). Uncommitted paths are workflow/queue/evidence only — no source drift after the packet run.

Spot-check vs plan Tasks 1–4 (letter + intent):

- `core/schemas/scorecard.py` ships `LOCKED_SCENARIO_IDS` (15 IDs) and frozen `ScorecardRow`.
- `batch/eval/e2e_kernel.py` calls `run_pipeline`; packet test `test_run_production_call_invokes_all_five_stages_and_does_not_insert_decisions_itself` passed.
- `tests/eval/scenarios/des.production_call_shape.yaml` exists; stem matches `scenario_id`.
- `batch/eval/theater.py` owns `THEATER_DETECTOR_NAMES` (10 spec §8 names). `batch/eval/scenario_loader.py` imports that set; no local `ALLOWED_THEATER`.

Sprint source diff vs `origin/main` is eval-kernel only (`batch/eval/*`, `core/schemas/scorecard.py`, `tests/eval/*`). No `config/` and no `tests/worker/test_precision_gate_stage_a.py`.

---

## Official P0 criteria vs standing suite

Queue item `S1-P0-GATE` commands are the two packet commands above. Both **MET**.

`state.json` “Full suite green” is a **sprint** success criterion, owned by `S1-EXIT-GATE` (`pytest -v --tb=short --ignore=tests/live`), not a P0 hard gate. Treating the standing miss as a P0 reject would block foundation drain for a failure this sprint is forbidden to paper over by reverting Series I knobs.

---

## Gap (recorded; does not reject P0)

**`test_precision_gate_disabled_does_not_change_containment_flag` is stale vs shipped Series I default.**

- Test (`tests/worker/test_precision_gate_stage_a.py:178-218`) docstring still claims `enabled: false (shipped default)` and asserts `simulated_containment_queued`.
- Live YAML (`config/scoring_config.yaml:61-62`) and `origin/main` both have `precision_gate.enabled: true`.
- Fresh isolation failure: `assert "simulated_containment_queued" in decision.flags` — actual flags `['volume_delta_deferred', 'containment_deferred_single_family']`; `precision_gate_version='stage_a_v1'`.
- `git diff origin/main -- tests/worker/test_precision_gate_stage_a.py config/scoring_config.yaml` is empty.
- `git log origin/main..HEAD -- config/scoring_config.yaml tests/worker/test_precision_gate_stage_a.py` is empty.

This is a pre-Series-I test contract vs the accepted Series I `enabled: true` default. It is **not** a Sprint 1 eval-kernel regression.

**Out of scope for this gate / this sprint:** revert `precision_gate.enabled` to `false`. Queue + run plan lock: no `scoring_config.yaml` knob edits.

**Follow-up (not P0, not a knob revert):** align the Stage A *test* with the shipped `enabled: true` default before `S1-EXIT-GATE`, or accept the same residual there if still red.

---

## Why not PASS

A clean `PASS` would overclaim standing-suite health. The suite is red (1 fail). That residual is real and will confront `S1-EXIT-GATE`. P0 may proceed with the gap named.

## Why not REJECT

Official P0 commands are green. S1-1..S1-4 verifier ACCEPT holds. The only standing fail is identical on `origin/main`, outside the sprint file set, and must not be cleared by a scoring-config revert. Rejecting foundation on that miss would violate sprint scope.

---

## Non-gaps

- Packet `utcnow` warnings in `batch/profile_builder/builder.py` are pre-existing and not a P0 command.
- Full-suite warning volume (394) matches the controller log; not a new Sprint 1 defect.
- Working-tree workflow evidence files (`S1-4-brief.md`, verifier/gate logs) are expected GSD residue, not product drift.
