from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from batch.synthetic.generator import EventGenerator
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


def write_sanctuary_jsonl(dir_path: Path) -> tuple[Path, Path]:
    """FP-before-ladder topology for T-PATIENT P0. Does not claim a detection win."""
    events_path, labels_path = write_mini_pipeline_jsonl(dir_path, night_login=True)
    ladder_day = datetime(2026, 1, 19)
    extras: list[Event] = []
    label_lines = [
        '{"event_id":"evt_night_20260115","is_malicious":false,"scenario":"none"}',
        '{"event_id":"evt_night_20260116","is_malicious":false,"scenario":"none"}',
    ]
    names = ("git.exe", "git.exe", "python.exe", "python.exe", "git.exe")
    cmds = (
        "git.exe --silent",
        "git.exe --silent",
        "python.exe -v --workdir=/home/eng",
        "python.exe -v --workdir=/home/eng",
        "git.exe --silent",
    )
    for burst, (name, cmd) in enumerate(zip(names, cmds, strict=True)):
        event_id = f"evt_ladder_{burst}"
        extras.append(
            Event(
                event_id=event_id,
                timestamp=ladder_day.replace(hour=10, minute=burst * 10, second=0),
                event_type="process",
                raw_entity_id="user_engineer_0",
                simulation_partition="eval_scenario_2",
                event_data=ProcessEventData(
                    process_name=name,
                    command_line=cmd,
                    parent_process_name="explorer.exe",
                    endpoint_id="ep_0",
                ),
            )
        )
        label_lines.append(
            json.dumps(
                {
                    "event_id": event_id,
                    "is_malicious": True,
                    "scenario": "scenario_2_slow_roll",
                }
            )
        )
    with events_path.open("a", encoding="utf-8") as fh:
        for event in extras:
            fh.write(event.model_dump_json() + "\n")
    labels_path.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
    return events_path, labels_path


def write_compact_seed42_s2_s3_s5_jsonl(dir_path: Path) -> tuple[Path, Path]:
    gen = EventGenerator(seed=42)
    keep = {
        eid: ent
        for eid, ent in gen.entities.items()
        if (
            (eid.startswith("user_engineer_") and int(eid.rsplit("_", 1)[1]) < 12)
            or (eid.startswith("user_finance_") and int(eid.rsplit("_", 1)[1]) < 12)
        )
    }
    gen.entities = keep
    start = datetime(2026, 1, 1, 0, 0, 0)
    events: list[Event] = []
    labels: list[dict] = []
    day = start
    while day < start + timedelta(days=10):
        if day.weekday() < 5:
            for ent in gen.entities.values():
                if ent.entity_type != "human":
                    continue
                for hour in range(9, 17):
                    ts = day.replace(hour=hour, minute=0, second=0)
                    events.append(
                        Event(
                            event_id=f"base_{ent.entity_id}_{ts.strftime('%Y%m%d%H')}",
                            timestamp=ts,
                            event_type="auth",
                            raw_entity_id=ent.entity_id,
                            simulation_partition="production",
                            event_data=AuthEventData(
                                action="login",
                                ip_address="192.0.2.10",
                                geolocation=ent.geography,
                                endpoint_id=ent.primary_endpoint,
                            ),
                        )
                    )
        day += timedelta(days=1)
    events, labels = gen.inject_scenario_2_slow_roll(events, labels, datetime(2026, 1, 2))
    events, labels = gen.inject_scenario_3_coordinated(events, labels, datetime(2026, 1, 6))
    s2_label = next(lb for lb in labels if lb.get("scenario") == "scenario_2_slow_roll")
    s2_event = next(e for e in events if e.event_id == s2_label["event_id"])
    events, labels = gen.inject_scenario_5_patient_cycle(
        events, labels, datetime(2026, 1, 2), exclude_entity_ids={s2_event.raw_entity_id}
    )
    gen.save_to_disk(
        events, labels, str(dir_path / "events.jsonl"), str(dir_path / "labels.jsonl")
    )
    return dir_path / "events.jsonl", dir_path / "labels.jsonl"

