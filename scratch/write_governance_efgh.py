#!/usr/bin/env python3
"""Generate Series E-H governance markdown from scratch/series_*_metrics.json."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
SCRATCH = REPO / "scratch"


def _load(series: str) -> dict:
    path = SCRATCH / f"series_{series.lower()}_metrics.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_series_e() -> None:
    payload = _load("e")
    m = payload["metrics"]
    b = m.get("blocked_entity_point_fp_delta", {})
    d_path = DOCS / "calibration_series_d_metrics.json"
    d_blocked = d_active = "N/A"
    if d_path.exists():
        dm = json.loads(d_path.read_text(encoding="utf-8")).get("metrics", {})
        d_blocked = dm.get("blocked_entity_count", "N/A")
        d_active = dm.get("active_alert_workflow_rows", "N/A")
    text = f"""# Scoring-config governance — Series E (2026-07-30)

**Plan:** `docs/superpowers/plans/2026-07-30-drift-detection-capability-expansion.md` (Phase 0)  
**Status:** Series E baseline established. **Not CALIBRATED.** Detection knobs **unchanged** (`enabled` flags none for Phase 0).

## What this sweep covers

| Item | Value |
|---|---|
| Seed | {payload.get('generator_seed', 42)} |
| Config | v{payload.get('config_version', '2.2')} @ `anomaly_threshold={payload.get('anomaly_threshold', 45)}` |
| Semantics | Same event mix as Series D + Phase 0 shadow-aware point-rarity/embedding baseline |
| Artifact | `scratch/series_e_metrics.json` |
| Harness | `scratch/run_series_e_sweep.py` |
| Knobs changed | **false** |

## Headline (Series E only — do not compare FP/P/R to A/B/C/D)

| Metric @ thr=45 | Value |
|---|---|
| P / R / F1 | {m.get('precision', 0):.4f} / {m.get('recall', 0):.4f} / {m.get('f1', 0):.4f} |
| TP / FP / FN | {m.get('tp')} / {m.get('fp')} / {m.get('fn')} |
| active_alert_workflow_rows | {m.get('active_alert_workflow_rows')} |
| blocked_entity_count | {m.get('blocked_entity_count')} |

## Phase 0 isolated effect

| Metric | Series D (archival) | Series E |
|---|---:|---:|
| blocked_entity_count | {d_blocked} | {b.get('blocked_entity_count', m.get('blocked_entity_count'))} |
| active_alert_workflow_rows | {d_active} | {m.get('active_alert_workflow_rows')} |
| point_baseline_shadow_engaged_count | 0 (pre-Phase-0) | {b.get('point_baseline_shadow_engaged_count', 0)} |
| blocked_entity_anomaly_count | — | {b.get('blocked_entity_anomaly_count', 'N/A')} |

Phase 0 has no config `enabled` gate — this doc confirms the fix does not shift blocked-entity FP volume unexpectedly before Phase 1+ lands.

## Cross-series rule

Do **not** compare headline FP/P/R to Series A/B/C/D. Series E isolates Phase 0 point-baseline behavior only.

## Standing rule

No production scoring change without recorded sweep + governance sign-off (S6.3).
"""
    (DOCS / "scoring-config-governance-series-e.md").write_text(text, encoding="utf-8")


def write_series_f() -> None:
    payload = _load("f")
    m = payload["metrics"]
    decomp = m.get("per_dimension_drift_decomposition", {})
    emb = decomp.get("embedding", {})
    cad = decomp.get("cadence", {})
    vol = decomp.get("total_volume_delta", {})
    emb_mean = emb.get("mean") or 0.0
    cad_mean = cad.get("mean") or 0.0
    ratio = (cad_mean / emb_mean) if emb_mean else None
    text = f"""# Scoring-config governance — Series F (2026-07-30)

**Plan:** Phases 1–2 (cadence + volume delta)  
**Status:** **Not CALIBRATED.** Sweep ran with `enabled: true` **only inside the harness**; committed YAML remains `enabled: false`.

## Headline @ thr=45

| Metric | Value |
|---|---|
| P / R / F1 | {m.get('precision', 0):.4f} / {m.get('recall', 0):.4f} / {m.get('f1', 0):.4f} |
| TP / FP / FN | {m.get('tp')} / {m.get('fp')} / {m.get('fn')} |

## Cadence dimension dominance check (H4)

| Dimension | mean delta_last_build | max | n |
|---|---:|---:|---:|
| embedding | {emb.get('mean')} | {emb.get('max')} | {emb.get('n')} |
| cadence | {cad.get('mean')} | {cad.get('max')} | {cad.get('n')} |
| total_volume_delta | {vol.get('mean')} | {vol.get('max')} | {vol.get('n')} |

Cadence/embedding mean ratio: {ratio if ratio is not None else 'N/A'}.

This sweep **reports evidence only** — it does **not** authorize flipping `enabled: true` in committed YAML.

## Cross-series rule

Compare decomposition against Series E predecessor, not Series D headline FP/P/R.
"""
    (DOCS / "scoring-config-governance-series-f.md").write_text(text, encoding="utf-8")


def write_series_g() -> None:
    payload = _load("g")
    m = payload["metrics"]
    s3 = m.get("scenarios", {}).get("scenario_3_subtle", {})
    s1 = m.get("scenarios", {}).get("scenario_1_sharp_misuse", {})
    text = f"""# Scoring-config governance — Series G (2026-07-30)

**Plan:** Phases 3–4 (fleet cohort drift + geo-velocity)  
**Status:** **Not CALIBRATED.** Harness-only `fleet_drift_enabled` + `geo_velocity.enabled`.

## S3 recall with fleet cohort drift enabled

| Metric | Value |
|---|---|
| scenario_3_subtle recall | {s3.get('recall', 'N/A')} |
| scenario_3 tp / fn | {s3.get('tp')} / {s3.get('fn')} |

Series D archival S3 recall was **0.444** — cross-series comparison is **informational only** per repo discipline; topology changed with new dimensions.

## S1 recall (geo-velocity check)

| scenario_1_sharp_misuse recall | {s1.get('recall', 'N/A')} |

## Headline @ thr=45

P/R: {m.get('precision', 0):.4f} / {m.get('recall', 0):.4f}; FP={m.get('fp')}; TP={m.get('tp')}.

Evidence report only — no committed YAML flip authorized.
"""
    (DOCS / "scoring-config-governance-series-g.md").write_text(text, encoding="utf-8")


def write_series_h() -> None:
    payload = _load("h")
    m = payload["metrics"]
    dist = m.get("signal_family_agreement_distribution", {})
    benign = dist.get("benign_fp_agreement_distribution", {})
    tp = dist.get("tp_agreement_distribution", {})
    s3 = m.get("scenarios", {}).get("scenario_3_subtle", {})
    text = f"""# Scoring-config governance — Series H (2026-07-30)

**Plan:** Phases 5–6 (precision gate Stage A + staged sequences)  
**Status:** **Not CALIBRATED.**

## Benign vs. TP signal-family agreement (Stage-B evidence base)

| Cohort | n | mean | histogram |
|---|---:|---:|---|
| benign FP | {benign.get('n', 0)} | {benign.get('mean', 'N/A')} | {benign.get('histogram', {})} |
| TP | {tp.get('n', 0)} | {tp.get('mean', 'N/A')} | {tp.get('histogram', {})} |

*This distribution is the evidence base for any future Stage-B threshold proposal. No proposal may cite a number not derived from this table.*

## Phase 6 staged-sequence recall impact

| scenario_3_subtle recall | {s3.get('recall', 'N/A')} |

Harness-only `precision_gate.enabled` + `staged_drift.enabled`; committed YAML remains false.
"""
    (DOCS / "scoring-config-governance-series-h.md").write_text(text, encoding="utf-8")


def main() -> int:
    write_series_e()
    write_series_f()
    write_series_g()
    write_series_h()
    print("Wrote docs/scoring-config-governance-series-{e,f,g,h}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
