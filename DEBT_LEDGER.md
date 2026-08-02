# DEBT_LEDGER — recoverable MVP-era traces

**Extracted:** 2026-07-30 · **IDs normalized:** 2026-07-30  
**Method:** Structured sweeps over comments, git messages, hardcoded constants, exception handlers, abstractions, complexity, tests, dependencies, stubs, and `scratch/`.  
**Companion:** [`AS_BUILT.md`](AS_BUILT.md)

**Rules:** Only findable traces. No invented debt. Severity is recovery priority, not a CVE rating.

---

## How to read this ledger

| Field | Meaning |
|-------|---------|
| ID | Stable `DEBT-###` handle (do not renumber; append new IDs at end) |
| Category | Sweep bucket (A–L) |
| Location | Path (and line when pinned) |
| Evidence | Quote or measurable fact |
| Severity | `S1` fix soon · `S2` schedule · `S3` cleanup · `INFO` observation / not actionable debt |
| Recovery | Smallest honest next step |

### Severity scale

| Level | Meaning |
|-------|---------|
| **S1** | Wrong defaults, broken SoT, undeclared runtime deps, untested critical path, active calibration residual that blocks honesty claims |
| **S2** | Magic numbers, soft-fail contracts, complexity hotspots, Path-B deferrals, weak coverage |
| **S3** | Cosmetic / local cleanup, historical git noise, optional docs |
| **INFO** | Negative finding (no markers), non-debt note, or alias pointer already covered by another ID |

Classic `# TODO` / `# FIXME` / `# HACK` / `# XXX` markers are **absent** from production `*.py`. Debt is expressed as deferred YAML knobs, wrong fallbacks, “for now”/“hacky” comments, stubs, and calibration residuals.

---

## Master ledger

| ID | Category | Location | Evidence | Severity | Recovery |
|----|----------|----------|----------|----------|----------|
| DEBT-001 | A comments | production `*.py` | Zero matches for `# TODO`, `# FIXME`, `# HACK`, `# XXX`, `# TEMP` | INFO | N/A — debt uses defer flags / wrong defaults instead |
| DEBT-002 | A comments | `core/database.py:48` | `# (This is a bit hacky, better to use a factory…)` | S3 | Explicit Vector type factory for SQLite vs pgvector |
| DEBT-003 | B constants | `batch/profile_builder/builder.py:425` | `config.get("drift_threshold", 45.0)` — live YAML is **5.0** | S1 | Default `5.0` or fail if YAML missing |
| DEBT-004 | B constants | `worker/scorer.py:393` | `contribution_scale_max` fallback **20.0** — YAML **50.0** | S1 | Align fallback to 50.0 |
| DEBT-005 | B constants | `worker/scorer.py:345` | Missing-file fallback `version: "2.1"` — live **2.2** | S2 | Fail closed or stamp 2.2 |
| DEBT-006 | B constants | `worker/scorer.py:536` | Embed weight fallback **5.0** — YAML **2.0** | S2 | Match YAML |
| DEBT-007 | B constants | `worker/scorer.py` (~170–181) | `_COHORT_CACHE_TTL=300`, `_NOVELTY_CACHE_MAX=2048`, `_NOVELTY_CACHE_TTL=300` — not in YAML | S2 | Config or document as ops constants |
| DEBT-008 | B constants | `worker/scorer.py:354–358` | Cohort hist floors `>= 20` / `>= 100` | S2 | Config or SPEC-named constants |
| DEBT-009 | B constants | `worker/scorer.py:520–523` | Hardcoded vocab sizes `24, 100, 50, 1000` + baseline bits | S2 | Move to feature schema / config |
| DEBT-010 | B constants | `worker/scorer.py:537` | `(dist - 0.50) * 50.0 * weight_emb` | S2 | Document or config-ize transform |
| DEBT-011 | B constants | `worker/scorer.py:549` | `dev_period * 5.0 * weight_period` | S2 | Same |
| DEBT-012 | B constants | `worker/scorer.py:386` | Periodicity `cv / 0.3` | S3 | Document |
| DEBT-013 | B constants | `worker/scorer.py` (~611–635) | Hardcoded contrib confidences `0.7`/`0.6`; damping `threshold - 5.0` | S2 | Named constants / config |
| DEBT-014 | B constants | `batch/profile_builder/builder.py:666` | `MIN_NORM_COHORT = 3` | S2 | YAML next to cohort gates |
| DEBT-015 | B constants | `worker/vectorizer.py:32`, `core/models.py:42` | Literal `128` alongside `DEFAULT_EMBEDDING_DIMENSIONALITY` | S3 | Single source only |
| DEBT-016 | B constants | `worker/resolver.py` | `LOW_RESOLUTION_THRESHOLD=0.75`, `COLLISION_SPLIT_CONFIDENCE=0.3`, unknown conf `0.5` | S2 | Config or schema |
| DEBT-017 | B constants | `worker/explainer.py` | Slot max 512; confidence bands 0.2/0.4/0.6/0.8; HTTP timeouts 30/60 | S3 | Document; optional config |
| DEBT-018 | B constants | `core/attestation.py:11–16` | `QUIET_WINDOW_DAYS=3`, `MIN_DWELL_BUILDS=2`, `ALPHA_PROD=0.02`, `ALPHA_ANCHOR=0.05` — YAML write deferred | S1 | Wire to YAML (S6.3 hygiene) or declare code-permanent SoT |
| DEBT-019 | B constants | `config/scoring_config.yaml` | `total_volume_delta` implemented shadow-computed (`features.total_volume_delta.enabled: false`); calendar/gap keys still deferred | S1 | **Partial recovery** — Phase 2 (`fc8f530`..`a916d13`, `worker/scorer.py` `compute_volume_rarity`, `builder.py` hourly counts); Series F governance done; `enabled: false` — not fully closed until governance sign-off flips flag |
| DEBT-020 | B constants | `builder.py:422–424` | Drift-weight fallbacks all `1.0` / embed `2.0` vs YAML `5/5/5/20/40` | S2 | Align fallbacks |
| DEBT-021 | C exceptions | `worker/explainer.py:180–181` | ADC discovery: `except Exception: pass` | S2 | Log; don’t silent-fail auth probe |
| DEBT-022 | C exceptions | `worker/explainer.py:313–314` | StubLLM: `except Exception: return "{}"` | S3 | Remove dead branch |
| DEBT-023 | C exceptions | `worker/explainer.py:641–643` | Broad `except Exception` → template fallback | S2 | Narrow types; intentional product path |
| DEBT-024 | C exceptions | `worker/explainer.py:49–50` | `except OSError` on `.env` read → warning | S3 | Acceptable; optional escalate |
| DEBT-025 | C exceptions | `batch/replay_runner.py:159–161` | Per-event except → warn + continue | S2 | Document fail-soft; optional fail-fast |
| DEBT-026 | C exceptions | `scratch/check_db.py:21–22` | `except Exception:` | S3 | Scratch only |
| DEBT-027 | D abstractions | `scripts/demo_path.py:61–64` | `HttpClient` Protocol — one impl | S3 | Keep for DI or inline |
| DEBT-028 | D abstractions | `core/schemas/config.py` vs YAML | `ScoringConfig` fields (`drift_weight`, `cohort_minimums`, `suppressed_decision_aging_days`, …) **≠** `scoring_config.yaml` | S1 | Unify schema with YAML or stop dual SoT |
| DEBT-029 | D abstractions | `persist_config.py:15` | `ScoringConfig(**config_data)` on full YAML — shape mismatch | S1 | Mapping layer or delete script |
| DEBT-030 | D abstractions | `ConfigStore` / `ProfileStore` | No ABC; one backend each | INFO | Not harmful; don’t add factories until second backend |
| DEBT-031 | D abstractions | `worker/explainer.py` `LLMProvider` | Base + `RealLLMProvider` + `StubLLMProvider` | INFO | Multi-impl; not single-impl debt |
| DEBT-032 | E complexity | `batch/profile_builder/builder.py:408` `build_profiles` | ~391 LOC, cc≈34; file ~738–798 LOC | S1 | Split load / KL / accumulate / persist |
| DEBT-033 | E complexity | `worker/scorer.py:389` `score_event` | ~292 LOC, cc≈31; file ~659–738 LOC | S1 | Extract rarity / embed / drift / assemble |
| DEBT-034 | E complexity | `worker/explainer.py:537` `generate_explanation` | ~129 LOC, cc≈21 | S2 | Split queue / LLM / validate / persist |
| DEBT-035 | E complexity | `builder.py:256` `_auto_resolve_quiet_attested_alerts` | ~76 LOC, cc≈17 | S2 | Extract attest predicates |
| DEBT-036 | E complexity | `web/api.py:224` `_build_mandatory_escalations` | ~51 LOC, cc≈13 | S2 | Table-driven rules |
| DEBT-037 | E complexity | `batch/synthetic/generator.py` `inject_scenario_5_*` | ~102 LOC; file ~407+ LOC | S2 | Per-scenario modules |
| DEBT-038 | E complexity | `web/api.py:82` `_compute_entity_attestation` | ~94 LOC | S2 | Move next to `core/attestation.py` |
| DEBT-039 | F untested | `worker/ingest.py` | No `tests/**` imports of `ingest_events` / `ingest_ground_truth` | S1 | JSONL round-trip + idempotency |
| DEBT-040 | F untested | `worker/resolver.py` `process_unresolved_events` | Tests focus on `resolve_entity` | S2 | Batch unresolved→resolved test |
| DEBT-041 | F untested | `batch/eval/{runner,calibrate,rescore,report,analyze_misses}.py` | No pytest ownership | S1 | Tiny fixture smoke for metrics/PR |
| DEBT-042 | F untested | `worker/vectorizer.py` `normalize_command_line` | No direct unit tests | S2 | Strip/hex/case unit tests |
| DEBT-043 | F untested | `core/settings.py`, `core/database.py` | No dedicated tests | S3 | Env / dialect smoke |
| DEBT-044 | F untested | `persist_config.py`, `verify_lineage.py` | Root scripts; lineage asserts stale `"2.0"` | S2 | Repair or archive |
| DEBT-045 | F untested | `process_unscored_events` no-profile skip | Fail-open skip; weak dedicated coverage | S2 | Assert unscored remain unscored |
| DEBT-046 | G deps | `pyproject.toml` dependencies | Loose lowers only; **no upper pins / lockfile** | S2 | Ceilings or lock for eval reproducibility |
| DEBT-047 | G deps | `optional-dependencies.dev` | `pytest`, `ruff`, `mypy` only | S3 | OK; add types packages if needed |
| DEBT-048 | G deps | undeclared imports | `numpy` (vectorizer/scorer/builder), `requests` (explainer/scripts), `google-auth` (Vertex) | S1 | Declare deps / `llm` extra |
| DEBT-049 | G deps | no `requirements*.txt` | None in repo | INFO | pyproject-only is fine if locked |
| DEBT-050 | G deps | `pyproject.toml` version | `version = "0.1.0"` | S3 | Bump on release |
| DEBT-051 | H stubs | `worker/scorer.py` | `compute_volume_rarity` wired; `score_vol=0` + `volume_delta_deferred` when `enabled: false` (Phase 2, 2026-07-30 plan) | S1 | **Partial recovery** — Phase 2 scorer + builder histogram (`fc8f530`..`a916d13`); Series F governance done; close after `enabled` governance flip |
| DEBT-052 | H stubs | `worker/explainer.py:121–123` | `NotImplementedError` on base `LLMProvider` | INFO | Expected ABC-style base |
| DEBT-053 | H stubs | `worker/explainer.py:303–314` | `StubLLMProvider` | S3 | Keep test/offline; mark |
| DEBT-054 | H stubs | `worker/config_store.py:30–37` | “strict for now” + bare `pass` — **does not reject** duplicate hash | S2 | Raise or document allow |
| DEBT-055 | H stubs | `ScoringConfig.suppressed_decision_aging_days` | In Pydantic schema; **absent** from live YAML | S2 | Align triad schema↔YAML↔SPEC |
| DEBT-056 | H stubs | `verify_lineage.py` | Assumes scorer YAML version `"2.0"` vs live **2.2** | S2 | Update or retire |
| DEBT-057 | H stubs | `ReplayRequest` config version fields | Schema fields unused by `run_replay` | S2 | Wire or drop fields |
| DEBT-058 | I language | `worker/resolver.py:27` | `For Phase 1, we use deterministic prefixes.` | S2 | Real IdP mapping when available |
| DEBT-059 | J git | subject grep | Almost empty debt-named subjects (“Ship S…”, “Harden…”) | INFO | Prefer code/YAML traces |
| DEBT-060 | J git | `c44ce00` (2026-05-11) | Pickaxe hit for `"for now"` (`phase 2 step 5`) | S3 | Historical; verify remnant |
| DEBT-061 | J git | early history | Opaque subjects (`.`, `more calibrations`, …) | S3 | Prefer `.workflow/` packet trails |
| DEBT-062 | K scratch | `scratch/run_series_c_sweep.py` | “Do not claim CALIBRATED from this script alone.” | S1 | Residual Series C work |
| DEBT-063 | K scratch | `scratch/run_series_d_sweep.py` | Same + D4 harness; `calibrated: False` | S1 | Residual Series D / FP storm |
| DEBT-064 | K scratch | `scratch/diagnose_series_c_s2.py` | One-shot S2 diagnosis | S2 | Keep until S2 residual closed |
| DEBT-065 | K scratch | `scratch/diagnose_d4_engagement.py` | D4 engagement diagnosis | S2 | Archive after governance settled |
| DEBT-066 | K scratch | `scratch/run_s31_sweep.py`, `s32_refresh_calibration_docs.py` | S3.1/S3.2 tooling | S2 | Prefer `batch/eval` as SoT |
| DEBT-067 | K scratch | `scratch/analyze_step{1,2,3,4}.py` | Stepwise calibration drivers | S2 | Consolidate or freeze |
| DEBT-068 | K scratch | `scratch/test_cohort_gate.py` | Fleet `COHORT_DRIFT` decision implemented in builder (`fleet_drift_enabled: false`); `min_clean_observation_count` still scratch-only | S1 | **Partial recovery** — Phase 3 fleet `COHORT_DRIFT` in `builder.py` (`fc8f530`..`b63884c`); Series G governance done; close after `enabled` flip + prior-update gate |
| DEBT-069 | K scratch | `scratch/scenario3_sweep.py`, `debug_fp.py`, `debug_benign.py`, … | Scenario-3 / FP leftovers | S2 | Tie to residual-risk docs or archive |
| DEBT-070 | K scratch | `scratch/series_c_d4_engagement_run.log` | Untracked run log | S3 | gitignore; don’t commit |
| DEBT-071 | K scratch | `memory-bank/progress.md` | Living defer inventory + Not CALIBRATED + attestation YAML deferred | S1 | Treat as debt SoT alongside this ledger |
| DEBT-072 | L deferrals | SPEC / progress S4.3 | Suppressed-decision aging + jitter; `age_jitter_hours` unread | S1 | Implement or delete knob |
| DEBT-073 | L deferrals | SPEC / progress S4.6 | Calendar dual-score / telemetry gap; `max_calendar_adjustment`, `gap_windows.*` | S1 | Implement or delete knobs |
| DEBT-074 | L deferrals | SPEC / progress S4.7 | Asset / blast-radius context — no artifacts/API | S2 | Greenfield packet or keep Path B |
| DEBT-075 | L deferrals | SPEC / progress S5.11 | Fleet-level `cohort_drift` parallel detector shipped (`fleet_drift_enabled: false`); independent cohort artifacts + prior-update gates still deferred | S1 | **Partial recovery** — Phase 3 fleet detector (`fc8f530`..`b63884c`, see DEBT-068); Series G governance done; S5.11 Path B unchanged; close after `enabled` flip |
| DEBT-076 | L deferrals | SPEC / progress S2.7 | Profile lifecycle states — no `lifecycle_state` | S2 | Spec-aligned ship or keep Path B |
| DEBT-077 | L deferrals | SPEC / progress S5.2 | K8s / Terraform deferred; compose-as-IaC | S3 | Optional portfolio IaC |
| DEBT-078 | B constants | `batch/profile_builder/builder.py:748–777` | Cadence drift uses **absolute** `cadence_cov` (same value per prev profile) not Δ vs baseline `cadence_cov`; pairs with DEBT-012 `cv/0.3` floor | S2 | Compute `abs(cadence_cov - prev.cadence_cov)` or KL-style delta before weight sweeps; Series I query 2026-08-02: 71% `cadence_cov==0` but 29% non-zero (mean 0.28) — sweep still informative, kill path **not** taken |

**ID range in use:** `DEBT-001` … `DEBT-077`. Next new item: `DEBT-078`.

**Alias notes (not separate IDs):** language hits “hacky” / “for now” on `database.py`, `config_store.py`, `attestation.py`, `volume_delta`, and YAML `# Deferred` comments are covered by DEBT-002, DEBT-054, DEBT-018, DEBT-051, DEBT-019 respectively. Broken `persist_config` is DEBT-029 (same root as DEBT-028).

---

## Severity rollup

| Severity | Count (approx) | Highest-signal IDs |
|----------|----------------|--------------------|
| **S1** | 20 | DEBT-003, DEBT-004, DEBT-018, DEBT-019, DEBT-028, DEBT-029, DEBT-032, DEBT-033, DEBT-039, DEBT-041, DEBT-048, DEBT-051, DEBT-062, DEBT-063, DEBT-068, DEBT-071–075 |
| **S2** | 38 | Magic numbers DEBT-005–011/013/014/016/020; exceptions DEBT-021/023/025; complexity DEBT-034–038; coverage DEBT-040/042/044/045; Path-B L items |
| **S3** | 14 | Local cleanup / historical git / version bump |
| **INFO** | 5 | DEBT-001, DEBT-030, DEBT-031, DEBT-049, DEBT-052, DEBT-059 |

---

## Suggested recovery order

1. **S1 defaults + deps:** DEBT-003, DEBT-004, DEBT-048.  
2. **S1 config SoT:** DEBT-028, DEBT-029 (and DEBT-055/056).  
3. **S1 deferrals / stubs:** DEBT-019, DEBT-051, DEBT-072–075 (implement vs delete).  
4. **S1 attestation YAML:** DEBT-018 (same theme as portfolio note in DEBT-071).  
5. **S1 tests:** DEBT-039, DEBT-041.  
6. **S1 complexity (after ownership clear):** DEBT-032, DEBT-033.  
7. **Calibration honesty:** DEBT-062, DEBT-063, DEBT-068, DEBT-071.

---

*End of DEBT_LEDGER. As-built system → [`AS_BUILT.md`](AS_BUILT.md).*
