from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from core.schemas.events import AuthEventData, Event, ProcessEventData


def write_mini_pipeline_jsonl(
    dir_path: Path,
    *,
    night_login: bool = False,
    command_line: str | None = None,
    baseline_weekdays: int | None = None,
) -> tuple[Path, Path]:
    """Emit two-engineer weekday JSONL for deterministic eval fixtures."""
    weekday_count = baseline_weekdays if baseline_weekdays is not None else (10 if night_login else 3)
    events_path = dir_path / "events.jsonl"
    labels_path = dir_path / "labels.jsonl"
    events: list[Event] = []
    day = datetime(2026, 1, 1)
    weekdays_emitted = 0
    last_weekday = day
    while weekdays_emitted < weekday_count:
        if day.weekday() < 5:
            weekdays_emitted += 1
            last_weekday = day
            for hour in range(9, 17):
                for idx, eid in enumerate(("user_engineer_0", "user_engineer_1")):
                    ts = day.replace(hour=hour, minute=0, second=0)
                    events.append(
                        Event(
                            event_id=f"evt_{eid}_{day.strftime('%Y%m%d')}_{hour}",
                            timestamp=ts,
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
        day += timedelta(days=1)
    if night_login:
        # Place the attack after the last weekday at 10:00+ so it occupies its
        # own day-window. Baseline stays auth-only: chrome process events make
        # empty command_line logins hit embedding=50 on day 2, then D3
        # auto-resolves those workflows before the pin can observe state=new.
        attack_day = last_weekday + timedelta(days=1)
        attack_days_emitted = 0
        while attack_days_emitted < 2:
            if attack_day.weekday() < 5:
                attack_days_emitted += 1
                events.append(
                    Event(
                        event_id=f"evt_night_{attack_day.strftime('%Y%m%d')}",
                        timestamp=attack_day.replace(hour=10, minute=5, second=0),
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
                for burst in range(6):
                    events.append(
                        Event(
                            event_id=(
                                f"evt_night_process_{attack_day.strftime('%Y%m%d')}_{burst}"
                            ),
                            timestamp=attack_day.replace(
                                hour=10 + burst, minute=20, second=0
                            ),
                            event_type="process",
                            raw_entity_id="user_engineer_0",
                            simulation_partition="production",
                            event_data=ProcessEventData(
                                process_name="mimikatz.exe",
                                command_line=(
                                    "mimikatz.exe privilege::debug "
                                    f"sekurlsa::logonpasswords burst={burst}"
                                ),
                                parent_process_name="cmd.exe",
                                endpoint_id="unknown_device",
                            ),
                        )
                    )
            attack_day += timedelta(days=1)
    if command_line is not None:
        events.append(
            Event(
                event_id="evt_inject_cmd",
                timestamp="2026-01-03T12:00:00",
                event_type="process",
                raw_entity_id="user_engineer_0",
                simulation_partition="production",
                event_data=ProcessEventData(
                    process_name="curl.exe",
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
