# Packet R-EXIT-GATE

- Run: `.workflow/2026-07-30-reverse-spec-rfc-remediation`
- Mode: `in_session_grok` — gate verdict by `cursor-grok-4.5-high`
  (operator override 2026-07-30: all future gates on Grok until told otherwise;
  re-opened after prior Opus 5 API-limit block)
- Scope: `run_exit` (run-wide gaps ARE in scope here, unlike the task packets)

## What this run claimed to do

Remediate the two independently-verified RFCs from the `5638f86d…-rfcs.md`
reverse-spec review:

- **RFC-006 / packet R1** — `tests/batch/profile_builder/builder.py` was never
  collected by pytest (default `test_*.py` pattern, no `python_files` override),
  so the module the ledger flags as the highest-complexity hotspot (DEBT-032,
  cc≈34) had zero CI execution. Renamed to `test_builder.py`.
- **RFC-005 / packet R2** — `build_profiles` fully materialized both event
  windows via `.scalars().all()` before writing temp JSONL. Replaced with
  chunked `yield_per` streaming straight to the files.

Explicitly NOT implemented, by the plan's own verification table: RFC-001
(rejected — fabricated premise), RFC-002 / RFC-003 (KILL affirmed), RFC-004
(dropped by the citation breaker).

## Gate command results (test-runner, fresh run)

- `pytest -v --tb=short --ignore=tests/live` → **165 passed**, 0 failed, 0 skipped, 23.96s
  (baseline before this run: 163)
- `ruff check .` → **All checks passed!**
- No stray `temp_events_hist_*.jsonl` / `temp_events_recent_*.jsonl` in repo root
- Evidence: `results/R-EXIT-GATE-pytest.txt`, `results/R-EXIT-GATE-ruff.txt`

## Commits produced (all scoped, verified via `git diff --name-only 2599b79 HEAD`)

| SHA | Subject | Files |
|---|---|---|
| `5311d3a` | test: fix pytest discovery for profile builder aggregation test | rename only, R100, 0 insertions/deletions |
| `2aaa4e0` | fix: stream Postgres extraction to temp JSONL in bounded chunks | `batch/profile_builder/builder.py`, `tests/batch/test_profile_build_snapshot.py` |
| `019487e` | style: annotate `_BUILD_EXTRACT_CHUNK_SIZE` as int per plan interface | `batch/profile_builder/builder.py` |

Total surface across the run: exactly three files —
`batch/profile_builder/builder.py`, `tests/batch/profile_builder/test_builder.py`,
`tests/batch/test_profile_build_snapshot.py`. `config/scoring_config.yaml`
untouched.

## Per-task verdicts already recorded

- R1 — skeptic `survives` (`cursor-grok-4.5-high`), code review skipped with
  recorded reason (pure R100 rename, identical blob).
- R2 — code review 0 blocking / 3 non-blocking (note 1 fixed in `019487e`);
  skeptic `survives` (`cursor-grok-4.5-high`), including an anti-vacuity probe
  that inserted a `break` after the first chunk and confirmed the regression
  test fails (`assert 2 == 5`), then restored the tree clean.

## Environment observation for the gate to weigh

`git status --short` at gate time shows two entries that were NOT in the
working tree snapshot at run start and are NOT attributable to any packet in
this run:

- ` M docs/residual-risk-drift-hypotheses.md` (+42 lines, hypotheses H12–H15 on
  cadence/geo-velocity/signal-agreement drift research)
- `?? alter-ego-drift-gap-evaluation.md` (mtime 2:06 PM, before this run started)

Both are drift-research content, thematically unrelated to RFC-005/006, and
both are uncommitted — they are outside every packet's declared write scope and
none of this run's three commits contain them. The plan's global constraints
forbid touching unrelated pre-existing artifacts, so they were deliberately
left alone. The gate should decide whether this is acceptable residual or a
blocker.

## Accepted non-blocking residuals

1. Partial temp files on a mid-stream exception rely on the pre-existing
   `finally` cleanup block; this diff does not worsen the pattern.
2. The regression test cannot prove server-side DB round-trips on sqlite — it
   proves row completeness across chunk boundaries, which is the property that
   matters for correctness.
3. `mypy .` reports 65 pre-existing errors repo-wide, none introduced here.
   mypy is not a gate command for this run.
