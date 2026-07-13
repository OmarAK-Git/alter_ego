# Project Brief

ALTER_EGO is a local-first **behavioral identity detection** (UEBA-style) portfolio system.

It profiles how users and service accounts normally behave from auth/process telemetry, then scores new events against immutable point-in-time profiles to surface credential misuse, lateral movement, and slow behavioral drift — with deterministic scoring, versioned config, and audit lineage.

## Portfolio claim (narrow)

Deterministic behavioral detection with evidence lineage, calibrated evaluation against four synthetic attack scenarios, and constrained post-threshold explanation. The LLM never influences the score.

## Non-goals (v1)

Real SIEM integration, multi-tenant SaaS, production IAM disablement, live enterprise ingest, Kubernetes operators, autonomous multi-agent detection.
