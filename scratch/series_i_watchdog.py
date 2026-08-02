"""Watchdog for Series I: cadence completion + parallel-probe safe resume.

Does NOT kill volume/geo/flag solo probes. Only stops the serial campaign
orchestrator after ws_cadence_2 metrics land, then resumes campaign once
parallel weight/flag solos are done (or immediately if none pending).
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
METRICS = RESULTS / "series_i_ws_cadence_2_metrics.json"
STATE = WF / "state.json"
FLAG = RESULTS / "WATCHDOG_DONE"
LOG = RESULTS / "watchdog.log"

# Steps launched by series_i_parallel_weights.py
PARALLEL_STEPS = [
    "ws_volume_1",
    "ws_volume_5",
    "ws_volume_15",
    "ws_geo_5",
    "ws_feat_volume",
    "ws_fleet",
    "ws_precision_gate",
    "ws_staged_drift",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    line = f"{utc_now()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def kill_campaign_only() -> None:
    """Kill run_series_i_campaign.py only — spare cadence + parallel sweeps."""
    ps = r"""
Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and ($_.CommandLine -match 'run_series_i_campaign\.py')
} | ForEach-Object {
  Write-Output ("KILL_CAMPAIGN " + $_.ProcessId)
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
    time.sleep(2)


def restore_shared_yaml_if_needed() -> None:
    backup = REPO / "config" / "scoring_config.yaml.series_i_ws_cadence_2_backup"
    cfg = REPO / "config" / "scoring_config.yaml"
    if backup.exists():
        # Only restore after cadence metrics exist (cadence process exiting).
        import shutil

        shutil.copy2(backup, cfg)
        log("Restored scoring_config.yaml from cadence_2 backup (copy, backup kept)")


def parallel_pending(state: dict) -> list[str]:
    completed = set(state.get("sweeps_completed") or [])
    pending = []
    for step in PARALLEL_STEPS:
        if step in completed:
            continue
        if (RESULTS / f"series_i_{step}_metrics.json").exists():
            continue
        info = (state.get("parallel_probes") or {}).get(step) or {}
        if info.get("status") in {"done", "failed"}:
            continue
        pending.append(step)
    return pending


def write_cadence_governance() -> None:
    """Minimal evidence note if campaign did not get to write it."""
    path = RESULTS / "scoring-config-governance-series-i-ws_cadence_2.md"
    if path.exists():
        return
    try:
        payload = json.loads(METRICS.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"Could not read cadence metrics for governance: {exc}")
        return
    h = payload.get("headline") or {}
    path.write_text(
        "\n".join(
            [
                "# Scoring-config governance — Series I / ws_cadence_2",
                "",
                f"**Timestamp:** {utc_now()}",
                "**Status:** **Not CALIBRATED.** Decision: **evidence** (watchdog)",
                "",
                "## Overrides under test",
                "",
                "```",
                "drift_weights.cadence.enabled=true",
                "drift_weights.cadence.weight=2.0",
                "```",
                "",
                "## Headline @ thr=45",
                "",
                f"- P={h.get('precision')} R={h.get('recall')} F1={h.get('f1')}",
                f"- TP/FP/FN={h.get('tp')}/{h.get('fp')}/{h.get('fn')}",
                f"- S1/S4={h.get('s1')}/{h.get('s4')} S2/S3/S5={h.get('s2')}/{h.get('s3')}/{h.get('s5')}",
                "",
                "Evidence from completed cadence probe. calibrated: false.",
                "Winner selection / short-circuit handled on campaign resume.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    log(f"Wrote {path.name}")


def resume_campaign() -> int:
    log_path = RESULTS / "campaign_resume.log"
    with open(log_path, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(REPO / "scratch" / "run_series_i_campaign.py")],
            cwd=str(REPO),
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    log(f"Resumed campaign pid={proc.pid} log={log_path}")
    return proc.pid


def main() -> int:
    log(f"Watchdog waiting for {METRICS}")
    while not METRICS.exists():
        time.sleep(30)

    log("Cadence metrics appeared; stopping campaign only (sparing parallel probes)")
    kill_campaign_only()
    restore_shared_yaml_if_needed()
    write_cadence_governance()

    state = json.loads(STATE.read_text(encoding="utf-8"))
    completed = state.setdefault("sweeps_completed", [])
    if "ws_cadence_2" not in completed:
        completed.append("ws_cadence_2")
    queued = state.setdefault("sweeps_queued", [])
    for s in ("ws_cadence_2", "ws_cadence_5", "ws_cadence_10"):
        if s in queued:
            queued.remove(s)
    for s in ("ws_cadence_5", "ws_cadence_10"):
        skip = f"{s}_SKIPPED"
        if skip not in completed:
            completed.append(skip)
        # Also mark base names so campaign _need() skips them
        if s not in completed:
            completed.append(s)

    state["current_step"] = "post_cadence_2_watchdog"
    state["updated_at"] = utc_now()
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Wait for parallel solos if still running
    while True:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        pending = parallel_pending(state)
        if not pending:
            break
        log(f"Waiting on parallel probes: {pending}")
        time.sleep(60)

    # Absorb any metrics that landed without sweeps_completed update
    state = json.loads(STATE.read_text(encoding="utf-8"))
    completed = state.setdefault("sweeps_completed", [])
    queued = state.setdefault("sweeps_queued", [])
    for step in PARALLEL_STEPS:
        if (RESULTS / f"series_i_{step}_metrics.json").exists() and step not in completed:
            completed.append(step)
        if step in queued and step in completed:
            queued.remove(step)
    state["current_step"] = "post_parallel_weights"
    state["updated_at"] = utc_now()
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    FLAG.write_text(f"ready-to-resume {utc_now()}\n", encoding="utf-8")
    resume_campaign()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
