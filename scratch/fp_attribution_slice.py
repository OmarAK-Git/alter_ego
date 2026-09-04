"""Post-hoc FP attribution on an existing Series I DB.

Does not invent per-scenario precision. Buckets FPs by partition, victim
entity, inject-window calendar, and dominant contribution feature.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "alter_ego_calibrate_series_i_ws_precision_gate.db"
OUT_JSON = ROOT / "scratch" / "fp_attribution_slice.json"
THR = 45.0


def parse_ts(v: str) -> datetime:
    s = str(v).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")


def contrib_map(raw: str) -> dict[str, float]:
    items = json.loads(raw) if raw else []
    out: dict[str, float] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("feature_name")
            if name:
                out[str(name)] = float(item.get("contribution_score") or 0.0)
    return out


def dominant_feature(cmap: dict[str, float]) -> str:
    if not cmap:
        return "(none)"
    name, score = max(cmap.items(), key=lambda kv: kv[1])
    if score <= 0:
        return "(all_zero)"
    return name


def main() -> None:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    gt = {
        r["event_id"]: r["scenario"]
        for r in conn.execute(
            "SELECT event_id, scenario FROM eval_ground_truth WHERE is_malicious = 1"
        )
    }
    gt_ids = set(gt)

    # Victim entities + inject windows from labeled attack events.
    victims: dict[str, set[str]] = defaultdict(set)
    windows: dict[str, tuple[datetime, datetime]] = {}
    scenario_event_ts: dict[str, list[datetime]] = defaultdict(list)
    for r in conn.execute(
        """
        SELECT e.event_id, e.raw_entity_id, e.timestamp, g.scenario
        FROM events e
        JOIN eval_ground_truth g ON g.event_id = e.event_id
        WHERE g.is_malicious = 1
        """
    ):
        ts = parse_ts(r["timestamp"])
        victims[r["scenario"]].add(r["raw_entity_id"])
        scenario_event_ts[r["scenario"]].append(ts)
    for scenario, tss in scenario_event_ts.items():
        windows[scenario] = (min(tss), max(tss))

    victim_to_scenarios: dict[str, list[str]] = defaultdict(list)
    for scenario, ents in victims.items():
        for eid in ents:
            victim_to_scenarios[eid].append(scenario)
    all_victims = set(victim_to_scenarios)

    s3_victims = victims.get("scenario_3_subtle", set())
    s3_peers = set()
    for r in conn.execute(
        "SELECT DISTINCT raw_entity_id FROM events WHERE raw_entity_id LIKE 'user_finance_%'"
    ):
        eid = r["raw_entity_id"]
        if eid not in s3_victims:
            s3_peers.add(eid)

    # Scored decisions at the operating point.
    fps: list[dict] = []
    tps = 0
    for r in conn.execute(
        """
        SELECT d.event_id, d.entity_id, d.timestamp, d.score, d.contributions,
               d.flags, e.simulation_partition, e.event_type, e.raw_entity_id
        FROM decisions d
        JOIN events e ON e.event_id = d.event_id
        WHERE d.score >= ?
        """,
        (THR,),
    ):
        eid = r["event_id"]
        if eid in gt_ids:
            tps += 1
            continue
        cmap = contrib_map(r["contributions"])
        flags = json.loads(r["flags"] or "{}")
        if isinstance(flags, dict):
            drift_alert = bool(flags.get("drift_alert"))
        elif isinstance(flags, list):
            drift_alert = "drift_alert" in flags
        else:
            drift_alert = False
        fps.append(
            {
                "event_id": eid,
                "entity_id": r["entity_id"],
                "raw_entity_id": r["raw_entity_id"],
                "timestamp": parse_ts(r["timestamp"]),
                "score": float(r["score"]),
                "partition": r["simulation_partition"],
                "event_type": r["event_type"],
                "dominant": dominant_feature(cmap),
                "drift_alert": drift_alert,
                "contrib": cmap,
            }
        )

    n_fp = len(fps)

    by_partition = Counter(fp["partition"] for fp in fps)
    by_event_type = Counter(fp["event_type"] for fp in fps)
    by_dominant = Counter(fp["dominant"] for fp in fps)
    by_drift = Counter("drift_alert" if fp["drift_alert"] else "no_drift" for fp in fps)

    def entity_bucket(raw_id: str) -> str:
        scs = victim_to_scenarios.get(raw_id)
        if scs:
            return "victim:" + ",".join(sorted(scs))
        if raw_id in s3_peers:
            return "s3_finance_peer"
        if raw_id.startswith("user_"):
            return "never_attacked_human"
        if raw_id.startswith("svc_"):
            return "never_attacked_service"
        return "never_attacked_other"

    by_entity = Counter(entity_bucket(fp["raw_entity_id"]) for fp in fps)

    # Mutually exclusive: partition first, then victim, then S3 peer, else background.
    exclusive = Counter()
    for fp in fps:
        if fp["partition"] != "production":
            exclusive[f"eval_partition:{fp['partition']}"] += 1
        elif fp["raw_entity_id"] in all_victims:
            exclusive["victim_production"] += 1
        elif fp["raw_entity_id"] in s3_peers:
            exclusive["s3_finance_peer_production"] += 1
        else:
            exclusive["unattributed_background"] += 1

    # Calendar: FP/day vs inject windows (inclusive date span).
    by_day = Counter(fp["timestamp"].date().isoformat() for fp in fps)
    window_dates = {
        scenario: (
            lo.date().isoformat(),
            hi.date().isoformat(),
        )
        for scenario, (lo, hi) in windows.items()
    }

    def in_window(ts: datetime, scenario: str) -> bool:
        lo, hi = windows[scenario]
        return lo - timedelta(hours=12) <= ts <= hi + timedelta(hours=12)

    during_any = 0
    during_by_scenario = Counter()
    for fp in fps:
        hit = False
        for scenario in windows:
            if in_window(fp["timestamp"], scenario):
                during_by_scenario[scenario] += 1
                hit = True
        if hit:
            during_any += 1

    # Rate: FPs on never-attacked vs victims (unique entities).
    fp_entities = Counter(fp["raw_entity_id"] for fp in fps)
    victim_fp_entities = {e: n for e, n in fp_entities.items() if e in all_victims}
    never_fp_entities = {e: n for e, n in fp_entities.items() if e not in all_victims}

    # Scored-event denominators for rates.
    scored_by_partition = dict(
        conn.execute(
            """
            SELECT e.simulation_partition, COUNT(*)
            FROM decisions d JOIN events e ON e.event_id = d.event_id
            GROUP BY e.simulation_partition
            """
        )
    )

    out = {
        "database": str(DB_PATH),
        "threshold": THR,
        "calibrated": False,
        "headline": {
            "tp": tps,
            "fp": n_fp,
            "precision": tps / (tps + n_fp) if (tps + n_fp) else 0.0,
            "gt_malicious_events": len(gt),
        },
        "victims": {k: sorted(v) for k, v in victims.items()},
        "inject_windows": {
            k: {"start": lo.isoformat(), "end": hi.isoformat()}
            for k, (lo, hi) in windows.items()
        },
        "fp_by_partition": dict(by_partition),
        "scored_by_partition": scored_by_partition,
        "fp_rate_by_partition": {
            p: (by_partition.get(p, 0) / n if n else 0.0)
            for p, n in scored_by_partition.items()
        },
        "fp_by_event_type": dict(by_event_type),
        "fp_by_entity_class": dict(by_entity),
        "exclusive_attribution": dict(exclusive),
        "exclusive_share_of_fp": {k: v / n_fp for k, v in exclusive.items()} if n_fp else {},
        "fp_during_any_inject_window": during_any,
        "fp_during_inject_window_by_scenario": dict(during_by_scenario),
        "note_windows_overlap": "Inject windows overlap on the calendar; during_* counts are not exclusive.",
        "fp_by_day": dict(sorted(by_day.items())),
        "inject_window_dates": window_dates,
        "fp_by_dominant_feature": dict(by_dominant.most_common()),
        "fp_by_drift_flag": dict(by_drift),
        "entities_with_fps": {
            "victim_entities_with_fp": len(victim_fp_entities),
            "never_attacked_entities_with_fp": len(never_fp_entities),
            "top_never_attacked": sorted(
                never_fp_entities.items(), key=lambda kv: -kv[1]
            )[:15],
            "victim_fp_counts": sorted(
                victim_fp_entities.items(), key=lambda kv: -kv[1]
            ),
        },
        "verdict_hint": None,
    }

    bg = exclusive.get("unattributed_background", 0)
    if n_fp and bg / n_fp >= 0.8:
        out["verdict_hint"] = (
            "FPs are mostly unattributed production background on never-attacked "
            "entities — detection rules / thr=45, not one attack scenario."
        )
    elif n_fp and (n_fp - bg) / n_fp >= 0.5:
        out["verdict_hint"] = (
            "A large share of FPs sit on eval partitions, victims, or S3 peers — "
            "inject collateral is load-bearing; inspect those buckets."
        )
    else:
        out["verdict_hint"] = "Mixed: report both background and collateral shares."

    OUT_JSON.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "headline",
        "fp_by_partition",
        "exclusive_attribution",
        "exclusive_share_of_fp",
        "fp_by_entity_class",
        "fp_by_dominant_feature",
        "fp_by_drift_flag",
        "fp_during_any_inject_window",
        "fp_during_inject_window_by_scenario",
        "verdict_hint",
        "victims",
        "inject_windows",
    )}, indent=2, default=str))
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
