"""Decompose accepted Series I TP/FP scores by contribution.

Replay-only: no threshold change, no campaign rerun.
DB: local Series I precision-gate solo (headline-identical to fold_06 accept).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "alter_ego_calibrate_series_i_ws_precision_gate.db"
OUT_JSON = ROOT / "scratch" / "score_contribution_decompose.json"
THR = 45.0
DAMP_CAP = THR - 5.0  # scorer: min(threshold-5, raw_total)

FEATURES = [
    "login_hour_rarity",
    "geolocation_rarity",
    "endpoint_set_rarity",
    "process_name_rarity",
    "command_line_embedding_similarity",
    "total_volume_delta",
    "drift_alert",
    "service_account_execution_frequency_deviation",
]


def pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p / 100.0
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return ys[lo]
    return ys[lo] * (hi - k) + ys[hi] * (k - lo)


def distro(xs: list[float]) -> dict[str, Any]:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": mean(xs),
        "std": (sum((x - mean(xs)) ** 2 for x in xs) / len(xs)) ** 0.5,
        "min": min(xs),
        "p25": pct(xs, 25),
        "median": median(xs),
        "p75": pct(xs, 75),
        "p90": pct(xs, 90),
        "p95": pct(xs, 95),
        "max": max(xs),
        "share_at_cap_50": sum(1 for x in xs if x >= 50.0 - 1e-9) / len(xs),
    }


def hist(xs: list[float], edges: list[float]) -> dict[str, int]:
    labels = []
    for i, e in enumerate(edges[:-1]):
        labels.append(f"[{e:g},{edges[i+1]:g})")
    labels.append(f">={edges[-1]:g}")
    counts = [0] * len(labels)
    for x in xs:
        placed = False
        for i in range(len(edges) - 1):
            if edges[i] <= x < edges[i + 1]:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return dict(zip(labels, counts))


def parse_contribs(raw: str) -> list[dict]:
    items = json.loads(raw) if raw else []
    return items if isinstance(items, list) else []


def maps(items: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    scores: dict[str, float] = {}
    raws: dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("feature_name")
        if not name:
            continue
        scores[str(name)] = float(item.get("contribution_score") or 0.0)
        raws[str(name)] = float(item.get("raw_value") or 0.0)
    return scores, raws


def dominant(scores: dict[str, float]) -> str:
    if not scores:
        return "(none)"
    name, val = max(scores.items(), key=lambda kv: kv[1])
    return name if val > 0 else "(all_zero)"


def feature_block(rows: list[dict], feature: str) -> dict[str, Any]:
    contrib = [r["scores"].get(feature, 0.0) for r in rows]
    raw = [r["raws"].get(feature, 0.0) for r in rows]
    final = [r["score"] for r in rows]
    remainder = [r["score"] - r["scores"].get(feature, 0.0) for r in rows]
    return {
        "counts": {
            "n": len(rows),
            "dominant_this_feature": sum(1 for r in rows if r["dominant"] == feature),
            "contrib_gt_0": sum(1 for x in contrib if x > 0),
        },
        "raw_value": distro(raw),
        "contribution": distro(contrib),
        "final_score": distro(final),
        "score_minus_this_contribution": distro(remainder),
    }


def ablation(rows: list[dict], feature: str, *, label: str) -> dict[str, Any]:
    """How many *FPs* fall below thr if this contribution is subtracted.

    Valid on undamped decisions (score == Σ contributions). Damped hits are
    capped at 40 and cannot be in the thr=45 set; counted separately.
    """
    fps = [r for r in rows if r["label"] == "fp"]
    tps = [r for r in rows if r["label"] == "tp"]
    damped_fp = sum(1 for r in fps if r["damped"])
    undamped_fp = [r for r in fps if not r["damped"]]

    def drop_count(subset: list[dict]) -> dict[str, Any]:
        below = 0
        still = 0
        for r in subset:
            new_score = r["score"] - r["scores"].get(feature, 0.0)
            if new_score < THR:
                below += 1
            else:
                still += 1
        n = len(subset)
        return {
            "n": n,
            "would_fall_below_45": below,
            "would_remain_ge_45": still,
            "fraction_fall_below_45": (below / n) if n else None,
        }

    return {
        "slice": label,
        "feature_removed": feature,
        "method": "new_score = recorded_score - contribution_score(feature); undamped only",
        "damped_fps_excluded": damped_fp,
        "fp": drop_count(undamped_fp),
        "tp_diagnostic_not_a_threshold_change": drop_count(
            [r for r in tps if not r["damped"]]
        ),
    }


def decompose(rows: list[dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for feat in FEATURES:
        contribs = [r["scores"].get(feat, 0.0) for r in rows]
        raws = [r["raws"].get(feat, 0.0) for r in rows]
        if not rows:
            out[feat] = {"n": 0}
            continue
        share = [r["scores"].get(feat, 0.0) / r["score"] if r["score"] else 0.0 for r in rows]
        out[feat] = {
            "mean_contribution": mean(contribs),
            "median_contribution": median(contribs),
            "mean_raw": mean(raws),
            "mean_share_of_final_score": mean(share),
            "n_nonzero_contrib": sum(1 for x in contribs if x > 0),
        }
    out["dominant_feature"] = dict(Counter(r["dominant"] for r in rows))
    out["mean_final_score"] = mean(r["score"] for r in rows) if rows else None
    out["n"] = len(rows)
    return out


def main() -> None:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    gt = {
        r[0]
        for r in conn.execute(
            "SELECT event_id FROM eval_ground_truth WHERE is_malicious = 1"
        )
    }

    rows: list[dict] = []
    recon_err = []
    for event_id, entity_id, ts, score, confidence, contrib_raw, flags_raw, event_type in conn.execute(
        """
        SELECT d.event_id, d.entity_id, d.timestamp, d.score, d.confidence,
               d.contributions, d.flags, e.event_type
        FROM decisions d
        JOIN events e ON e.event_id = d.event_id
        WHERE d.score >= ?
        """,
        (THR,),
    ):
        items = parse_contribs(contrib_raw)
        scores, raws = maps(items)
        raw_total = sum(scores.values())
        recon_err.append(abs(float(score) - raw_total))
        flags = json.loads(flags_raw or "[]")
        if isinstance(flags, dict):
            flag_list = [k for k, v in flags.items() if v]
        elif isinstance(flags, list):
            flag_list = [str(x) for x in flags]
        else:
            flag_list = []
        damped = "low_confidence_damping_applied" in flag_list
        label = "tp" if event_id in gt else "fp"
        rows.append(
            {
                "event_id": event_id,
                "entity_id": entity_id,
                "timestamp": ts,
                "score": float(score),
                "confidence": float(confidence or 0.0),
                "scores": scores,
                "raws": raws,
                "dominant": dominant(scores),
                "event_type": event_type,
                "label": label,
                "damped": damped,
                "flag_list": flag_list,
            }
        )

    tps = [r for r in rows if r["label"] == "tp"]
    fps = [r for r in rows if r["label"] == "fp"]
    process = [r for r in rows if r["event_type"] == "process"]
    auth = [r for r in rows if r["event_type"] == "auth"]
    process_tp = [r for r in process if r["label"] == "tp"]
    process_fp = [r for r in process if r["label"] == "fp"]
    auth_tp = [r for r in auth if r["label"] == "tp"]
    auth_fp = [r for r in auth if r["label"] == "fp"]

    drift_raw_edges = [0.0, 1.0, 2.0, 2.25, 2.5, 5.0, 10.0]
    drift_contrib_edges = [0.0, 10.0, 20.0, 30.0, 40.0, 45.0, 50.0]
    emb_raw_edges = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    emb_contrib_edges = [0.0, 10.0, 20.0, 30.0, 40.0, 45.0, 50.0]
    score_edges = [45.0, 50.0, 55.0, 60.0, 70.0, 85.0, 100.0]

    def slice_report(subset_tp: list[dict], subset_fp: list[dict], feature: str, kind: str) -> dict:
        all_rows = subset_tp + subset_fp
        return {
            "event_type": kind,
            "focus_feature": feature,
            "tp_count": len(subset_tp),
            "fp_count": len(subset_fp),
            "tp": feature_block(subset_tp, feature),
            "fp": feature_block(subset_fp, feature),
            "histograms": {
                "tp_raw": hist([r["raws"].get(feature, 0.0) for r in subset_tp], drift_raw_edges if feature == "drift_alert" else emb_raw_edges),
                "fp_raw": hist([r["raws"].get(feature, 0.0) for r in subset_fp], drift_raw_edges if feature == "drift_alert" else emb_raw_edges),
                "tp_contribution": hist([r["scores"].get(feature, 0.0) for r in subset_tp], drift_contrib_edges if feature == "drift_alert" else emb_contrib_edges),
                "fp_contribution": hist([r["scores"].get(feature, 0.0) for r in subset_fp], drift_contrib_edges if feature == "drift_alert" else emb_contrib_edges),
                "tp_final_score": hist([r["score"] for r in subset_tp], score_edges),
                "fp_final_score": hist([r["score"] for r in subset_fp], score_edges),
            },
            "ablation_remove_feature": ablation(all_rows, feature, label=f"{kind}:{feature}"),
        }

    out = {
        "database": str(DB_PATH),
        "source": "local series_i_ws_precision_gate; headline-identical to fold_06 accept",
        "threshold": THR,
        "calibrated": False,
        "n_anomaly_decisions": len(rows),
        "tp": len(tps),
        "fp": len(fps),
        "damped_in_anomaly_set": sum(1 for r in rows if r["damped"]),
        "reconstruction": {
            "max_abs_score_minus_sum_contrib": max(recon_err) if recon_err else None,
            "mean_abs_score_minus_sum_contrib": mean(recon_err) if recon_err else None,
            "note": "ablation subtracts contribution from recorded score; valid when this error is ~0 and damped_in_anomaly_set is 0",
        },
        "overall_tp_fp_decomposition": {
            "tp": decompose(tps),
            "fp": decompose(fps),
        },
        "drift_alert_process": slice_report(process_tp, process_fp, "drift_alert", "process"),
        "embedding_auth": slice_report(auth_tp, auth_fp, "command_line_embedding_similarity", "auth"),
        "event_type_mix": {
            "process_tp": len(process_tp),
            "process_fp": len(process_fp),
            "auth_tp": len(auth_tp),
            "auth_fp": len(auth_fp),
        },
        "formulas": {
            "drift_alert": "contribution = min(50, cumulative_drift / 5 * 100); cap at drift=2.5; drift alone crosses 45 at drift≈2.25",
            "command_line_embedding_similarity": "raw=cosine_distance; contribution = min(50, (dist-0.50)*50*weight2) if dist>0.50 else 0",
        },
    }

    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")

    def brief_distro(d: dict) -> str:
        if d.get("n", 0) == 0:
            return "n=0"
        return (
            f"n={d['n']} mean={d['mean']:.3f} p50={d['median']:.3f} "
            f"p90={d['p90']:.3f} max={d['max']:.3f} cap50={d['share_at_cap_50']:.2%}"
        )

    print("=== reconstruction ===")
    print(json.dumps(out["reconstruction"], indent=2))
    print("damped_in_anomaly_set", out["damped_in_anomaly_set"])
    print("\n=== overall mean contribution TP vs FP ===")
    for feat in FEATURES:
        tp_m = out["overall_tp_fp_decomposition"]["tp"][feat]["mean_contribution"]
        fp_m = out["overall_tp_fp_decomposition"]["fp"][feat]["mean_contribution"]
        print(f"  {feat:45s}  TP {tp_m:8.3f}  FP {fp_m:8.3f}")
    print("  dominant TP", out["overall_tp_fp_decomposition"]["tp"]["dominant_feature"])
    print("  dominant FP", out["overall_tp_fp_decomposition"]["fp"]["dominant_feature"])

    for key, title in (
        ("drift_alert_process", "drift_alert on PROCESS"),
        ("embedding_auth", "embedding on AUTH"),
    ):
        s = out[key]
        print(f"\n=== {title}  TP={s['tp_count']} FP={s['fp_count']} ===")
        print("  TP raw     ", brief_distro(s["tp"]["raw_value"]))
        print("  FP raw     ", brief_distro(s["fp"]["raw_value"]))
        print("  TP contrib ", brief_distro(s["tp"]["contribution"]))
        print("  FP contrib ", brief_distro(s["fp"]["contribution"]))
        print("  TP score   ", brief_distro(s["tp"]["final_score"]))
        print("  FP score   ", brief_distro(s["fp"]["final_score"]))
        print("  hist fp raw", s["histograms"]["fp_raw"])
        print("  hist fp contrib", s["histograms"]["fp_contribution"])
        print("  hist fp score", s["histograms"]["fp_final_score"])
        ab = s["ablation_remove_feature"]
        print("  ablation FP would fall <45:", ab["fp"])
        print("  ablation TP would fall <45 (diagnostic):", ab["tp_diagnostic_not_a_threshold_change"])

    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
