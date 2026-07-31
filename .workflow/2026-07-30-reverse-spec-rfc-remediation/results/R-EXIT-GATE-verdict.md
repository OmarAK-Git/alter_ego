# R-EXIT-GATE verdict

- **model:** `cursor-grok-4.5-high`
- **packet:** `R-EXIT-GATE`
- **timestamp:** `2026-07-30T20:00:42-04:00`
- **authority:** operator-authorized Grok re-open after prior Opus 5 API-limit block
- **verdict:** `ACCEPT-WITH-GAPS`

---

## Verdict

**ACCEPT-WITH-GAPS**

All six `state.json` success criteria hold under fresh independent checks. Remediation commits are scoped. Fresh gate commands are green (165 / ruff clean). RFC-001 rejection is correct. Unrelated working-tree residue is out of scope and does not block.

One real residual vs the run's stated memory-bounding intent is recorded below. It does not make the remediation cosmetic, and it does not reopen R1/R2 as failed — but it prevents a clean `ACCEPT`.

---

## Fresh gate commands (re-run by this gate; not trusted from prior logs alone)

| Command | Result | Evidence |
|---|---|---|
| `pytest -v --tb=short --ignore=tests/live` | **165 passed**, 0 failed, 0 skipped, 21.44s | `results/R-EXIT-GATE-pytest.txt` |
| `ruff check .` | **All checks passed!** | `results/R-EXIT-GATE-ruff.txt` |

Arithmetic check: baseline 163 → +1 R1 rename discovery → +1 R2 regression = **165**. Matches.

---

## Success criteria (checked against code, not result files alone)

| # | Criterion | Ruling | Evidence |
|---|---|---|---|
| 1 | `tests/batch/profile_builder/test_builder.py` collected under default discovery | **MET** | File exists; `builder.py` gone. `pytest …/profile_builder/ --collect-only` → 1 item. `pyproject.toml` has `testpaths=["tests"]` and **no** `python_files` override. |
| 2 | No `.scalars().all()` for hist/recent; stream via `yield_per` | **MET** | `_stream_events_to_jsonl` at `builder.py:411-433` uses `stmt.execution_options(yield_per=chunk_size)`. Call sites L502 / L534. Remaining `.scalars().all()` are alerts / prev-profiles only. |
| 3 | Zero `events_hist` / `events_recent` references in `builder.py` | **MET** | `Select-String` over `builder.py` → no matches. |
| 4 | Trailing `chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE` (5000) | **MET** | `builder.py:408` (`: int = 5000`); signature `builder.py:436`. |
| 5 | Regression test forces multi-chunk and asserts full aggregate | **MET** | `tests/batch/test_profile_build_snapshot.py:72-95` — 5 rows, `chunk_size=2`, asserts `total_events == 5`. |
| 6 | Full suite green + ruff clean at exit gate | **MET** | Fresh runs above. |

---

## Scope discipline

Remediation commits only:

| SHA | Files |
|---|---|
| `5311d3a` | `tests/batch/profile_builder/test_builder.py` (R100 rename) |
| `2aaa4e0` | `batch/profile_builder/builder.py`, `tests/batch/test_profile_build_snapshot.py` |
| `019487e` | `batch/profile_builder/builder.py` |

`git diff 5311d3a^..019487e --name-only` → exactly those three paths.
`git show 5311d3a 2aaa4e0 019487e -- config/scoring_config.yaml` → empty (untouched).

Later commit `d0f41cd` (H12–H15 drift design docs) is **not** part of this remediation; it touches only `docs/residual-risk-drift-hypotheses.md` and a design spec under `docs/superpowers/specs/`.

---

## Memory-bounding attack (RFC-005)

**What is real (not cosmetic):**
- The full-window Python lists from `.scalars().all()` are gone.
- Rows are written one-at-a-time to temp JSONL under `yield_per`.
- Downstream DuckDB reads JSONL from disk and returns **aggregates** (`histogram`, `COUNT`, `list(command_line)` per entity). It does **not** reconstitute a Python list of `ResolvedEventModel` for either window.

**Gap (recorded):**
- `_stream_events_to_jsonl` never `expunge`s / clears loaded ORM instances. Under SQLAlchemy, `yield_per` partitions DB fetch size but the `Session` identity map still retains every yielded `ResolvedEventModel` for the life of the session. Peak **ORM** memory therefore still scales with window size, contrary to the plan/architecture claim of “one chunk at a time regardless of window size.”
- Pre-existing (not introduced here; not a separate gap of this run): DuckDB `list(command_line)` still materializes per-entity command-line lists into Python after aggregation.

---

## Unrelated working-tree files

**Ruling: accepted residual / out of scope — not a blocker.**

Present uncommitted/untracked items (`AS_BUILT.md`, `DEBT_LEDGER.md`, `alter-ego-drift-gap-evaluation.md`, drift expansion plan, RFCs, scratch logs, memory-bank mirrors, this `.workflow/` tree, etc.) were **not** swept into `5311d3a` / `2aaa4e0` / `019487e`. Operator has plans for them. Constraint satisfied.

---

## RFC-001 rejection spot-check

**Ruling: rejection is correct.**

- `batch/synthetic/scenarios.py::ScenarioType` holds semantic attack labels (`SHARP_CREDENTIAL_MISUSE`, `SLOW_ROLL_BEHAVIORAL_DRIFT`, …) — not partition strings.
- `builder.py` never imports or reads `ScenarioType`.
- Real filter is hardcoded `builder_partitions = ("production", "eval_scenario_2", "eval_scenario_3", "eval_scenario_5")` at `builder.py:478`, used only in SQL `.in_()` (`L483`, `L492`). Unrecognized partition strings are silently excluded, not a crash path.

Deliberate non-implementation of RFC-001 (and RFC-002/003 KILL / RFC-004 drop) is properly justified.

---

## Gaps recorded

1. **Session identity-map retention under streamed extraction:** `yield_per` removes the unbounded Python result list, but without `expunge`/session-per-chunk the ORM identity map still accumulates the full hist (then recent) window. Plan wording that peak Python memory is bounded to one chunk is overstated. Remediation remains a real improvement over `.scalars().all()` + list materialization; this is an incompleteness of the memory bound, not a fake fix.

---

## Non-gaps / accepted residuals (affirm prior packet notes)

- Partial temp-file cleanup on mid-stream exception relies on pre-existing `finally` — not worsened.
- Sqlite regression proves row completeness across chunk boundaries, not Postgres server-side round-trip count.
- `mypy` pre-existing noise; not a gate command for this run.
