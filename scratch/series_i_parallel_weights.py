"""Launch Series I weight + weightless-flag solo probes in parallel.

Each probe uses an isolated YAML via ALTER_EGO_SCORING_CONFIG (see
run_series_i_sweep.py) and its own sqlite DB. Does not touch the live
shared scoring_config.yaml used by the in-flight ws_cadence_2 sweep.

Does NOT run additive fold stacks — solo screens vs baseline only.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF = REPO / ".workflow" / "2026-08-02-series-i-serial-calibration"
RESULTS = WF / "results"
STATE = WF / "state.json"
SWEEP = REPO / "scratch" / "run_series_i_sweep.py"
COLLECTOR_FLAG = RESULTS / "PARALLEL_COLLECTOR_DONE"

# Solo probes that do not depend on cadence/volume/geo weight winners.
PROBES: list[tuple[str, list[str]]] = [
    # Volume-drift weight grid
    (
        "ws_volume_1",
        [
            "drift_weights.total_volume_delta.enabled=true",
            "drift_weights.total_volume_delta.weight=1.0",
        ],
    ),
    (
        "ws_volume_5",
        [
            "drift_weights.total_volume_delta.enabled=true",
            "drift_weights.total_volume_delta.weight=5.0",
        ],
    ),
    (
        "ws_volume_15",
        [
            "drift_weights.total_volume_delta.enabled=true",
            "drift_weights.total_volume_delta.weight=15.0",
        ],
    ),
    # Geo one-shot
    (
        "ws_geo_5",
        [
            "drift_weights.geo_velocity.enabled=true",
            "drift_weights.geo_velocity.weight=5.0",
        ],
    ),
    # Weightless flag solos (enable-only vs baseline)
    (
        "ws_feat_volume",
        ["features.total_volume_delta.enabled=true"],
    ),
    (
        "ws_fleet",
        ["cohort_gating_constants.fleet_drift_enabled=true"],
    ),
    (
        "ws_precision_gate",
        ["precision_gate.enabled=true"],
    ),
    (
        "ws_staged_drift",
        ["staged_drift.enabled=true"],
    ),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    state["updated_at"] = utc_now()
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def metrics_exist(step: str) -> bool:
    return (RESULTS / f"series_i_{step}_metrics.json").exists()


def launch_probe(step: str, sets: list[str]) -> subprocess.Popen:
    log = RESULTS / f"series_i_{step}_sweep.log"
    cmd = [sys.executable, "-u", str(SWEEP), "--step", step]
    for s in sets:
        cmd.extend(["--set", s])
    RESULTS.mkdir(parents=True, exist_ok=True)
    fh = open(log, "a", encoding="utf-8")
    fh.write(f"\n=== parallel launch {utc_now()} ===\n")
    fh.flush()
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO),
        stdout=fh,
        stderr=subprocess.STDOUT,
    )
    # Keep fh open for the child lifetime (Windows inherits handle).
    proc._series_i_log_fh = fh  # type: ignore[attr-defined]
    return proc


def main() -> int:
    state = load_state()
    parallel = state.setdefault("parallel_probes", {})
    running: dict[str, subprocess.Popen] = {}

    for step, sets in PROBES:
        completed = state.get("sweeps_completed") or []
        if step in completed or metrics_exist(step):
            print(f"SKIP {step} (already done)", flush=True)
            continue
        info = parallel.get(step) or {}
        if info.get("status") == "running" and info.get("pid"):
            # Re-attach if process still alive
            try:
                import os

                os.kill(int(info["pid"]), 0)
                print(f"ALREADY RUNNING {step} pid={info['pid']}", flush=True)
                continue
            except OSError:
                pass

        proc = launch_probe(step, sets)
        running[step] = proc
        parallel[step] = {
            "pid": proc.pid,
            "status": "running",
            "sets": sets,
            "started_at": utc_now(),
            "db": f"alter_ego_calibrate_series_i_{step}.db",
            "config": f"config/scoring_config.series_i_{step}.yaml",
            "log": str(RESULTS / f"series_i_{step}_sweep.log"),
        }
        print(f"LAUNCHED {step} pid={proc.pid}", flush=True)

    state["parallel_weight_mode"] = True
    state["phase"] = "A_weight_search_parallel"
    state["current_step"] = "parallel_weight_and_flag_solos"
    # Ensure queued steps include weightless solos for bookkeeping
    queued = state.setdefault("sweeps_queued", [])
    for step, _ in PROBES:
        if step not in queued and step not in (state.get("sweeps_completed") or []):
            # insert before folds
            fold_idx = next((i for i, s in enumerate(queued) if s.startswith("fold_")), len(queued))
            if step not in queued:
                queued.insert(fold_idx, step)
    save_state(state)

    if not running:
        print("Nothing new to launch", flush=True)
        return 0

    # Wait until all launched children exit (collector companion also watches).
    print(f"Waiting on {len(running)} probes…", flush=True)
    while running:
        for step, proc in list(running.items()):
            rc = proc.poll()
            if rc is None:
                continue
            fh = getattr(proc, "_series_i_log_fh", None)
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass
            parallel[step]["status"] = "done" if rc == 0 else "failed"
            parallel[step]["exit_code"] = rc
            parallel[step]["finished_at"] = utc_now()
            completed = state.setdefault("sweeps_completed", [])
            if rc == 0 and step not in completed:
                completed.append(step)
            queued = state.get("sweeps_queued") or []
            if step in queued:
                queued.remove(step)
            save_state(state)
            print(f"FINISHED {step} rc={rc}", flush=True)
            del running[step]
        time.sleep(15)

    COLLECTOR_FLAG.write_text(f"launcher-wait-done {utc_now()}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
