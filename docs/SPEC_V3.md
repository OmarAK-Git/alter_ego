ALTER\_EGO — Architecture Specification (v3)

Status: implementation\_plan\_ready; Phase 1 reopened and in progress

Scope: Portfolio project, single-operator deployment, 8–10 week target with explicit cut lines

Last updated: May 2026

Version: 3.0 — revised after Phase 1 self-audit and implementation review



1\. Goal

ALTER\_EGO is a behavioral identity engine for detecting credential misuse, insider activity, and novel threats by learning entity behavior rather than matching static signatures. It ingests authentication and process execution telemetry, builds immutable versioned profiles for users and service accounts, scores new events deterministically against the active point-in-time profile, and produces analyst-facing explanations grounded in recorded evidence.



The portfolio claim is narrow and testable: deterministic behavioral detection with evidence lineage, calibrated evaluation, and constrained LLM explanation after the scoring decision. The LLM never influences the score.



2\. Non-Goals

ALTER\_EGO v1 does not provide real SIEM integration, multi-tenant operation, production IAM, external identity-provider integration, network-layer detection, live production ingest, mobile analyst workflows, Kubernetes operators, or autonomous multi-agent detection. Simulated containment writes to a queue; it does not disable real accounts.



Database-superuser tampering is out of scope. v1 audit immutability is application-layer plus database-role enforcement and hash-chain detection, not WORM-grade storage.



3\. Architecture

ALTER\_EGO uses three execution tiers:



Cold path: profile builds, cohort recomputation, drift calculation, calibration, replay, and synthetic generation.

Hot path: deterministic per-event scoring. No LLM calls, randomness, or external model calls except already-configured local embedding generation where applicable.

Warm path: post-threshold explanation generation and UI rendering. LLM output is validated and may fall back to deterministic templates.

Logical modules are deployed in a compressed four-container topology:



| Container | Modules |

|---|---|

| web | analyst UI, ingest API, explainer API, containment queue API |

| worker | entity resolver, scorer, decision recorder |

| batch | profile builder, synthetic generator, eval harness, replay runner, cohort builder |

| postgres | Postgres, pgvector, operational state |



DuckDB is used as a per-build analytical compute target. It is not a long-lived source of truth. Profile builds materialize a deterministic slice from Postgres into DuckDB, compute artifacts, and write immutable profile versions back to Postgres.



4\. Data Flow

Synthetic or replayed auth/process events are validated against canonical Pydantic schemas.

Ingest stores canonical events and attaches simulation\_partition metadata.

Entity resolver maps raw references to canonical entity\_id and emits resolution\_confidence.

Profile builder reads events through an as\_of cutoff using either a Postgres REPEATABLE READ snapshot or a recorded source\_high\_watermark.

Profile builder writes immutable profile artifacts. If an entity has an uncleared active alert, the new profile is stored as shadow and is not promoted.

Cohort builder writes versioned frozen cohort-prior artifacts on an independent cadence.

Scorer selects the point-in-time active profile for the event and a frozen cohort snapshot for the scoring window.

Decision recorder persists idempotent decisions, feature contributions, lineage, and containment-queue entries when thresholds and confidence criteria are met.

Eval harness joins decisions to ground truth from a side table only outside the scorer.

Explainer generates or templates explanations after threshold crossing.

5\. Tech Stack

Python + Pydantic: typed schemas for events, profiles, decisions, explanations, and scoring config.

Postgres + pgvector: operational state, versioned artifacts, audit records, containment queue, embedding storage.

DuckDB: cold-path profile computation over materialized event windows.

Local embedding model, initially nomic-embed-text: command-line semantic similarity without external per-event dependency. The chosen model ID, version, dimensionality, and input normalizer version are locked before calibration.

Kubernetes kind/k3d: local four-container deployment target.

Terraform or equivalent IaC: required before portfolio-readiness claims, not required to unblock Phase 2 calibration.

LLM provider with pinned non-alias model ID: warm-path explanation only, with lineage and fallback.

6\. Key Design Decisions

6.1 Deterministic Scoring Contract

Hot-path scoring is deterministic over:



event + profile\_version + scoring\_config\_version + scorer\_algorithm\_version



The decision\_id is produced from canonical serialization with sorted keys, normalized UTC datetimes, and stable decimal float handling. Inputs include event\_id, profile\_version, scoring\_config\_version, scorer\_algorithm\_version, and embedding\_model\_version when embeddings participate.



6.2 Point-in-Time Profile Activation

Profile activation is based on effective intervals, not build timestamps. Profile P is active for event time E only when:



P.is\_shadow = false AND P.promoted\_at <= E < P.superseded\_at



Profile artifacts include promoted\_at and superseded\_at. Shadow profiles may be stored for analysis but cannot replace active scoring profiles until the relevant alert is cleared.



6.3 Profile Immutability

Committed profiles are immutable. Pydantic profile models are frozen. Database roles for application writes have INSERT only on committed profile artifact tables and no UPDATE or DELETE. Rebuilds create new versions.



6.4 Six-Feature Baseline Scorer

Phase 1 is not complete until all applicable six features are real, bounded, tested, and nonzero on positive fixtures:



login\_hour\_rarity

geolocation\_rarity

endpoint\_set\_rarity

process\_name\_rarity

command\_line\_embedding\_similarity

service\_account\_execution\_frequency\_deviation

Categorical rarity uses Laplace-smoothed log-likelihood with the same alpha used by drift calculations. Per-feature contributions are clipped by contribution\_scale\_max from scoring\_config.



6.5 Confidence Model

Confidence is evidence-count based, not a fixed cohort-tier constant. The default form is:



confidence = n / (n + k)



where n is the relevant per-feature observation count and k is a calibrated scoring-config parameter. Cohort tier may cap confidence, but cannot replace observation-count evidence.



6.6 Cohort Chain

v1 uses a practical three-step fallback:



entity-local -> role cohort -> unsupported terminus



The unsupported terminus sets cohort\_unsupported = true, applies a higher containment confidence requirement, and surfaces a UI warning. Broader parent/global priors are deferred unless role cohorts prove too sparse in tests.



Cohort priors are recomputed on a schedule independent of profile builds. Cohort-prior artifacts are versioned and frozen per scoring window.



6.7 Scenario 3 Gate

Scenario 3 performance claims require an implemented cohort novelty gate with provisional defaults: max\_changed\_fraction, min\_cohort\_size, min\_clean\_observation\_count, and cohort\_gate\_window\_days. If this mechanism is not implemented, Scenario 3 may be demonstrated qualitatively but no calibrated performance claim may be reported.



6.8 Embedding Lock

Before Phase 2, the embedding model ID, model version, dimensionality, and embedding\_input\_normalizer\_version must be locked and recorded on every profile artifact. Legacy profiles must be rebuilt to populate this metadata. The input normalizer must document preserved and stripped fields because command lines are low-trust, security-relevant strings.



A full future pgvector dimensionality migration playbook is required before portfolio-readiness claims, but Phase 2 only requires the current model/dimensionality lock and current schema correctness.



6.9 Evaluation Discipline

No precision/recall, F1, or production-grade detection claim may be reported before Phase 2 clears. Phase 2 requires benign-only false-positive sweeps and correlated benign-change scenarios before mixed anomaly sweeps. Ground truth remains in eval\_ground\_truth, never on event records and never queryable by scorer code.



6.10 Audit Governance

Scoring config changes are versioned records with previous\_config\_hash, new\_config\_hash, author, timestamp, and change\_reason. Calibration must produce a tracked sequence of config records.



If project materials claim audit immutability during calibration, hash chaining and a per-run integrity assertion are Phase 2 blockers. If not completed, the materials must explicitly downgrade the claim to append-only application behavior pending portfolio-readiness hardening.



6.11 LLM Boundary

The LLM is used only after scoring for analyst explanation. Output must validate against ExplanationRecord. Confidence labels are computed by the service, not selected by the LLM. Lineage, not provider determinism, is authoritative.



7\. Acceptance Criteria

Phase 2 calibration may begin only when:



All six applicable scoring features are implemented and tested.

Embedding metadata and current pgvector dimensionality are locked.

Legacy profiles are rebuilt with embedding metadata.

Profile effective intervals and point-in-time selection are tested.

Committed profile immutability is enforced at model and DB-role level.

Profile-builder snapshot/high-watermark reproducibility is tested.

Observation-count confidence is implemented and configurable.

Three-step cohort fallback and unsupported terminus are implemented.

Frozen cohort-prior snapshots exist.

Scenario 3 novelty gate exists or Scenario 3 claims are deferred.

Correlated benign-change and benign-only false-positive tests exist.

Resolver split/collision tests emit low\_resolution\_confidence.

Shadow-profile non-promotion and calibration exclusion tests pass.

Canonical decision serialization is reproducible across processes.

Evidence-binding reconstruction of raw\_score passes within tolerance.

Scorer cannot import or query ground truth or simulation-partition evidence.

Containment queue write path exists.

Staged calibration process covers anomaly threshold, confidence floor, and containment threshold.

Scoring-config governance records are implemented.

ExplanationRecord schema and tests are committed.

Portfolio-readiness claims require the separate gate in §9.



8\. Risks and Mitigations

| Risk | Mitigation |

|---|---|

| Stubbed features invalidate calibration | Block Phase 2 until all six features are real and tested |

| Sparse data creates false confidence | Observation-count confidence with calibrated caps |

| Shadow profiles contaminate scoring | Effective intervals, non-promotion tests, calibration exclusion tests |

| Cohort-wide benign changes inflate precision | Correlated benign generator and benign-only sweeps |

| Scenario 3 overclaimed without gate | Implement novelty gate or defer Scenario 3 performance claims |

| Audit claims exceed implementation | Complete DB hash-chain integrity or downgrade project materials |

| Embedding migration breaks profiles | Lock current model before calibration; require migration playbook before portfolio readiness |

| Resolver collisions corrupt identity | Collision/split tests and low-confidence flags |

| Prompt injection via command lines | Slot isolation, normalizer threat model, schema validation, prohibited-content checks |



9\. Portfolio Readiness Gate

Before claiming production-grade infrastructure, the project must ship:



IaC for the four-container topology.

CI checks documented and running.

Empirical LLM determinism check against pinned non-alias model.

Full pgvector migration playbook for future dimensionality changes.

Replay runner end to end with replay\_run\_id audit path.

Staleness circuit breaker and active-alert mandatory escalation.

max\_profile\_build\_block\_days supervisor escalation.

Counterfactual consistency corpus and harness.

Schema-version mismatch detection at scorer startup.

These are binding portfolio gates, not optional future-work decorations.

