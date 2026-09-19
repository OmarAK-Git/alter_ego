# S1-17 implement / review / verify packet

**Task:** `cap.attributed_s2_s3_s5`
**Plan:** `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md` Task 17 (~2462–2610)
**Claim:** `old_build` records attributed S2/S3/S5 cells on compact seed-42 fixture (`n>=1`, not vacuous R=1.0); `new_build` is `pending`. Corpus is `ci_compact_seed42_shaped`. Do not compare to Series I TP=54. Do not claim usefulness.

## Files
- Create: `tests/eval/scenarios/cap.attributed_s2_s3_s5.yaml`
- Create: `tests/eval/test_cap_attributed_s2_s3_s5.py`
- Modify: `batch/eval/kernel_fixtures.py` (`write_compact_seed42_s2_s3_s5_jsonl`)
- Modify: `batch/eval/e2e_kernel.py` (helpers + dispatch)

## Locked
- No `scoring_config.yaml` edits
- No `/api/ingest`, Series J, FakeProvider
- Reuse existing `attributed_tp` (already in `e2e_kernel.py`)
- `inject_scenario_5_patient_cycle(events, labels, start_ts, exclude_entity_ids=...)` — live signature; do not invent a second inject
- `new_build` skips `run_pipeline` (same pattern as sanctuary)
- If `run_pipeline` > ~2 min, drop baseline days from 10 to 8; keep the three injects

## Controller
```
PYTHONPATH=. pytest tests/eval/test_cap_attributed_s2_s3_s5.py -v --tb=short
ruff check batch/eval/e2e_kernel.py batch/eval/kernel_fixtures.py tests/eval/test_cap_attributed_s2_s3_s5.py
```

Expected: 1 passed; ruff clean.

## Commit
`Record attributed S2/S3/S5 B3a baseline; leave quality new_build pending`
