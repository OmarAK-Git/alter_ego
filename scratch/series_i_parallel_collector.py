"""Collect completed parallel Series I solos: governance notes + state updates.

Runs alongside series_i_parallel_weights.py. Does not start Phase B folds.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".workflow" / "2026-08-02-series-i-serial-calibration"
RESULTS = WF / "results"
STATE = WF / "state.json"

BASELINE = {
    "precision": 0.006708907938874394,
    "recall": 0.46153846153846156,
    "f1": 0.01322556943423953,
    "tp": 54,
    "fp": 7995,
    "fn": 63,
    "s1": 1.0,
    "s2": 0.7428571428571429,
    "s3": 0.1111111111111111,
    "s4": 1.0,
    "s5": 0.6,
}

PROBES: dict[str, list[str]] = {
    "ws_volume_1": [
        "drift_weights.total_volume_delta.enabled=true",
        "drift_weights.total_volume_delta.weight=1.0",
    ],
    "ws_volume_5": [
        "drift_weights.total_volume_delta.enabled=true",
        "drift_weights.total_volume_delta.weight=5.0",
    ],
    "ws_volume_15": [
        "drift_weights.total_volume_delta.enabled=true",
        "drift_weights.total_volume_delta.weight=15.0",
    ],
    "ws_geo_5": [
        "drift_weights.geo_velocity.enabled=true",
        "drift_weights.geo_velocity.weight=5.0",
    ],
    "ws_feat_volume": ["features.total_volume_delta.enabled=true"],
    "ws_fleet": ["cohort_gating_constants.fleet_drift_enabled=true"],
    "ws_precision_gate": ["precision_gate.enabled=true"],
    "ws_staged_drift": ["staged_drift.enabled=true"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def headline_of(payload: dict) -> dict:
    return dict(payload.get("headline") or {})


def floors_ok(h: dict) -> bool:
    s1, s4 = h.get("s1"), h.get("s4")
    if s1 is None or s4 is None:
        return False
    return float(s1) >= 1.0 - 1e-9 and float(s4) >= 1.0 - 1e-9


def is_inert(h: dict) -> bool:
    return (
        abs(int(h.get("tp") or -1) - BASELINE["tp"]) <= 0
        and abs(int(h.get("fp") or -1) - BASELINE["fp"]) <= 5
        and abs(float(h.get("f1") or 0) - BASELINE["f1"]) < 1e-6
    )


def rank_key(h: dict) -> tuple:
    return (
        float(h.get("f1") or 0.0),
        float(h.get("recall") or 0.0),
        -float(h.get("fp") if h.get("fp") is not None else 1e18),
    )


def decide(step: str, h: dict, payload: dict) -> tuple[str, str]:
    """Solo-screen decision for this dim/flag only (not additive fold)."""
    if not floors_ok(h):
        return "reject", f"REJECT {step}: S1/S4 floor collapse (S1={h.get('s1')} S4={h.get('s4')})"
    if is_inert(h):
        return "reject", f"REJECT {step}: inert vs Series E–H baseline"
    if rank_key(h) > rank_key(BASELINE):
        return "accept-candidate", (
            f"ACCEPT-CANDIDATE {step}: improves F1/R/FP vs baseline "
            f"(F1={h.get('f1')} R={h.get('recall')} FP={h.get('fp')}); "
            "final fold still deferred until weight phase closes"
        )
    # Non-inert geo mean-zero check
    if step == "ws_geo_5":
        decomp = (payload.get("metrics") or {}).get("per_dimension_drift_decomposition") or {}
        geo_mean = (decomp.get("geo_velocity") or {}).get("mean")
        if geo_mean is not None and float(geo_mean) == 0.0:
            return "reject", f"REJECT {step}: geo_velocity mean_delta=0 (inert dimension)"
    return "reject", (
        f"REJECT {step}: non-inert but does not beat baseline "
        f"(F1={h.get('f1')} R={h.get('recall')} FP={h.get('fp')})"
    )


def write_governance(step: str, decision: str, reason: str, h: dict, overrides: list[str]) -> None:
    path = RESULTS / f"scoring-config-governance-series-i-{step}.md"
    if path.exists():
        return
    path.write_text(
        "\n".join(
            [
                f"# Scoring-config governance — Series I / {step}",
                "",
                f"**Timestamp:** {utc_now()}",
                f"**Status:** **Not CALIBRATED.** Decision: **{decision}**",
                "",
                "## Overrides under test (solo screen)",
                "",
                "```",
                *overrides,
                "```",
                "",
                "## Headline @ thr=45",
                "",
                "| Metric | Value | Baseline |",
                "|---|---:|---:|",
                f"| P | {h.get('precision')} | {BASELINE['precision']} |",
                f"| R | {h.get('recall')} | {BASELINE['recall']} |",
                f"| F1 | {h.get('f1')} | {BASELINE['f1']} |",
                f"| TP / FP / FN | {h.get('tp')} / {h.get('fp')} / {h.get('fn')} | "
                f"{BASELINE['tp']} / {BASELINE['fp']} / {BASELINE['fn']} |",
                f"| S1 / S4 | {h.get('s1')} / {h.get('s4')} | {BASELINE['s1']} / {BASELINE['s4']} |",
                "",
                "## Decision reason",
                "",
                reason,
                "",
                "Solo screen only — not an additive fold. calibrated: false.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def maybe_update_weight_winners(state: dict) -> None:
    """When volume/geo grids finish, record winners (cadence left to campaign/watchdog)."""
    winners = state.setdefault("weight_winners", {})
    # Volume
    vol_steps = [("ws_volume_1", 1.0), ("ws_volume_5", 5.0), ("ws_volume_15", 15.0)]
    if all((RESULTS / f"series_i_{s}_metrics.json").exists() for s, _ in vol_steps) and (
        "total_volume_delta" not in winners
    ):
        viable = []
        for step, w in vol_steps:
            payload = json.loads((RESULTS / f"series_i_{step}_metrics.json").read_text(encoding="utf-8"))
            h = headline_of(payload)
            if floors_ok(h) and not is_inert(h) and rank_key(h) > rank_key(BASELINE):
                viable.append((w, h, step))
        if viable:
            viable.sort(key=lambda t: rank_key(t[1]), reverse=True)
            best_w, best_h, best_step = viable[0]
            winners["total_volume_delta"] = {
                "weight": best_w,
                "reason": f"Winner from {best_step}: F1={best_h.get('f1')} FP={best_h.get('fp')}",
            }
        else:
            winners["total_volume_delta"] = {
                "weight": None,
                "reason": "No volume-drift weight beats baseline (or floors/inert)",
            }
    # Geo
    if (RESULTS / "series_i_ws_geo_5_metrics.json").exists() and "geo_velocity" not in winners:
        payload = json.loads((RESULTS / "series_i_ws_geo_5_metrics.json").read_text(encoding="utf-8"))
        h = headline_of(payload)
        decision, reason = decide("ws_geo_5", h, payload)
        winners["geo_velocity"] = {
            "weight": 5.0 if decision == "accept-candidate" else None,
            "reason": reason,
        }
    # Flag solos → rejected_flags / accepted_flags candidates (not folded yet)
    for step, key in (
        ("ws_feat_volume", "features.total_volume_delta"),
        ("ws_fleet", "cohort_gating_constants.fleet_drift_enabled"),
        ("ws_precision_gate", "precision_gate.enabled"),
        ("ws_staged_drift", "staged_drift.enabled"),
    ):
        mpath = RESULTS / f"series_i_{step}_metrics.json"
        if not mpath.exists():
            continue
        gpath = RESULTS / f"scoring-config-governance-series-i-{step}.md"
        if not gpath.exists():
            continue
        # Decisions already in governance; mirror into state once
        text = gpath.read_text(encoding="utf-8")
        if "ACCEPT-CANDIDATE" in text:
            state.setdefault("solo_flag_candidates", {})[key] = step
        elif "REJECT" in text:
            state.setdefault("solo_flag_rejects", {})[key] = step


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    handled: set[str] = set()
    print(f"{utc_now()} collector watching {list(PROBES)}", flush=True)
    while True:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        all_done = True
        for step, overrides in PROBES.items():
            mpath = RESULTS / f"series_i_{step}_metrics.json"
            if not mpath.exists():
                # still pending if marked running
                info = (state.get("parallel_probes") or {}).get(step) or {}
                if info.get("status") == "running" or step not in (state.get("sweeps_completed") or []):
                    # If never launched and not completed, still pending from our perspective
                    if info.get("status") in {"done", "failed"} and not mpath.exists():
                        pass
                    elif not mpath.exists():
                        all_done = False
                continue
            if step in handled:
                continue
            payload = json.loads(mpath.read_text(encoding="utf-8"))
            h = headline_of(payload)
            decision, reason = decide(step, h, payload)
            write_governance(step, decision, reason, h, overrides)
            completed = state.setdefault("sweeps_completed", [])
            if step not in completed:
                completed.append(step)
            queued = state.get("sweeps_queued") or []
            if step in queued:
                queued.remove(step)
            probes = state.setdefault("parallel_probes", {})
            probes.setdefault(step, {})["status"] = "done"
            probes[step]["decision"] = decision
            probes[step]["reason"] = reason
            probes[step]["collected_at"] = utc_now()
            maybe_update_weight_winners(state)
            state["updated_at"] = utc_now()
            STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
            handled.add(step)
            print(f"{utc_now()} COLLECTED {step} → {decision}", flush=True)

        maybe_update_weight_winners(state)
        state["updated_at"] = utc_now()
        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

        if all_done and len(handled) >= len(PROBES):
            print(f"{utc_now()} all parallel probes collected", flush=True)
            (RESULTS / "PARALLEL_COLLECTOR_DONE").write_text(f"{utc_now()}\n", encoding="utf-8")
            return 0
        # Also exit if every probe has metrics or failed
        if all(
            (RESULTS / f"series_i_{s}_metrics.json").exists()
            or ((state.get("parallel_probes") or {}).get(s) or {}).get("status") == "failed"
            for s in PROBES
        ):
            if len(handled) >= sum(
                1 for s in PROBES if (RESULTS / f"series_i_{s}_metrics.json").exists()
            ):
                print(f"{utc_now()} collector exit (all terminal)", flush=True)
                (RESULTS / "PARALLEL_COLLECTOR_DONE").write_text(f"{utc_now()}\n", encoding="utf-8")
                return 0
        time.sleep(20)


if __name__ == "__main__":
    raise SystemExit(main())
