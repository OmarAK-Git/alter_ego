"""One-shot Series C S2 diagnosis against alter_ego_calibrate_series_c.db."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from core.attestation import ANCHOR_HISTORY_COUNT, novel_mass

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "alter_ego_calibrate_series_c.db"
OUT_JSON = ROOT / "scratch" / "series_c_s2_diagnosis.json"
THR = 45.0
SCENARIO = "scenario_2_slow_roll"


def _parse_ts(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s[:26], fmt)
            except ValueError:
                continue
    return None


def _loads(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    return json.loads(v)


def _contrib_map(contributions: Any) -> dict[str, float]:
    raw = _loads(contributions) or []
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                out[str(k)] = float(v.get("contribution_score", v.get("score", 0.0)))
            else:
                out[str(k)] = float(v)
        return out
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("feature_name") or item.get("name") or item.get("contribution_id")
            if name is None:
                continue
            out[str(name)] = float(item.get("contribution_score", item.get("score", 0.0)))
    return out


def classify_trajectory(points: list[dict[str, Any]], thr: float = 5.0) -> str:
    """Qualitative label for cumulative_drift over profile history."""
    if not points:
        return "no_profiles"
    drifts = [float(p["cumulative_drift"]) for p in points]
    promoted = [p for p in points if not p.get("is_shadow") and p.get("promoted_at")]
    promo_drifts = [float(p["cumulative_drift"]) for p in promoted]
    max_d = max(drifts) if drifts else 0.0
    # resets: promoted rows with low drift after high shadow drift, or sequence dips after promos
    resets = 0
    for i in range(1, len(points)):
        prev, cur = drifts[i - 1], drifts[i]
        if prev >= thr * 0.5 and cur < prev * 0.35 and points[i].get("promoted_at"):
            resets += 1
        if (
            points[i].get("promoted_at")
            and not points[i].get("is_shadow")
            and prev > cur + 1.0
        ):
            resets += 1
    # also count promoted cumulative near-zero while shadows rose high
    shadow_max = max((float(p["cumulative_drift"]) for p in points if p.get("is_shadow")), default=0.0)
    promo_max = max(promo_drifts, default=0.0)
    if resets >= 2 or (shadow_max >= thr and promo_max < thr * 0.5 and len(promoted) >= 2):
        return "flat-with-resets"
    if max_d >= thr:
        return "rising and would cross"
    if max_d > 0.5 and any(d > drifts[0] + 0.25 for d in drifts):
        return "rising but sub threshold for score"
    if max_d < 0.5:
        return "flat-with-resets" if resets else "flat"
    return "rising but sub threshold for score"


def main() -> int:
    if not DB_PATH.is_file():
        print(f"FAIL: database missing: {DB_PATH}", file=sys.stderr)
        return 2

    os.environ.setdefault("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")

    report: dict[str, Any] = {
        "database": str(DB_PATH),
        "anomaly_threshold": THR,
        "quiet_window_days": 3,
        "min_dwell_builds": 2,
        "anchor_history_count": ANCHOR_HISTORY_COUNT,
    }

    with engine.connect() as conn:
        # --- Identities / attack window ---
        s2 = list(
            conn.execute(
                text(
                    """
                    SELECT e.event_id, e.raw_entity_id, e.timestamp, gt.is_malicious
                    FROM eval_ground_truth gt
                    JOIN events e ON e.event_id = gt.event_id
                    WHERE gt.scenario = :sc
                    ORDER BY e.timestamp
                    """
                ),
                {"sc": SCENARIO},
            ).mappings()
        )
        if not s2:
            print("FAIL: no scenario_2_slow_roll ground-truth events", file=sys.stderr)
            return 2

        raw_ids = sorted({r["raw_entity_id"] for r in s2})
        # resolve via resolved_events if present
        resolved = list(
            conn.execute(
                text(
                    """
                    SELECT DISTINCT re.entity_id, e.raw_entity_id
                    FROM eval_ground_truth gt
                    JOIN events e ON e.event_id = gt.event_id
                    LEFT JOIN resolved_events re ON re.event_id = e.event_id
                    WHERE gt.scenario = :sc
                    """
                ),
                {"sc": SCENARIO},
            ).mappings()
        )
        entity_ids = sorted(
            {
                (r["entity_id"] or r["raw_entity_id"])
                for r in resolved
                if (r["entity_id"] or r["raw_entity_id"])
            }
        )
        victim = entity_ids[0] if len(entity_ids) == 1 else (
            entity_ids[0] if entity_ids else raw_ids[0]
        )
        ts_list = [_parse_ts(r["timestamp"]) for r in s2]
        ts_list = [t for t in ts_list if t is not None]
        attack_min, attack_max = min(ts_list), max(ts_list)
        report["identities"] = {
            "scenario": SCENARIO,
            "raw_entity_ids": raw_ids,
            "entity_ids": entity_ids,
            "s2_victim": victim,
            "malicious_event_count": len(s2),
            "attack_window": {
                "min": attack_min.isoformat(),
                "max": attack_max.isoformat(),
                "span_days": round((attack_max - attack_min).total_seconds() / 86400.0, 3),
            },
        }

        # --- A) cumulative_drift trajectory ---
        profiles = list(
            conn.execute(
                text(
                    """
                    SELECT profile_version, entity_id, created_at, data_window_start,
                           data_window_end, promoted_at, superseded_at, is_shadow, features
                    FROM profiles
                    WHERE entity_id = :eid
                    ORDER BY COALESCE(data_window_end, created_at), created_at
                    """
                ),
                {"eid": victim},
            ).mappings()
        )
        traj: list[dict[str, Any]] = []
        for p in profiles:
            feat = _loads(p["features"]) or {}
            drift = float(feat.get("cumulative_drift") or 0.0)
            is_shadow = bool(p["is_shadow"])
            superseded = p["superseded_at"]
            promoted_at = p["promoted_at"]
            scorer_visible = (not is_shadow) and (promoted_at is not None) and (superseded is None)
            # as-of visibility note for superseded promoted
            was_promoted = (not is_shadow) and (promoted_at is not None)
            traj.append(
                {
                    "profile_version": p["profile_version"],
                    "timestamp": str(p["data_window_end"] or p["created_at"]),
                    "created_at": str(p["created_at"]),
                    "data_window_end": str(p["data_window_end"]) if p["data_window_end"] else None,
                    "is_shadow": is_shadow,
                    "promoted_at": str(promoted_at) if promoted_at else None,
                    "superseded_at": str(superseded) if superseded else None,
                    "cumulative_drift": drift,
                    "normalized_drift": float(feat.get("normalized_drift") or 0.0),
                    "scorer_visible_current": scorer_visible,
                    "was_promoted_non_shadow": was_promoted,
                    "visibility": (
                        "scorer-visible-current"
                        if scorer_visible
                        else (
                            "promoted-then-superseded"
                            if was_promoted and superseded
                            else ("shadow" if is_shadow else "other")
                        )
                    ),
                }
            )
        traj_class = classify_trajectory(traj)
        max_drift = max((t["cumulative_drift"] for t in traj), default=0.0)
        max_promoted_drift = max(
            (t["cumulative_drift"] for t in traj if t["was_promoted_non_shadow"]),
            default=0.0,
        )
        max_shadow_drift = max(
            (t["cumulative_drift"] for t in traj if t["is_shadow"]),
            default=0.0,
        )
        # Dual reading: shadows may rise-and-cross while scorer-visible promos stay flat
        dual = traj_class
        if max_shadow_drift >= 5.0 and max_promoted_drift < 2.5:
            dual = (
                "flat-with-resets (scorer-visible promoted); "
                "rising and would cross (shadow-only)"
            )
        report["A_trajectory"] = {
            "entity_id": victim,
            "n_profiles": len(traj),
            "n_shadow": sum(1 for t in traj if t["is_shadow"]),
            "n_promoted_non_shadow": sum(1 for t in traj if t["was_promoted_non_shadow"]),
            "max_cumulative_drift_all": max_drift,
            "max_cumulative_drift_shadow": max_shadow_drift,
            "max_cumulative_drift_promoted": max_promoted_drift,
            "classification": dual,
            "classification_raw": traj_class,
            "time_series": traj,
            "notes": (
                "Shadow can accumulate high drift while promoted profiles stay low after "
                "promotion resets (tempo laundering)."
                if traj_class == "flat-with-resets"
                else None
            ),
        }

        # --- B) Auto-resolution ---
        auto_rows = conn.execute(
            text("SELECT COUNT(*) FROM alert_workflow_state WHERE state='auto_resolved'")
        ).scalar()
        state_hist = {
            r[0]: r[1]
            for r in conn.execute(
                text("SELECT state, COUNT(*) FROM alert_workflow_state GROUP BY state")
            )
        }
        audit_auto = conn.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE action='alert_auto_resolved'")
        ).scalar()

        # per-entity workflow auto_resolved counts
        per_ent_wf = list(
            conn.execute(
                text(
                    """
                    SELECT entity_id, COUNT(*) AS n
                    FROM alert_workflow_state
                    WHERE state='auto_resolved'
                    GROUP BY entity_id
                    ORDER BY n DESC
                    """
                )
            )
        )
        wf_counts = [n for _, n in per_ent_wf]
        hist_bins: Counter[str] = Counter()
        for n in wf_counts:
            if n == 1:
                hist_bins["1"] += 1
            elif n <= 5:
                hist_bins["2-5"] += 1
            elif n <= 10:
                hist_bins["6-10"] += 1
            elif n <= 20:
                hist_bins["11-20"] += 1
            elif n <= 50:
                hist_bins["21-50"] += 1
            else:
                hist_bins["51+"] += 1

        # audit per entity (episodes)
        audit_rows = list(
            conn.execute(
                text(
                    """
                    SELECT entity_id, timestamp, details
                    FROM audit_logs
                    WHERE action='alert_auto_resolved'
                    ORDER BY timestamp
                    """
                )
            ).mappings()
        )
        audit_by_ent: dict[str, list[datetime]] = defaultdict(list)
        for r in audit_rows:
            t = _parse_ts(r["timestamp"])
            if t and r["entity_id"]:
                audit_by_ent[str(r["entity_id"])].append(t)

        # also day-grouped episodes from workflow updated_at
        wf_auto = list(
            conn.execute(
                text(
                    """
                    SELECT entity_id, updated_at, decision_id
                    FROM alert_workflow_state
                    WHERE state='auto_resolved'
                    ORDER BY entity_id, updated_at
                    """
                )
            ).mappings()
        )
        wf_days_by_ent: dict[str, set[str]] = defaultdict(set)
        wf_ts_by_ent: dict[str, list[datetime]] = defaultdict(list)
        for r in wf_auto:
            eid = str(r["entity_id"])
            t = _parse_ts(r["updated_at"])
            if t:
                wf_days_by_ent[eid].add(t.date().isoformat())
                wf_ts_by_ent[eid].append(t)

        episode_counts_audit = [len(v) for v in audit_by_ent.values()]
        # collapse audit timestamps within same calendar day as one episode? user asked both
        episode_days_audit = {
            eid: len({t.date().isoformat() for t in ts}) for eid, ts in audit_by_ent.items()
        }

        # S2 specific
        s2_wf_auto = [r for r in wf_auto if r["entity_id"] == victim]
        s2_audit_ts = audit_by_ent.get(victim, [])
        s2_days = sorted(wf_days_by_ent.get(victim, set()))
        s2_intervals: list[float] = []
        if len(s2_audit_ts) >= 2:
            ordered = sorted(s2_audit_ts)
            for a, b in zip(ordered, ordered[1:]):
                s2_intervals.append(round((b - a).total_seconds() / 86400.0, 4))
        # day-level intervals
        s2_day_intervals: list[float] = []
        if len(s2_days) >= 2:
            days_dt = [datetime.fromisoformat(d) for d in s2_days]
            for a, b in zip(days_dt, days_dt[1:]):
                s2_day_intervals.append(round((b - a).total_seconds() / 86400.0, 4))

        s2_opened = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM decisions
                WHERE entity_id = :eid AND is_anomaly = 1
                """
            ),
            {"eid": victim},
        ).scalar()

        # sweep window approx from decisions
        sweep_bounds = conn.execute(
            text("SELECT MIN(timestamp), MAX(timestamp) FROM decisions")
        ).fetchone()
        sweep_min, sweep_max = _parse_ts(sweep_bounds[0]), _parse_ts(sweep_bounds[1])
        sweep_days = (
            (sweep_max - sweep_min).total_seconds() / 86400.0
            if sweep_min and sweep_max
            else None
        )

        s2_episodes_audit = len(s2_audit_ts)
        s2_episodes_day = len(s2_days)
        strain = False
        strain_note = None
        # Prefer day-grouped episodes for quiet+dwell binding; raw audit/WF rows
        # are decision-level (batch auto-resolve), not cycle counts.
        # quiet=3d + dwell=2 → expected ~5-7 cycles over ~21 days
        if s2_episodes_audit > 7 and s2_episodes_day <= 7:
            strain_note = (
                "counting confusion: "
                f"{s2_episodes_audit} workflow/audit auto_resolved rows vs "
                f"{s2_episodes_day} distinct day-episodes; "
                "row count is not entity cycle count"
            )
            # not predicate-failure if day episodes are in-band
            strain = False
        elif s2_episodes_day > 7:
            strain = True
            strain_note = (
                "predicate not binding or counting confusion "
                f"(entity-level day-episodes={s2_episodes_day}; "
                "quiet=3d+dwell=2 implies ~5–7 over ~21d)"
            )

        report["B_auto_resolution"] = {
            "count_auto_resolved_workflow_rows": int(auto_rows),
            "workflow_state_histogram": state_hist,
            "audit_alert_auto_resolved_rows": int(audit_auto),
            "1817_matches_workflow_auto_resolved": int(auto_rows) == 1817,
            "1817_matches_audit": int(audit_auto) == 1817,
            "fleet": {
                "entities_with_auto_resolved_rows": len(per_ent_wf),
                "mean_auto_resolved_rows_per_entity": (
                    round(sum(wf_counts) / len(wf_counts), 3) if wf_counts else 0.0
                ),
                "histogram_rows_per_entity": dict(hist_bins),
                "top_entities_by_rows": [{"entity_id": e, "rows": n} for e, n in per_ent_wf[:15]],
                "entities_with_audit_auto_resolved": len(audit_by_ent),
                "mean_audit_episodes_per_entity": (
                    round(sum(episode_counts_audit) / len(episode_counts_audit), 3)
                    if episode_counts_audit
                    else 0.0
                ),
                "mean_audit_day_episodes_per_entity": (
                    round(sum(episode_days_audit.values()) / len(episode_days_audit), 3)
                    if episode_days_audit
                    else 0.0
                ),
            },
            "s2_victim": {
                "entity_id": victim,
                "workflow_rows_auto_resolved": len(s2_wf_auto),
                "audit_auto_resolved_count": s2_episodes_audit,
                "distinct_auto_resolve_days": s2_episodes_day,
                "auto_resolve_days": s2_days,
                "inter_resolution_intervals_days_audit": s2_intervals,
                "inter_resolution_intervals_days_by_day": s2_day_intervals,
                "decisions_opened_is_anomaly": int(s2_opened),
            },
            "sweep_window": {
                "min": sweep_min.isoformat() if sweep_min else None,
                "max": sweep_max.isoformat() if sweep_max else None,
                "span_days": round(sweep_days, 3) if sweep_days is not None else None,
            },
            "quiet_dwell_strain": strain,
            "quiet_dwell_flag": strain_note,
        }

        # --- C) FP decomposition at thr=45 ---
        # malicious event ids
        mal_ids = {
            r[0]
            for r in conn.execute(
                text("SELECT event_id FROM eval_ground_truth WHERE is_malicious = 1")
            )
        }
        # Also consider scenario labels: FP = score>=45 or is_anomaly, event not malicious
        decisions = list(
            conn.execute(
                text(
                    """
                    SELECT decision_id, event_id, entity_id, score, is_anomaly, contributions
                    FROM decisions
                    WHERE score >= :thr OR is_anomaly = 1
                    """
                ),
                {"thr": THR},
            ).mappings()
        )
        fp_rows = [d for d in decisions if d["event_id"] not in mal_ids]
        n_fp = len(fp_rows)
        drift_primary = 0
        point_only = 0  # drift contrib == 0
        hybrid = 0
        other = 0
        examples: dict[str, list[dict[str, Any]]] = {
            "drift_primary": [],
            "point_only": [],
            "hybrid": [],
        }

        for d in fp_rows:
            cmap = _contrib_map(d["contributions"])
            drift_c = float(cmap.get("drift_alert", 0.0))
            others = {k: v for k, v in cmap.items() if k != "drift_alert"}
            max_other = max(others.values()) if others else 0.0
            point_sum = sum(others.values())
            alone_crosses = drift_c >= THR
            is_largest = drift_c > 0 and drift_c >= max_other - 1e-9
            if drift_c == 0.0 or abs(drift_c) < 1e-12:
                bucket = "point_only"
                point_only += 1
            elif alone_crosses or (is_largest and drift_c >= max_other):
                # drift primary: largest contrib OR alone would cross
                # but if other also large, could be hybrid — use:
                # primary if drift is strictly largest OR alone crosses AND point_sum < thr
                if alone_crosses and point_sum < THR:
                    bucket = "drift_primary"
                    drift_primary += 1
                elif is_largest and point_sum < THR:
                    bucket = "drift_primary"
                    drift_primary += 1
                elif drift_c > 0 and point_sum > 0 and (alone_crosses or point_sum >= THR or drift_c >= THR * 0.5):
                    bucket = "hybrid"
                    hybrid += 1
                elif is_largest:
                    bucket = "drift_primary"
                    drift_primary += 1
                else:
                    bucket = "hybrid"
                    hybrid += 1
            elif drift_c > 0 and point_sum > 0:
                bucket = "hybrid"
                hybrid += 1
            else:
                other += 1
                bucket = "other"

            if len(examples.get(bucket, [])) < 3 and bucket in examples:
                examples[bucket].append(
                    {
                        "decision_id": d["decision_id"],
                        "entity_id": d["entity_id"],
                        "score": d["score"],
                        "drift_alert": drift_c,
                        "max_other": max_other,
                        "point_sum": point_sum,
                    }
                )

        def pct(x: int) -> float:
            return round(100.0 * x / n_fp, 2) if n_fp else 0.0

        report["C_fp_decomposition"] = {
            "threshold": THR,
            "fp_count": n_fp,
            "anomaly_or_ge_thr_total": len(decisions),
            "malicious_gt_events": len(mal_ids),
            "drift_primary": {"count": drift_primary, "pct": pct(drift_primary)},
            "point_only_drift_zero": {"count": point_only, "pct": pct(point_only)},
            "hybrid": {"count": hybrid, "pct": pct(hybrid)},
            "other": {"count": other, "pct": pct(other)},
            "examples": examples,
            "definition": {
                "point_only": "drift_alert contribution_score == 0",
                "drift_primary": (
                    "drift_alert alone >= thr with point_sum < thr, or drift largest "
                    "with point_sum < thr"
                ),
                "hybrid": "both drift_alert > 0 and other contributions > 0 without pure primary",
            },
        }

        # --- D) M_novel at each S2 promotion ---
        promoted = [
            p
            for p in profiles
            if (not bool(p["is_shadow"])) and p["promoted_at"] is not None
        ]
        # chrono already from query order; re-sort by promoted_at / window
        def _pkey(p: Any) -> datetime:
            return _parse_ts(p["promoted_at"]) or _parse_ts(p["data_window_end"]) or _parse_ts(p["created_at"]) or datetime.min

        promoted = sorted(promoted, key=_pkey)
        novel_rows: list[dict[str, Any]] = []
        near_zero_during_attack = []
        for i, p in enumerate(promoted):
            feat = _loads(p["features"]) or {}
            # P0 = immediately prior promoted
            m_p0 = None
            if i > 0:
                prior = _loads(promoted[i - 1]["features"]) or {}
                m_p0 = novel_mass(feat, prior)
            # anchor = ANCHOR_HISTORY_COUNT promotions back
            anchor_idx = max(0, i - ANCHOR_HISTORY_COUNT)
            anchor_feat = _loads(promoted[anchor_idx]["features"]) or {}
            m_anchor = novel_mass(feat, anchor_feat) if i > 0 else 0.0
            # vs earliest available when fewer than ANCHOR
            earliest = _loads(promoted[0]["features"]) or {}
            m_earliest = novel_mass(feat, earliest) if i > 0 else 0.0
            t_prom = _parse_ts(p["promoted_at"])
            in_or_after_attack = False
            if t_prom:
                # during attack ladder or shortly after (through attack_max + 7d)
                from datetime import timedelta

                in_or_after_attack = attack_min <= t_prom <= (attack_max + timedelta(days=7))
            row = {
                "profile_version": p["profile_version"],
                "promoted_at": str(p["promoted_at"]),
                "data_window_end": str(p["data_window_end"]) if p["data_window_end"] else None,
                "cumulative_drift": float(feat.get("cumulative_drift") or 0.0),
                "index": i,
                "anchor_index": anchor_idx,
                "M_novel_vs_anchor": m_anchor,
                "M_novel_vs_P0": m_p0,
                "M_novel_vs_earliest": m_earliest,
                "in_or_after_attack_window": in_or_after_attack,
                "near_zero": (m_anchor is not None and m_anchor < 0.02)
                and (m_p0 is None or m_p0 < 0.02),
            }
            novel_rows.append(row)
            if in_or_after_attack and row["near_zero"]:
                near_zero_during_attack.append(row["profile_version"])

        report["D_m_novel"] = {
            "entity_id": victim,
            "n_promoted": len(promoted),
            "anchor_history_count": ANCHOR_HISTORY_COUNT,
            "promotions": novel_rows,
            "near_zero_during_or_after_attack": near_zero_during_attack,
            "pre_seeding_concern": bool(near_zero_during_attack)
            or (
                len(novel_rows) >= 2
                and all(
                    (r["M_novel_vs_P0"] or 0) < 0.02
                    for r in novel_rows
                    if r["in_or_after_attack_window"] and r["M_novel_vs_P0"] is not None
                )
                and any(r["in_or_after_attack_window"] for r in novel_rows)
            ),
        }

        # --- Verdict ---
        verdict = {
            "trajectories": dual,
            "trajectory_detail": (
                f"max_shadow_drift={max_shadow_drift:.3f} "
                f"max_promoted_drift={max_promoted_drift:.3f} "
                f"n_promoted={sum(1 for t in traj if t['was_promoted_non_shadow'])} "
                f"n_shadow={sum(1 for t in traj if t['is_shadow'])}"
            ),
            "auto_resolved_1817_is_rows": int(auto_rows) == 1817,
            "auto_resolved_row_count": int(auto_rows),
            "s2_entity_cycle_count_days": s2_episodes_day,
            "s2_entity_audit_episodes": s2_episodes_audit,
            "s2_workflow_auto_resolved_rows": len(s2_wf_auto),
            "strains_quiet_dwell": strain,
            "quiet_dwell_flag": strain_note,
            "fp_point_only_pct": pct(point_only),
            "fp_drift_primary_pct": pct(drift_primary),
            "fp_hybrid_pct": pct(hybrid),
            "m_novel_near_zero_at_s2_promotions": (
                report["D_m_novel"]["pre_seeding_concern"]
                or (
                    len(novel_rows) > 1
                    and all((r["M_novel_vs_P0"] or 0) < 0.05 for r in novel_rows[1:])
                )
            ),
            "m_novel_summary": [
                {
                    "promoted_at": r["promoted_at"],
                    "M_novel_vs_P0": r["M_novel_vs_P0"],
                    "M_novel_vs_anchor": r["M_novel_vs_anchor"],
                }
                for r in novel_rows
            ],
        }
        report["verdict"] = verdict

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Human summary
    print("=" * 72)
    print("SERIES C S2 DIAGNOSIS")
    print("=" * 72)
    print(f"DB: {DB_PATH}")
    print(f"Wrote: {OUT_JSON}")
    print()
    print("--- Identities ---")
    print(json.dumps(report["identities"], indent=2))
    print()
    print("--- A) Trajectory ---")
    a = report["A_trajectory"]
    print(f"classification: {a['classification']}")
    print(
        f"profiles={a['n_profiles']} shadow={a['n_shadow']} "
        f"promoted={a['n_promoted_non_shadow']} "
        f"max_drift(all/shadow/promoted)="
        f"{a['max_cumulative_drift_all']:.3f}/"
        f"{a['max_cumulative_drift_shadow']:.3f}/"
        f"{a['max_cumulative_drift_promoted']:.3f}"
    )
    print("time_series (compact):")
    for t in a["time_series"]:
        print(
            f"  {t['timestamp'][:19]} shadow={t['is_shadow']} "
            f"drift={t['cumulative_drift']:.4f} "
            f"prom={t['promoted_at']} sup={t['superseded_at']} "
            f"vis={t['visibility']}"
        )
    print()
    print("--- B) Auto-resolution ---")
    b = report["B_auto_resolution"]
    print(
        f"workflow auto_resolved rows={b['count_auto_resolved_workflow_rows']} "
        f"(1817 match={b['1817_matches_workflow_auto_resolved']})"
    )
    print(f"audit alert_auto_resolved={b['audit_alert_auto_resolved_rows']}")
    print(f"fleet: {json.dumps(b['fleet'], indent=2)}")
    print(f"S2: {json.dumps(b['s2_victim'], indent=2)}")
    print(f"strain flag: {b['quiet_dwell_flag']}")
    print()
    print("--- C) FP decomposition thr=45 ---")
    c = report["C_fp_decomposition"]
    print(
        f"FP={c['fp_count']} "
        f"point_only={c['point_only_drift_zero']['pct']}% "
        f"drift_primary={c['drift_primary']['pct']}% "
        f"hybrid={c['hybrid']['pct']}%"
    )
    print()
    print("--- D) M_novel ---")
    print(json.dumps(report["D_m_novel"]["promotions"], indent=2))
    print(f"pre_seeding_concern={report['D_m_novel']['pre_seeding_concern']}")
    print()
    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    v = report["verdict"]
    print(f"Trajectories: {v['trajectories']} ({v['trajectory_detail']})")
    print(
        f"Is 1817 rows? {v['auto_resolved_1817_is_rows']} "
        f"(count={v['auto_resolved_row_count']})"
    )
    print(
        f"S2 cycles: workflow_rows={v['s2_workflow_auto_resolved_rows']} "
        f"audit_episodes={v['s2_entity_audit_episodes']} "
        f"distinct_days={v['s2_entity_cycle_count_days']} "
        f"strains_quiet+dwell={v['strains_quiet_dwell']}"
    )
    if v["quiet_dwell_flag"]:
        print(f"  FLAG: {v['quiet_dwell_flag']}")
    print(
        f"FP: point-only={v['fp_point_only_pct']}% "
        f"drift-primary={v['fp_drift_primary_pct']}% "
        f"hybrid={v['fp_hybrid_pct']}%"
    )
    print(f"M_novel near zero at S2 promotions? {v['m_novel_near_zero_at_s2_promotions']}")
    for m in v["m_novel_summary"]:
        print(f"  {m}")
    print("=" * 72)
    # also dump full JSON path reminder
    print(json.dumps({"ok": True, "out": str(OUT_JSON), "verdict": v}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
