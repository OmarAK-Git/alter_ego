# Orchestration — Drift Capability Expansion (H12–H15 + Phase 0)

T3 GSD run loaded from `docs/superpowers/plans/2026-07-30-drift-detection-capability-expansion.md`.
Queue SoT: `.workflow/autopilot-queue.json`. Machine state: `state.json`.

## Phases

| Phase | Scope | Sweep |
|---|---|---|
| 0 | Shadow-aware point-rarity/embedding baseline | Series E |
| 1–2 | Cadence CoV + volume delta | Series F |
| 3–4 | Fleet cohort drift + geo-velocity | Series G |
| 5–6 | Precision gate Stage A + staged sequences | Series H |

All new signals ship **shadow-computed, `enabled: false`** — zero behavioral diff until governance flip.

## Agent routing

| Stage | Agent | Model |
|---|---|---|
| Research | `researcher` | only when ≥2 paths |
| Implement | `implementer` | `composer-2.5` |
| Review | `code-reviewer` | `composer-2.5` |
| Verify | `skeptic-verifier` | `cursor-grok-4.5-high` |
| Gate commands | `test-runner` | in-session |
| Gate verdict | Task w/ Grok | `cursor-grok-4.5-high` |

Standing order: all gates on Grok (`gate_run_mode: in_session_grok`).

## Resume note (2026-07-31)

Implementation packets P0–P6 landed in working tree before workflow dir existed.
Series E–H sweeps were interrupted by Windows SQLite file locks; stale processes killed,
`_reset_calibration_db()` updated to fall back to in-place table clear.
