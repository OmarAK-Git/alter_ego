"""Series I additive fold chain — serial governance + launch.

Folds are the main campaign. Each fold runs only after the prior fold has
metrics JSON. Solos (ws_*) are separate weight-search screens; do not block folds.

Usage:
  python scratch/series_i_fold_chain.py --watch          # poll + chain (default)
  python scratch/series_i_fold_chain.py --launch-next    # launch one pending fold
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".workflow" / "2026-08-02-series-i-serial-calibration"
RESULTS = WF / "results"
STATE_PATH = WF / "state.json"
CONFIG_PATH = REPO / "config" / "scoring_config.yaml"
CHUNKED_PS1 = REPO / "scratch" / "run_series_i_chunked.ps1"
POLL_SECONDS = 120

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

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

# Operator fold order (cadence/geo skipped). Volume drift last — provisional if grid pending.
FOLD_SPECS: list[dict[str, Any]] = [
    {
        "step": "fold_02_feature_volume",
        "new_sets": ["features.total_volume_delta.enabled=true"],
        "flag_label": "features.total_volume_delta",
    },
    {
        "step": "fold_06_precision_gate",
        "new_sets": ["precision_gate.enabled=true"],
        "flag_label": "precision_gate.enabled",
    },
    {
        "step": "fold_05_fleet",
        "new_sets": ["cohort_gating_constants.fleet_drift_enabled=true"],
        "flag_label": "cohort_gating_constants.fleet_drift_enabled",
    },
    {
        "step": "fold_07_staged_drift",
        "new_sets": ["staged_drift.enabled=true"],
        "flag_label": "staged_drift.enabled",
    },
    {
        "step": "fold_03_drift_volume",
        "new_sets": None,  # resolved at runtime from cloud volume grid or provisional 5.0
        "flag_label": "drift_weights.total_volume_delta",
        "volume_drift": True,
    },
]

SKIPPED_FOLDS = {"fold_01_cadence", "fold_04_geo"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    state["updated_at"] = utc_now()
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_metrics(step: str) -> dict:
    path = RESULTS / f"series_i_{step}_metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def headline_of(payload: dict) -> dict:
    h = dict(payload.get("headline") or {})
    if h:
        return h
    m = payload.get("metrics") or {}
    scenarios = m.get("scenarios") or {}
    return {
        "precision": m.get("precision"),
        "recall": m.get("recall"),
        "f1": m.get("f1"),
        "tp": m.get("tp"),
        "fp": m.get("fp"),
        "fn": m.get("fn"),
        "s1": (scenarios.get("scenario_1_sharp_misuse") or {}).get("recall"),
        "s2": (scenarios.get("scenario_2_slow_roll") or {}).get("recall"),
        "s3": (scenarios.get("scenario_3_subtle") or {}).get("recall"),
        "s4": (scenarios.get("scenario_4_service_abuse") or {}).get("recall"),
        "s5": (scenarios.get("scenario_5_patient_cycle") or {}).get("recall"),
    }


def rank_key(h: dict) -> tuple:
    return (
        float(h.get("f1") or 0.0),
        float(h.get("recall") or 0.0),
        -float(h.get("fp") if h.get("fp") is not None else 1e18),
    )


def floors_ok(h: dict) -> bool:
    s1, s4 = h.get("s1"), h.get("s4")
    if s1 is None or s4 is None:
        return False
    return float(s1) >= 1.0 - 1e-9 and float(s4) >= 1.0 - 1e-9


def decide_fold_vs_prev(h: dict, prev: dict, flag_label: str) -> tuple[str, str]:
    if not floors_ok(h):
        return "reject", (
            f"REJECT {flag_label}: S1/S4 floor collapse "
            f"(S1={h.get('s1')}, S4={h.get('s4')})"
        )
    if rank_key(h) > rank_key(prev):
        return "accept", (
            f"ACCEPT {flag_label}: improves vs prior accepted baseline "
            f"(F1 {prev.get('f1')}→{h.get('f1')}, R {prev.get('recall')}→{h.get('recall')}, "
            f"FP {prev.get('fp')}→{h.get('fp')})"
        )
    if (
        abs(float(h.get("f1") or 0) - float(prev.get("f1") or 0)) < 1e-9
        and abs(int(h.get("fp") or 0) - int(prev.get("fp") or 0)) <= 5
        and abs(float(h.get("recall") or 0) - float(prev.get("recall") or 0)) < 1e-9
    ):
        return "reject", f"REJECT {flag_label}: inert vs prior accepted baseline"
    return "reject", (
        f"REJECT {flag_label}: worse/equal rank vs prior accepted "
        f"(F1 {prev.get('f1')}→{h.get('f1')}, R {prev.get('recall')}→{h.get('recall')}, "
        f"FP {prev.get('fp')}→{h.get('fp')})"
    )


def sets_from_accepted(accepted: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k, v in accepted.items():
        if isinstance(v, bool):
            out.append(f"{k}={str(v).lower()}")
        else:
            out.append(f"{k}={v}")
    return out


def merge_sets(accepted: dict[str, Any], new_sets: list[str]) -> list[str]:
    merged: dict[str, str] = {}
    for item in sets_from_accepted(accepted) + new_sets:
        k, v = item.split("=", 1)
        merged[k] = v
    return [f"{k}={v}" for k, v in merged.items()]


def write_governance(step: str, decision: str, reason: str, headline: dict, overrides: list[str]) -> None:
    path = RESULTS / f"scoring-config-governance-series-i-{step}.md"
    lines = [
        f"# Scoring-config governance — Series I / {step}",
        "",
        f"**Timestamp:** {utc_now()}",
        f"**Status:** **Not CALIBRATED.** Decision: **{decision}**",
        "",
        "## Overrides under test",
        "",
        "```",
        *overrides,
        "```",
        "",
        "## Headline @ thr=45",
        "",
        f"| F1 | R | FP | S1 | S4 |",
        f"|---:|---:|---:|---:|---:|",
        f"| {headline.get('f1')} | {headline.get('recall')} | {headline.get('fp')} | "
        f"{headline.get('s1')} | {headline.get('s4')} |",
        "",
        "## Decision reason",
        "",
        reason,
        "",
        "Evidence report for Series I additive fold chain. calibrated: false.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def apply_accepted_yaml(accepted: dict[str, Any]) -> None:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config.setdefault("drift_weights", {})
    for dim in ("cadence", "total_volume_delta", "geo_velocity"):
        node = config["drift_weights"].setdefault(dim, {})
        if not isinstance(node, dict):
            node = {"weight": float(node), "enabled": False}
            config["drift_weights"][dim] = node
        node["enabled"] = False
        node.setdefault("weight", 0.0)
    feat_vol = config.setdefault("features", {}).setdefault("total_volume_delta", {})
    feat_vol["enabled"] = False
    feat_vol.setdefault("weight", 1.0)
    config.setdefault("cohort_gating_constants", {})["fleet_drift_enabled"] = False
    config.setdefault("precision_gate", {})["enabled"] = False
    config.setdefault("staged_drift", {})["enabled"] = False
    for path, value in accepted.items():
        parts = path.split(".")
        node = config
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


def git_commit(message: str, paths: list[str]) -> None:
    subprocess.run(["git", "add", "--"] + paths, cwd=str(REPO), check=False)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(REPO))
    if staged.returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", message], cwd=str(REPO), check=False)


def pick_volume_drift_weight(state: dict) -> tuple[float, str]:
    """Pick volume drift weight from cloud grid metrics or provisional 5.0."""
    candidates: list[tuple[str, float, dict]] = []
    for step, weight in [("ws_volume_1", 1.0), ("ws_volume_5", 5.0), ("ws_volume_15", 15.0)]:
        mpath = RESULTS / f"series_i_{step}_metrics.json"
        if mpath.exists():
            h = headline_of(load_metrics(step))
            if floors_ok(h):
                candidates.append((step, weight, h))
    if candidates:
        candidates.sort(key=lambda t: rank_key(t[2]), reverse=True)
        best_step, best_w, best_h = candidates[0]
        state.setdefault("weight_winners", {})["total_volume_delta"] = {
            "weight": best_w,
            "from_step": best_step,
            "f1": best_h.get("f1"),
            "recall": best_h.get("recall"),
            "fp": best_h.get("fp"),
        }
        return best_w, f"cloud grid winner {best_step} w={best_w}"
  # provisional mid-grid
    state.setdefault("fold_chain", {})["volume_drift_provisional"] = True
    return 5.0, "provisional w=5.0 pending cloud ws_volume_* confirmation"


def resolve_new_sets(spec: dict[str, Any], state: dict) -> list[str]:
    if spec.get("volume_drift"):
        weight, note = pick_volume_drift_weight(state)
        state.setdefault("fold_chain", {})["volume_drift_note"] = note
        return [
            "drift_weights.total_volume_delta.enabled=true",
            f"drift_weights.total_volume_delta.weight={weight}",
        ]
    return list(spec["new_sets"] or [])


def metrics_ready(step: str) -> bool:
    return (RESULTS / f"series_i_{step}_metrics.json").exists()


def lane_running(state: dict, step: str) -> bool:
    lane = (state.get("lanes") or {}).get(step) or {}
    return lane.get("status") in {"running", "queued"}


def launch_fold_local(step: str, combo: list[str], state: dict) -> int:
    """Launch chunked fold sweep locally (background subprocess)."""
    args = ["pwsh", "-File", str(CHUNKED_PS1), "-Step", step]
    for s in combo:
        args.extend(["-Set", s])
    log_path = RESULTS / f"series_i_{step}_sweep.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as logf:
        logf.write(f"\n=== fold chain launch {utc_now()} ===\n")
        proc = subprocess.Popen(
            args,
            cwd=str(REPO),
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
    state.setdefault("lanes", {})[step] = {
        "host": "local",
        "status": "running",
        "pid": proc.pid,
        "launched_at": utc_now(),
        "overrides": combo,
    }
    state["current_step"] = step
    save_state(state)
    logger.info("Launched %s locally pid=%s", step, proc.pid)
    return proc.pid


def process_completed_fold(spec: dict[str, Any], state: dict) -> bool:
    """Governance for a fold whose metrics JSON exists. Returns True if processed."""
    step = spec["step"]
    if step in (state.get("sweeps_completed") or []):
        return False
    if not metrics_ready(step):
        return False

    accepted: dict[str, Any] = dict(state.get("accepted_flags") or {})
    rejected: dict[str, Any] = dict(state.get("rejected_flags") or {})
    prev_headline = dict(state.get("fold_chain", {}).get("prev_headline") or BASELINE)

    new_sets = resolve_new_sets(spec, state)
    combo = merge_sets(accepted, new_sets)
    h = headline_of(load_metrics(step))
    decision, reason = decide_fold_vs_prev(h, prev_headline, spec["flag_label"])
    write_governance(step, decision, reason, h, combo)

    if decision == "accept":
        for item in new_sets:
            k, v = item.split("=", 1)
            if v in {"true", "false"}:
                accepted[k] = v == "true"
            else:
                try:
                    accepted[k] = float(v) if "." in v else int(v)
                except ValueError:
                    accepted[k] = float(v)
        apply_accepted_yaml(accepted)
        state.setdefault("fold_chain", {})["prev_headline"] = h
    else:
        rejected[spec["flag_label"]] = reason

    state["accepted_flags"] = accepted
    state["rejected_flags"] = rejected
    state.setdefault("lanes", {})[step] = {
        **(state.get("lanes", {}).get(step) or {}),
        "status": "done",
        "completed_at": utc_now(),
    }
    state.setdefault("sweeps_completed", []).append(step)
    queued = state.get("sweeps_queued") or []
    if step in queued:
        queued.remove(step)
    state["sweeps_queued"] = queued
    save_state(state)
    git_commit(
        f"Series I fold: {step} governance ({decision})",
        [str(RESULTS), str(STATE_PATH), str(CONFIG_PATH)],
    )
    logger.info("%s governance: %s — %s", step, decision, reason)
    return True


def next_pending_fold(state: dict) -> dict[str, Any] | None:
    completed = set(state.get("sweeps_completed") or [])
    for spec in FOLD_SPECS:
        step = spec["step"]
        if step in completed:
            continue
        if metrics_ready(step):
            continue
        if lane_running(state, step):
            continue
        return spec
    return None


def launch_next(state: dict) -> int | None:
    spec = next_pending_fold(state)
    if spec is None:
        logger.info("No pending fold to launch")
        return None
    step = spec["step"]
    accepted = dict(state.get("accepted_flags") or {})
    new_sets = resolve_new_sets(spec, state)
    combo = merge_sets(accepted, new_sets)
    return launch_fold_local(step, combo, state)


def watch_loop(state: dict) -> None:
    logger.info("Fold chain watcher started (poll=%ds)", POLL_SECONDS)
    while True:
        state = load_state()
        changed = False
        for spec in FOLD_SPECS:
            if process_completed_fold(spec, state):
                changed = True
                state = load_state()

        pending = next_pending_fold(state)
        running = any(
            lane_running(state, s["step"]) for s in FOLD_SPECS
        )
        if pending and not running:
            pid = launch_next(state)
            if pid:
                logger.info("Chained launch %s pid=%s", pending["step"], pid)
        elif not pending and not running:
            all_done = all(
                s["step"] in (state.get("sweeps_completed") or []) for s in FOLD_SPECS
            )
            if all_done:
                state["phase"] = "B_additive_folds_complete"
                state["current_step"] = "fold_chain_done"
                save_state(state)
                logger.info("Fold chain complete")
                return
        time.sleep(POLL_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Series I additive fold chain")
    parser.add_argument("--watch", action="store_true", help="Poll and chain folds (default)")
    parser.add_argument("--launch-next", action="store_true", help="Launch one pending fold")
    parser.add_argument("--process-done", action="store_true", help="Governance only for ready metrics")
    args = parser.parse_args()

    state = load_state()
    state["phase"] = "B_additive_folds"
    if "fold_chain" not in state:
        state["fold_chain"] = {
            "started_at": utc_now(),
            "order": [s["step"] for s in FOLD_SPECS],
            "skipped": sorted(SKIPPED_FOLDS),
            "prev_headline": BASELINE,
            "note": (
                "Folds are main campaign; started without waiting for all weight-search solos. "
                "Solos (ws_*) continue as screens. Volume drift fold uses cloud grid winner "
                "when metrics land, else provisional w=5.0."
            ),
        }
    save_state(state)

    if args.process_done:
        for spec in FOLD_SPECS:
            process_completed_fold(spec, state)
        return 0

    if args.launch_next:
        pid = launch_next(state)
        return 0 if pid else 1

    if args.watch or not (args.launch_next or args.process_done):
        watch_loop(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
