from __future__ import annotations

from pathlib import Path

from core.schemas.events import AuthEventData, Event


def _write_two_day_login(dir_path: Path, *, night_login: bool = False) -> tuple[Path, Path]:
    events_path = dir_path / "events.jsonl"
    labels_path = dir_path / "labels.jsonl"
    events: list[Event] = []
    for day in (1, 2, 3):
        for hour in range(9, 17):
            for idx, eid in enumerate(("user_engineer_0", "user_engineer_1")):
                events.append(
                    Event(
                        event_id=f"evt_{eid}_{day}_{hour}",
                        timestamp=f"2026-01-0{day}T{hour:02d}:00:00",
                        event_type="auth",
                        raw_entity_id=eid,
                        simulation_partition="production",
                        event_data=AuthEventData(
                            action="login",
                            ip_address="192.0.2.10",
                            geolocation="US-East",
                            endpoint_id=f"ep_{idx}",
                        ),
                    )
                )
    if night_login:
        events.append(
            Event(
                event_id="evt_night",
                timestamp="2026-01-03T03:15:00",
                event_type="auth",
                raw_entity_id="user_engineer_0",
                simulation_partition="production",
                event_data=AuthEventData(
                    action="login",
                    ip_address="198.51.100.10",
                    geolocation="RU-Moscow",
                    endpoint_id="unknown_device",
                ),
            )
        )
    with events_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(event.model_dump_json() + "\n")
    labels_path.write_text("", encoding="utf-8")
    return events_path, labels_path


def test_run_production_call_invokes_all_five_stages_and_does_not_insert_decisions_itself(
    tmp_path, monkeypatch
):
    from batch.eval.e2e_kernel import run_production_call

    events_path, labels_path = _write_two_day_login(tmp_path)
    result = run_production_call(events_path, labels_path, sqlite_path=tmp_path / "eval.db")
    assert result.stages == {
        "ingest_events": True,
        "process_unresolved_events": True,
        "build_profiles": True,
        "process_unscored_events": True,
        "record_decision": True,
    }
    assert result.event_count >= 2
    assert result.resolved_count >= 2
    assert result.profile_count >= 1
    assert result.decision_count >= 1
    assert result.seeded_decision_insert is False


def test_cli_writes_scorecard_and_exits_nonzero_on_missing_row(tmp_path, monkeypatch):
    import subprocess
    import sys

    out = tmp_path / "scorecard.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "batch.eval.e2e_kernel",
            "--scorecard-out",
            str(out),
            "--assert-complete",
            "--only",
            "des.production_call_shape",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**__import__("os").environ, "PYTHONPATH": "."},
        capture_output=True,
        text=True,
    )
    # After Task 2 only the kernel stub exists; completeness must fail until all 15 land.
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "PermissionError" not in (proc.stderr or "")
    assert "missing scorecard rows" in (proc.stderr or "")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "des.production_call_shape" in text
    assert "old_build" in text
