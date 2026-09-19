# S1-P1-GATE verdict

- **model:** `cursor-grok-4.6-high-fast` (`in_session_grok`, never Opus)
- **packet:** `S1-P1-GATE` (gov/des/thr/use phase exit)
- **branch:** `gsd/eval-kernel-sprint1` @ `e11019d`
- **timestamp:** `2026-09-18`
- **verdict:** `ACCEPT`

---

## Verdict

**ACCEPT**

Sprint 1 may proceed to capability rows **S1-17..S1-19**. Official P1 commands are green under a fresh independent re-run. Live `evaluate_scenario` for the twelve gov/des/thr/use IDs emits two arms each; the only `pending` is the allowed triple `(thr.fp_block_sanctuary, new_build)`. Series I remains `calibrated: false`. SoT copy does not claim usefulness.

---

## Claim under review

S1-P1-GATE may open S1-17..S1-19 because:

1. Queue packets S1-5..S1-16 are `done` with skeptic-verifier ACCEPT (S1-5/6/7 individual; S1-8..S1-16 in `results/S1-8-16-21-verifier-result.md`).
2. Official P1 commands pass (16 pytest / `ruff check .` clean).
3. No usefulness claim; Series I SoT is `calibrated: false`.
4. `pending` only on allowed triples; among shipped P1 rows that means `(thr.fp_block_sanctuary, new_build)` only.

Vague “phase 1 is done” without those four checks would be unverifiable.

---

## Fresh gate commands (re-run by this gate; packet not trusted alone)

| Command | Result | Evidence |
|---|---|---|
| Official 12-file pytest list | **16 passed**, 0 failed, 174 warnings (`builder.py` / SQLAlchemy `utcnow`), exit 0, 49.60s | this gate, 2026-09-18 |
| `ruff check .` | **All checks passed**, exit 0 | this gate |

Controller `S1-P1-GATE-packet.txt` (16 passed / 52.07s) matches these results. It was not used as sole evidence.

---

## Constraint probes (independent of pytest files)

Live `evaluate_scenario` in a fresh tempdir (not the test modules):

| scenario_id | n | old_build | new_build |
|---|---|---|---|
| gov.no_knob_without_sweep | 2 | pass/none | pass/none |
| gov.anomaly_opens_workflow | 2 | pass/none | pass/none |
| gov.integrity_job_sees_decisions | 2 | pass/none | pass/none |
| des.production_call_shape | 2 | pass/none | pass/none |
| des.no_llm_in_score | 2 | pass/none | pass/none |
| des.ngram_mismatch_halts | 2 | pass/none | pass/none |
| thr.cmdline_injection_survives | 2 | pass/none | pass/none |
| thr.api_key_required | 2 | pass/none | pass/none |
| thr.fp_block_sanctuary | 2 | pass/none | **pending**/none (`stage_b=pending`) |
| use.pipeline_to_triage | 2 | pass/none | pass/none |
| use.ui_sends_api_key | 2 | pass/none | pass/none (named gap `app.js omits X-API-KEY`) |
| use.demo_honesty | 2 | pass/none | pass/none (`unearned_demo_claim` False) |

`PENDING = [('thr.fp_block_sanctuary', 'new_build', 'none')]`. `NONPASS = []`.

`PENDING_ALLOWED` in `core/schemas/scorecard.py:45-51` is exactly the three locked triples. Kernel literal `status="pending"` exists only at `batch/eval/e2e_kernel.py:745` (sanctuary `new_build`). Capability quality `new_build` pending is allowed and **not yet shipped** — that is S1-17..S1-18 work, not a P1 miss.

**Series I `calibrated: false`:** `README.md:22`, `docs/SPEC.md:8`, `docs/eval-kernel.md:12`, `memory-bank/progress.md:15`. Root `SPEC.md` == `docs/SPEC.md` (69207 bytes).

**No usefulness claim:** `docs/eval-kernel.md:13` (“does not claim usefulness”); `README.md:22` (“Not useful yet”); no “the detector is useful” in README.

**Knobs / ingest:** live YAML SHA-256 `26a00c3c17f70d459cf5fff9d2a23f0c230f65ab6e61c5a6ea30c350f39a4701` matches `tests/eval/fixtures/scoring_config_baseline.sha256`; `anomaly_threshold: 45.0`. `git log origin/main..HEAD -- config/scoring_config.yaml` empty. `web/api.py` has no `/api/ingest`.

Twelve YAML stems and twelve pytest modules exist for gov/des/thr/use. Capability YAML/tests are absent — expected; those are S1-17..S1-19.

---

## Why not REJECT

Official P1 commands are green. The three named constraints hold under a live dump, not only packet logs. Rejecting here would block the capability rows this gate exists to authorize.

## Why not ACCEPT-WITH-GAPS

No P1-scoped miss. Carried residuals (P0 standing-suite `precision_gate` contract, uncommitted identical `tests/eval/helpers.py` → `tests/eval/helpers/` move, stale `memory-bank/tasks.md` S1-7..16 line) do not refute proceeding to S1-17..S1-19 and are not this packet’s commands.

---

## Non-blockers (named so they are not forgotten)

- Capability IDs `cap.*` are not in this phase; do not treat missing cap rows as a P1 fail.
- `use.ui_sends_api_key` passes by naming the missing `X-API-KEY`, not by claiming the UI sends one.
- `thr.fp_block_sanctuary` `new_build` must stay `pending` until Sprint 2 earns it. S1-17..S1-19 must not flip that arm.
- Do not staff Sprint 2/3 from this accept. This is a harness-phase exit only.
