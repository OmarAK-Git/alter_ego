from __future__ import annotations

from pathlib import Path

from core.schemas.events import AuthEventData, Event, ProcessEventData


def write_mini_pipeline_jsonl(
    dir_path: Path,
    *,
    night_login: bool = False,
    command_line: str | None = None,
) -> tuple[Path, Path]:
    """Emit two-engineer, three-weekday JSONL for deterministic eval fixtures."""
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
    if command_line is not None:
        events.append(
            Event(
                event_id="evt_process_injection",
                timestamp="2026-01-03T10:00:00",
                event_type="process",
                raw_entity_id="user_engineer_0",
                simulation_partition="production",
                event_data=ProcessEventData(
                    process_name="powershell.exe",
                    command_line=command_line,
                    parent_process_name="explorer.exe",
                    endpoint_id="ep_0",
                ),
            )
        )
    with events_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(event.model_dump_json() + "\n")
    labels_path.write_text(
        '{"event_id":"evt_user_engineer_0_1_9","is_malicious":false,"scenario":"none"}\n',
        encoding="utf-8",
    )
    return events_path, labels_path
