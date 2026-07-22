"""Diagnose Series C D4 engagement (drift_source_profile_version flags)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "alter_ego_calibrate_series_c.db"
OUT_JSON = ROOT / "scratch" / "series_c_d4_engagement.json"
SCENARIO = "scenario_2_slow_roll"
ACTIVE_STATES = ("new", "acknowledged", "investigating")
D4_PREFIX = "drift_source_profile_version"


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


def flags_have_d4(flags: Any) -> bool:
    raw = _loads(flags)
    if raw is None:
        return False
    if isinstance(raw, list):
        return any(isinstance(x, str) and x.startswith(D4_PREFIX) for x in raw)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if D4_PREFIX in str(k):
                return True
            if isinstance(v, str) and v.startswith(D4_PREFIX):
                return True
            if isinstance(v, list) and any(
                isinstance(x, str) and x.startswith(D4_PREFIX) for x in v
            ):
                return True
    return False


def extract_d4_flags(flags: Any) -> list[str]:
    raw = _loads(flags)
    out: list[str] = []
    if isinstance(raw, list):
        out = [x for x in raw if isinstance(x, str) and x.startswith(D4_PREFIX)]
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if D4_PREFIX in str(k):
                out.append(f"{k}={v}")
            if isinstance(v, str) and v.startswith(D4_PREFIX):
                out.append(v)
    return out


def drift_contrib(contributions: Any) -> dict[str, float | None]:
    raw = _loads(contributions) or []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("feature_name") or item.get("name")
            if name == "drift_alert":
                return {
                    "raw_value": float(item.get("raw_value", 0.0)),
                    "contribution_score": float(
                        item.get("contribution_score", item.get("score", 0.0))
                    ),
                }
    if isinstance(raw, dict) and "drift_alert" in raw:
        v = raw["drift_alert"]
        if isinstance(v, dict):
            return {
                "raw_value": float(v.get("raw_value", 0.0)),
                "contribution_score": float(
                    v.get("contribution_score", v.get("score", 0.0))
                ),
            }
    return {"raw_value": None, "contribution_score": None}


def shadow_gate_condition() -> dict[str, Any]:
    return {
        "exact_condition": (
            "if entity_has_active_uncleared_alert(db, resolved_event.entity_id): "
            "shadow = ProfileStore(db).get_latest_shadow_profile("
            "entity_id, as_of=resolved_event.timestamp); "
            "if shadow is not None: use shadow.cumulative_drift; "
            "if shadow.profile_version != promoted.profile_version: "
            "flags.append(f'drift_source_profile_version:{shadow.profile_version}')"
        ),
        "entity_has_active_uncleared_alert": (
            "bool(get_active_alert_decision_ids(db, entity_id))"
        ),
        "get_active_alert_decision_ids": (
            "Query DecisionRecordModel LEFT OUTER JOIN AlertWorkflowStateModel "
            "WHERE entity_id match AND is_anomaly=True; "
            "workflow_state = state.state if state else 'new'; "
            "include decision_id when workflow_state in "
            "{'new','acknowledged','investigating'}"
        ),
        "score_event_db_from_process_unscored_events": (
            "YES — process_unscored_events passes db_session into "
            "score_event(db_session, resolved_event, profile, config). "
            "db_session is either the caller-provided Session or SessionLocal(). "
            "ProfileStore(db) inside score_event uses that same session; db is not None "
            "on the normal process_unscored_events path."
        ),
        "source_lines": (
            "worker/scorer.py ~315-338 gate; ~568-581 D4 block; ~724 score_event call"
        ),
    }


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_url = f"sqlite:///{DB_PATH.as_posix()}"
    if not DB_PATH.exists():
        print(f"FAIL: DB missing at {DB_PATH}", file=sys.stderr)
        return 2

    engine = create_engine(db_url)

    with engine.connect() as conn:
        total_decisions = conn.execute(text("SELECT COUNT(*) FROM decisions")).scalar() or 0
        anomaly_decisions = (
            conn.execute(
                text("SELECT COUNT(*) FROM decisions WHERE is_anomaly = 1")
            ).scalar()
            or 0
        )

        d4_count = 0
        d4_examples: list[dict[str, Any]] = []
        rows = conn.execute(
            text(
                "SELECT decision_id, entity_id, event_id, timestamp, score, is_anomaly, "
                "profile_version, flags FROM decisions"
            )
        ).mappings()
        for r in rows:
            if flags_have_d4(r["flags"]):
                d4_count += 1
                if len(d4_examples) < 5:
                    d4_examples.append(
                        {
                            "decision_id": r["decision_id"],
                            "entity_id": r["entity_id"],
                            "event_id": r["event_id"],
                            "score": r["score"],
                            "d4_flags": extract_d4_flags(r["flags"]),
                        }
                    )

        s2 = conn.execute(
            text(
                """
                SELECT e.event_id, e.raw_entity_id, e.timestamp, gt.is_malicious,
                       re.entity_id AS resolved_entity_id
                FROM eval_ground_truth gt
                JOIN events e ON e.event_id = gt.event_id
                LEFT JOIN resolved_events re ON re.event_id = e.event_id
                WHERE gt.scenario = :sc
                ORDER BY e.timestamp
                """
            ),
            {"sc": SCENARIO},
        ).mappings().all()

        s2_entity = None
        s2_raw = None
        attack_event_ids: list[str] = []
        attack_window: dict[str, Any] = {"start": None, "end": None}
        if s2:
            s2_raw = s2[0]["raw_entity_id"]
            entity_ids = {r["resolved_entity_id"] for r in s2 if r["resolved_entity_id"]}
            s2_entity = next(iter(entity_ids)) if len(entity_ids) == 1 else (
                sorted(entity_ids)[0] if entity_ids else None
            )
            malicious = [r for r in s2 if r["is_malicious"] in (1, True, "1")]
            if not malicious:
                malicious = list(s2)
            attack_event_ids = [r["event_id"] for r in malicious]
            ts_list = [_parse_ts(r["timestamp"]) for r in malicious]
            ts_list = [t for t in ts_list if t]
            if ts_list:
                attack_window = {
                    "start": min(ts_list).isoformat(),
                    "end": max(ts_list).isoformat(),
                }

        workflows: list[dict[str, Any]] = []
        had_active_during_attack = False
        had_active_at_all = False
        if s2_entity:
            wf_rows = conn.execute(
                text(
                    """
                    SELECT w.decision_id, w.entity_id, w.state, w.updated_at,
                           d.timestamp AS decision_timestamp, d.is_anomaly, d.score
                    FROM alert_workflow_state w
                    JOIN decisions d ON d.decision_id = w.decision_id
                    WHERE w.entity_id = :eid
                    ORDER BY d.timestamp
                    """
                ),
                {"eid": s2_entity},
            ).mappings().all()
            aw_end = _parse_ts(attack_window["end"]) if attack_window.get("end") else None
            for w in wf_rows:
                st = w["state"]
                dts = _parse_ts(w["decision_timestamp"])
                active = st in ACTIVE_STATES
                if active:
                    had_active_at_all = True
                in_window = False
                if active and dts and aw_end and dts <= aw_end:
                    in_window = True
                    had_active_during_attack = True
                elif active and aw_end is None:
                    had_active_during_attack = True
                    in_window = True
                workflows.append(
                    {
                        "decision_id": w["decision_id"],
                        "state": st,
                        "updated_at": str(w["updated_at"]),
                        "decision_timestamp": dts.isoformat() if dts else None,
                        "is_anomaly": bool(w["is_anomaly"]),
                        "score": w["score"],
                        "active": active,
                        "approx_active_in_attack_window": in_window,
                    }
                )

        attack_decisions: list[dict[str, Any]] = []
        if attack_event_ids and s2_entity:
            chunk = 400
            by_event: dict[str, dict[str, Any]] = {}
            for i in range(0, len(attack_event_ids), chunk):
                ids = attack_event_ids[i : i + chunk]
                placeholders = ", ".join(f":e{j}" for j in range(len(ids)))
                params = {f"e{j}": eid for j, eid in enumerate(ids)}
                params["ent"] = s2_entity
                decs = conn.execute(
                    text(
                        f"""
                        SELECT decision_id, event_id, entity_id, timestamp, score,
                               is_anomaly, profile_version, contributions, flags
                        FROM decisions
                        WHERE entity_id = :ent AND event_id IN ({placeholders})
                        ORDER BY timestamp
                        """
                    ),
                    params,
                ).mappings().all()
                for d in decs:
                    by_event[d["event_id"]] = dict(d)

            for eid in attack_event_ids:
                d = by_event.get(eid)
                ev_row = next((r for r in s2 if r["event_id"] == eid), None)
                ev_ts = _parse_ts(ev_row["timestamp"]) if ev_row else None
                if d is None:
                    attack_decisions.append(
                        {
                            "event_id": eid,
                            "event_timestamp": ev_ts.isoformat() if ev_ts else None,
                            "decision": None,
                            "note": "no DecisionRecord for attack event",
                        }
                    )
                    continue
                dc = drift_contrib(d["contributions"])
                d4_flags = extract_d4_flags(d["flags"])
                active_at_ts = False
                matching_wf = None
                if ev_ts:
                    prior = conn.execute(
                        text(
                            """
                            SELECT d.decision_id, d.timestamp, w.state AS wf_state
                            FROM decisions d
                            LEFT JOIN alert_workflow_state w
                              ON w.decision_id = d.decision_id
                            WHERE d.entity_id = :ent AND d.is_anomaly = 1
                              AND d.timestamp <= :ts
                            ORDER BY d.timestamp
                            """
                        ),
                        {"ent": s2_entity, "ts": ev_ts.isoformat()},
                    ).mappings().all()
                    for p in prior:
                        st = p["wf_state"] if p["wf_state"] is not None else "new"
                        if st in ACTIVE_STATES:
                            active_at_ts = True
                            matching_wf = p["decision_id"]
                            break

                attack_decisions.append(
                    {
                        "event_id": eid,
                        "decision_id": d["decision_id"],
                        "event_timestamp": (
                            ev_ts.isoformat() if ev_ts else str(d["timestamp"])
                        ),
                        "score": d["score"],
                        "is_anomaly": bool(d["is_anomaly"]),
                        "profile_version": d["profile_version"],
                        "drift_alert_raw_value": dc["raw_value"],
                        "drift_alert_contribution_score": dc["contribution_score"],
                        "has_drift_source_flag": bool(d4_flags),
                        "drift_source_flags": d4_flags,
                        "active_alert_at_event_ts": active_at_ts,
                        "active_alert_decision_id": matching_wf,
                    }
                )

        shadow_count = 0
        promoted_count = 0
        profile_rows: list[dict[str, Any]] = []
        shadow_ever = 0
        promoted_ever = 0
        min_shadow_created = None
        max_shadow_created = None
        shadows_created_le_attack_end = 0
        max_shadow_cd = None
        if s2_entity:
            aw_start = attack_window.get("start")
            aw_end = attack_window.get("end")
            # Window by sim attack dates is empty when created_at is wall-clock;
            # also report created_at vs attack_end eligibility (as_of seam).
            if aw_start and aw_end:
                prow = conn.execute(
                    text(
                        """
                        SELECT profile_version, is_shadow, promoted_at, created_at,
                               superseded_at, features
                        FROM profiles
                        WHERE entity_id = :eid
                          AND created_at >= :start
                          AND created_at <= :end
                        ORDER BY created_at
                        """
                    ),
                    {"eid": s2_entity, "start": aw_start, "end": aw_end},
                ).mappings().all()
            else:
                prow = []
            for p in prow:
                feats = _loads(p["features"]) or {}
                is_shadow = bool(p["is_shadow"])
                if is_shadow:
                    shadow_count += 1
                elif p["promoted_at"]:
                    promoted_count += 1
                profile_rows.append(
                    {
                        "profile_version": p["profile_version"],
                        "is_shadow": is_shadow,
                        "promoted_at": str(p["promoted_at"]) if p["promoted_at"] else None,
                        "created_at": str(p["created_at"]),
                        "cumulative_drift": feats.get("cumulative_drift"),
                    }
                )

            shadow_ever = (
                conn.execute(
                    text(
                        "SELECT COUNT(*) FROM profiles "
                        "WHERE entity_id = :eid AND is_shadow = 1"
                    ),
                    {"eid": s2_entity},
                ).scalar()
                or 0
            )
            promoted_ever = (
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM profiles
                        WHERE entity_id = :eid AND is_shadow = 0
                          AND promoted_at IS NOT NULL
                        """
                    ),
                    {"eid": s2_entity},
                ).scalar()
                or 0
            )
            min_shadow_created = conn.execute(
                text(
                    "SELECT MIN(created_at) FROM profiles "
                    "WHERE entity_id = :eid AND is_shadow = 1"
                ),
                {"eid": s2_entity},
            ).scalar()
            max_shadow_created = conn.execute(
                text(
                    "SELECT MAX(created_at) FROM profiles "
                    "WHERE entity_id = :eid AND is_shadow = 1"
                ),
                {"eid": s2_entity},
            ).scalar()
            if aw_end:
                shadows_created_le_attack_end = (
                    conn.execute(
                        text(
                            """
                            SELECT COUNT(*) FROM profiles
                            WHERE entity_id = :eid AND is_shadow = 1
                              AND created_at <= :end
                            """
                        ),
                        {"eid": s2_entity, "end": aw_end},
                    ).scalar()
                    or 0
                )
            # max cumulative_drift among shadows
            all_shadows = conn.execute(
                text(
                    """
                    SELECT features FROM profiles
                    WHERE entity_id = :eid AND is_shadow = 1
                    """
                ),
                {"eid": s2_entity},
            ).scalars().all()
            cds = []
            for feats_raw in all_shadows:
                feats = _loads(feats_raw) or {}
                if feats.get("cumulative_drift") is not None:
                    cds.append(float(feats["cumulative_drift"]))
            max_shadow_cd = max(cds) if cds else None

        n_attack_with_decision = sum(1 for a in attack_decisions if a.get("decision_id"))
        n_active_at_ts = sum(
            1 for a in attack_decisions if a.get("active_alert_at_event_ts")
        )
        n_d4_on_attack = sum(
            1 for a in attack_decisions if a.get("has_drift_source_flag")
        )
        promo_versions = {
            a.get("profile_version")
            for a in attack_decisions
            if a.get("profile_version")
        }
        drift_raws = [
            a.get("drift_alert_raw_value")
            for a in attack_decisions
            if a.get("drift_alert_raw_value") is not None
        ]
        max_decision_drift_raw = max(drift_raws) if drift_raws else None

        as_of_clock_skew = {
            "note": (
                "get_latest_shadow_profile filters ProfileArtifactModel.created_at <= "
                "resolved_event.timestamp (sim time). Series C profiles use wall-clock "
                "created_at from the sweep host, so as_of excludes all shadows."
            ),
            "min_shadow_created_at": str(min_shadow_created) if min_shadow_created else None,
            "max_shadow_created_at": str(max_shadow_created) if max_shadow_created else None,
            "attack_window_end": attack_window.get("end"),
            "shadows_with_created_at_le_attack_end": int(shadows_created_le_attack_end),
            "max_shadow_cumulative_drift": max_shadow_cd,
            "max_s2_attack_decision_drift_alert_raw": max_decision_drift_raw,
        }

        seams = {
            "seam1_active_alert_gate": {
                "description": (
                    "entity_has_active_uncleared_alert must be True before shadow consult"
                ),
                "had_active_workflow_during_attack_window": had_active_during_attack,
                "had_active_workflow_ever": had_active_at_all,
                "attack_events_with_active_alert_at_ts": n_active_at_ts,
                "attack_events_with_decision": n_attack_with_decision,
            },
            "seam2_shadow_profile_available": {
                "description": (
                    "get_latest_shadow_profile must return a row with created_at <= "
                    "event ts and then version != promoted"
                ),
                "shadow_profiles_in_attack_window_by_created_at": shadow_count,
                "promoted_profiles_in_attack_window_by_created_at": promoted_count,
                "shadow_profiles_ever": shadow_ever,
                "promoted_profiles_ever": promoted_ever,
                "as_of_clock_skew": as_of_clock_skew,
            },
            "seam3_version_mismatch_flag": {
                "description": (
                    "D4 flag only appended when shadow.profile_version != "
                    "promoted profile.profile_version"
                ),
                "d4_flag_count_global": d4_count,
                "d4_on_s2_attack_events": n_d4_on_attack,
                "distinct_decision_profile_versions_on_attack": sorted(
                    x for x in promo_versions if x
                ),
            },
            "db_session_path": shadow_gate_condition()[
                "score_event_db_from_process_unscored_events"
            ],
        }

        if d4_count == 0:
            if shadows_created_le_attack_end == 0 and shadow_ever > 0:
                likely = "seam2_shadow_profile_available"
                reason = (
                    f"S2 has {shadow_ever} shadow profiles (max cumulative_drift="
                    f"{max_shadow_cd}) but ALL have wall-clock created_at "
                    f"({min_shadow_created} .. {max_shadow_created}); "
                    f"as_of=sim event timestamp (<= {attack_window.get('end')}) "
                    f"matches 0 shadows, so get_latest_shadow_profile returns None "
                    f"and D4 never appends. Attack decisions keep "
                    f"drift_alert_raw_value=0 (promoted). "
                    f"Seam1 is less likely: {n_active_at_ts}/{n_attack_with_decision} "
                    f"attack events had an active uncleared alert at event ts."
                )
            elif n_active_at_ts == 0 and not had_active_during_attack:
                likely = "seam1_active_alert_gate"
                reason = (
                    "No active AlertWorkflowState for S2 entity at attack event times, "
                    "so the D4 shadow consult never entered."
                )
            elif shadow_ever == 0:
                likely = "seam2_shadow_profile_available"
                reason = (
                    "Active-alert gate may open but no shadow profiles exist for the "
                    "S2 entity."
                )
            else:
                likely = "seam3_version_mismatch_flag"
                reason = (
                    "Alert gate and as_of-eligible shadows present, but shadow version "
                    "matched promoted or consult did not emit the flag."
                )
        else:
            likely = None
            reason = f"D4 fired {d4_count} times globally."

        verdict = (
            f"D4 fired {d4_count} times "
            f"(flags containing drift_source_profile_version). "
            f"Series C total decisions={total_decisions}, anomalies={anomaly_decisions}. "
            f"S2 victim entity={s2_entity!r} (raw={s2_raw!r}); "
            f"attack-window profiles by created_at: shadows={shadow_count} vs "
            f"promoted={promoted_count} (ever: shadows={shadow_ever}, "
            f"promoted={promoted_ever}); "
            f"attack events with active alert at ts={n_active_at_ts}/"
            f"{n_attack_with_decision}. "
            f"score_event does receive db from process_unscored_events "
            f"(same SessionLocal/db_session) — not the failure mode. "
        )
        if d4_count == 0:
            verdict += (
                f"Most likely seam: {likely} — {reason} "
                f"Exact shadow gate: only after "
                f"entity_has_active_uncleared_alert(db, entity_id) which requires an "
                f"anomaly DecisionRecord whose AlertWorkflowState is in "
                f"{{new,acknowledged,investigating}} "
                f"(missing workflow row defaults to 'new')."
            )
        else:
            verdict += reason

        out = {
            "db": str(DB_PATH),
            "database_url_env": os.environ.get("DATABASE_URL"),
            "d4_flag_count": d4_count,
            "d4_examples": d4_examples,
            "total_decisions": int(total_decisions),
            "anomaly_decisions": int(anomaly_decisions),
            "s2": {
                "scenario": SCENARIO,
                "raw_entity_id": s2_raw,
                "entity_id": s2_entity,
                "attack_window": attack_window,
                "attack_event_count": len(attack_event_ids),
                "attack_decisions": attack_decisions,
                "workflows": workflows,
                "had_active_workflow_during_attack_window": had_active_during_attack,
                "had_active_workflow_ever": had_active_at_all,
                "profiles_in_attack_window": {
                    "shadow_count": shadow_count,
                    "promoted_count": promoted_count,
                    "rows": profile_rows[:50],
                    "rows_truncated": len(profile_rows) > 50,
                    "note": (
                        "Filtered by created_at within attack sim window; "
                        "empty when created_at is sweep wall-clock."
                    ),
                },
                "profiles_ever": {
                    "shadow_count": shadow_ever,
                    "promoted_count": promoted_ever,
                },
                "as_of_clock_skew": as_of_clock_skew,
            },
            "shadow_consult_gate": shadow_gate_condition(),
            "seams": seams,
            "most_likely_seam_if_zero": likely,
            "most_likely_reason": reason,
            "verdict": verdict,
        }

        OUT_JSON.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        print(json.dumps({
            "d4_flag_count": d4_count,
            "total_decisions": total_decisions,
            "anomaly_decisions": anomaly_decisions,
            "s2_entity": s2_entity,
            "shadow_ever": shadow_ever,
            "shadows_as_of_eligible": shadows_created_le_attack_end,
            "active_at_ts": n_active_at_ts,
            "most_likely_seam": likely,
        }, indent=2, default=str))
        print("\n=== VERDICT ===")
        print(verdict)
        print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
