"""Watchdog: after ws_cadence_2 metrics land, stop old campaign and resume with short-circuit code."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
METRICS = (
    REPO
    / ".workflow"
    / "2026-08-02-series-i-serial-calibration"
    / "results"
    / "series_i_ws_cadence_2_metrics.json"
)
STATE = REPO / ".workflow" / "2026-08-02-series-i-serial-calibration" / "state.json"
FLAG = REPO / ".workflow" / "2026-08-02-series-i-serial-calibration" / "results" / "WATCHDOG_DONE"


def kill_series_i() -> None:
    ps = """
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'run_series_i')
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    time.sleep(2)


def main() -> int:
    print("Watchdog waiting for", METRICS, flush=True)
    while not METRICS.exists():
        time.sleep(30)
    print("Metrics appeared; killing campaign to resume with short-circuit", flush=True)
    kill_series_i()

    # Ensure config restored if backup left behind
    backup = REPO / "config" / "scoring_config.yaml.series_i_ws_cadence_2_backup"
    cfg = REPO / "config" / "scoring_config.yaml"
    if backup.exists():
        backup.replace(cfg)
        print("Restored scoring_config from cadence_2 backup", flush=True)

    state = json.loads(STATE.read_text(encoding="utf-8"))
    completed = state.setdefault("sweeps_completed", [])
    if "ws_cadence_2" not in completed:
        completed.append("ws_cadence_2")
    queued = state.setdefault("sweeps_queued", [])
    for s in ("ws_cadence_2", "ws_cadence_5", "ws_cadence_10"):
        if s in queued:
            queued.remove(s)
    # Mark higher cadence probes skipped; winner selection happens in campaign
    for s in ("ws_cadence_5", "ws_cadence_10"):
        if s not in completed:
            completed.append(s)
        skip = f"{s}_SKIPPED"
        if skip not in completed:
            completed.append(skip)
    state["current_step"] = "post_cadence_2_watchdog"
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    FLAG.write_text("killed-and-ready-to-resume\n", encoding="utf-8")

    # Relaunch campaign (skips completed; pick_weight_winner uses existing metrics)
    log = (
        REPO
        / ".workflow"
        / "2026-08-02-series-i-serial-calibration"
        / "results"
        / "campaign_resume.log"
    )
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(REPO / "scratch" / "run_series_i_campaign.py")],
            cwd=str(REPO),
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    print(f"Resumed campaign pid={proc.pid} log={log}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
