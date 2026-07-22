"""Partition → builder visibility (Design 1 §0.2).

S2/S3/S5 feed the profile builder; S1/S4 do not. Labels stay on eval_scenario_*.
"""

from pathlib import Path

import yaml

from batch.synthetic.generator import EventGenerator
from core.schemas.events import ProcessEventData
from datetime import datetime, timedelta

# Authoritative table — keep in sync with Design 1 spec §0.2
FEEDS_BUILDER = {
    "scenario_1_sharp_misuse": False,
    "scenario_2_slow_roll": True,
    "scenario_3_subtle": True,
    "scenario_4_service_abuse": False,
    "scenario_5_patient_cycle": True,
}
PARTITION_BY_SCENARIO = {
    "scenario_1_sharp_misuse": "eval_scenario_1",
    "scenario_2_slow_roll": "eval_scenario_2",
    "scenario_3_subtle": "eval_scenario_3",
    "scenario_4_service_abuse": "eval_scenario_4",
    "scenario_5_patient_cycle": "eval_scenario_5",
}
BUILDER_PARTITIONS = frozenset(
    {"production", "eval_scenario_2", "eval_scenario_3", "eval_scenario_5"}
)

_S5_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "boil_the_frog"
    / "s5_patient_cycle.yaml"
)
_S2_LADDER = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "boil_the_frog"
    / "s2_process_ladder.yaml"
)


def test_scenario_2_tagged_eval_and_feeds_builder():
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    events, labels = gen.inject_scenario_2_slow_roll([], [], start + timedelta(days=8))
    attack_events = [e for e in events if e.event_id in {lb["event_id"] for lb in labels}]

    assert len(attack_events) == 35
    assert all(e.simulation_partition == "eval_scenario_2" for e in attack_events)
    assert "eval_scenario_2" in BUILDER_PARTITIONS
    assert FEEDS_BUILDER["scenario_2_slow_roll"] is True


def test_scenario_3_tagged_eval_and_feeds_builder():
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 15)
    events, labels = gen.generate_baseline(start, end)
    events, labels = gen.inject_scenario_3_coordinated(
        events, labels, start + timedelta(days=11)
    )
    attack_event_ids = {label["event_id"] for label in labels}
    attack_events = [e for e in events if e.event_id in attack_event_ids]

    assert len(attack_events) == 45
    assert all(e.simulation_partition == "eval_scenario_3" for e in attack_events)
    assert "eval_scenario_3" in BUILDER_PARTITIONS
    assert FEEDS_BUILDER["scenario_3_subtle"] is True


def test_scenario_1_and_4_do_not_feed_builder():
    """S1/S4 remain builder-excluded (sharp / service point attacks)."""
    assert FEEDS_BUILDER["scenario_1_sharp_misuse"] is False
    assert FEEDS_BUILDER["scenario_4_service_abuse"] is False
    assert "eval_scenario_1" not in BUILDER_PARTITIONS
    assert "eval_scenario_4" not in BUILDER_PARTITIONS


def test_baseline_events_remain_production_partition():
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 2)
    events, _ = gen.generate_baseline(start, end)

    assert len(events) > 0
    assert all(e.simulation_partition == "production" for e in events)


def test_benign_only_baseline_smoke_production_partition():
    """Smoke: benign-only generation runs and tags every event production."""
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 7)
    events, labels = gen.generate_baseline(start, end)

    assert len(events) > 0
    assert labels == []
    assert {e.simulation_partition for e in events} == {"production"}


def test_correlated_benign_rollout_stays_production():
    """Correlated benign tooling rollout remains production, not eval attack."""
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 7)
    events, _ = gen.generate_baseline(start, end)
    events = gen.inject_tooling_rollout(
        events, start + timedelta(days=3), "Engineer", "new_sec_agent.exe"
    )

    rollout_events = [
        e
        for e in events
        if isinstance(e.event_data, ProcessEventData)
        and e.event_data.process_name == "new_sec_agent.exe"
    ]

    assert len(rollout_events) == 45
    assert all(e.simulation_partition == "production" for e in rollout_events)
    assert not any(e.simulation_partition.startswith("eval_scenario_") for e in rollout_events)


def test_attack_partitions_match_scenario_table():
    """Full eval mix: partitions follow §0.2 table; benign stays production."""
    gen = EventGenerator(seed=1337)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 15)

    events, labels = gen.generate_baseline(start, end)
    events = gen.inject_tooling_rollout(
        events, start + timedelta(days=5), "Engineer", "new_sec_agent.exe"
    )
    events, labels = gen.inject_scenario_1_sharp_misuse(
        events, labels, start + timedelta(days=10)
    )
    events, labels = gen.inject_scenario_2_slow_roll(
        events, labels, start + timedelta(days=8)
    )
    events, labels = gen.inject_scenario_3_coordinated(
        events, labels, start + timedelta(days=11)
    )
    events, labels = gen.inject_scenario_4_service_abuse(
        events, labels, start + timedelta(days=12)
    )

    attack_event_ids = {label["event_id"] for label in labels}
    attack_events = [e for e in events if e.event_id in attack_event_ids]
    benign_events = [e for e in events if e.event_id not in attack_event_ids]

    assert len(attack_events) > 0
    assert len(benign_events) > 0
    assert all(e.simulation_partition.startswith("eval_scenario_") for e in attack_events)
    assert all(e.simulation_partition == "production" for e in benign_events)

    event_by_id = {e.event_id: e for e in events}
    for label in labels:
        scenario = label["scenario"]
        part = event_by_id[label["event_id"]].simulation_partition
        assert part == PARTITION_BY_SCENARIO[scenario]
        feeds = part in BUILDER_PARTITIONS
        assert feeds is FEEDS_BUILDER[scenario]


def test_builder_partition_constant_matches_code():
    """Guard: BUILDER_PARTITIONS matches batch/profile_builder/builder.py filter."""
    import inspect
    from batch.profile_builder import builder as builder_mod

    src = inspect.getsource(builder_mod.build_profiles)
    assert "eval_scenario_2" in src
    assert "eval_scenario_3" in src
    assert "eval_scenario_5" in src
    assert (
        'builder_partitions = ("production", "eval_scenario_2", "eval_scenario_3", "eval_scenario_5")'
        in src
    )


def test_scenario_5_attack_events_on_eval_scenario_5():
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 3)
    events, labels = gen.inject_scenario_5_patient_cycle([], [], start)
    attack_ids = {lb["event_id"] for lb in labels if lb.get("is_malicious")}
    attack_events = [e for e in events if e.event_id in attack_ids]

    assert len(attack_events) == 35  # 7 ladder days × 5 bursts
    assert all(e.simulation_partition == "eval_scenario_5" for e in attack_events)
    assert "eval_scenario_5" in BUILDER_PARTITIONS
    assert FEEDS_BUILDER["scenario_5_patient_cycle"] is True


def test_scenario_5_labels_patient_cycle():
    gen = EventGenerator(seed=42)
    _, labels = gen.inject_scenario_5_patient_cycle([], [], datetime(2026, 1, 3))
    malicious = [lb for lb in labels if lb.get("is_malicious")]
    assert malicious
    assert all(lb["scenario"] == "scenario_5_patient_cycle" for lb in malicious)


def test_scenario_5_quiet_gaps_at_least_four_days():
    """Between attack clusters, ≥ quiet_days (4) calendar days with no attack."""
    with open(_S5_FIXTURE, encoding="utf-8") as f:
        fixture = yaml.safe_load(f)
    quiet_days = int(fixture["quiet_days"])
    assert quiet_days >= 4

    gen = EventGenerator(seed=42)
    events, labels = gen.inject_scenario_5_patient_cycle([], [], datetime(2026, 1, 3))
    attack_ids = {lb["event_id"] for lb in labels if lb.get("is_malicious")}
    attack_dates = sorted(
        {e.timestamp.date() for e in events if e.event_id in attack_ids}
    )

    # Collapse consecutive attack dates into clusters
    clusters: list[list] = []
    for d in attack_dates:
        if not clusters or (d - clusters[-1][-1]).days > 1:
            clusters.append([d])
        else:
            clusters[-1].append(d)
    assert len(clusters) == len(fixture["rung_segments"])

    for prev, nxt in zip(clusters, clusters[1:]):
        gap = (nxt[0] - prev[-1]).days
        assert gap >= quiet_days, (
            f"quiet gap {gap}d between {prev[-1]} and {nxt[0]} < quiet_days={quiet_days}"
        )


def test_scenario_5_attack_process_names_match_ladder():
    with open(_S2_LADDER, encoding="utf-8") as f:
        ladder = yaml.safe_load(f)
    ladder_by_day = {int(k): set(v) for k, v in ladder["ladder_by_day"].items()}

    gen = EventGenerator(seed=42)
    events, labels = gen.inject_scenario_5_patient_cycle([], [], datetime(2026, 1, 3))
    attack_ids = {lb["event_id"] for lb in labels if lb.get("is_malicious")}
    attack_events = sorted(
        [e for e in events if e.event_id in attack_ids], key=lambda e: e.timestamp
    )

    # Chronological attack calendar days map to ladder day indices 0..6
    attack_dates = sorted({e.timestamp.date() for e in attack_events})
    assert len(attack_dates) == 7
    day_index_by_date = {d: i for i, d in enumerate(attack_dates)}

    for e in attack_events:
        assert isinstance(e.event_data, ProcessEventData)
        day_idx = day_index_by_date[e.timestamp.date()]
        assert e.event_data.process_name in ladder_by_day[day_idx]


def test_scenario_5_quiet_events_eval_partition_not_malicious():
    gen = EventGenerator(seed=42)
    events, labels = gen.inject_scenario_5_patient_cycle([], [], datetime(2026, 1, 3))
    attack_ids = {lb["event_id"] for lb in labels if lb.get("is_malicious")}
    s5_events = [e for e in events if e.simulation_partition == "eval_scenario_5"]
    quiet = [e for e in s5_events if e.event_id not in attack_ids]

    assert quiet
    assert all(e.simulation_partition == "eval_scenario_5" for e in quiet)
    assert not any(e.event_id in attack_ids for e in quiet)
    # Quiet must not be labeled malicious
    malicious_ids = {lb["event_id"] for lb in labels if lb.get("is_malicious")}
    assert not any(e.event_id in malicious_ids for e in quiet)


def test_scenario_2_and_5_victims_differ_with_exclude():
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    events, labels = gen.inject_scenario_2_slow_roll([], [], start + timedelta(days=8))
    s2_ids = {lb["event_id"] for lb in labels if lb["scenario"] == "scenario_2_slow_roll"}
    s2_victim = next(e.raw_entity_id for e in events if e.event_id in s2_ids)

    events, labels = gen.inject_scenario_5_patient_cycle(
        events, labels, start + timedelta(days=2), exclude_entity_ids={s2_victim}
    )
    s5_ids = {
        lb["event_id"]
        for lb in labels
        if lb.get("scenario") == "scenario_5_patient_cycle" and lb.get("is_malicious")
    }
    s5_victim = next(e.raw_entity_id for e in events if e.event_id in s5_ids)
    assert s2_victim != s5_victim


def test_event_generator_deterministic():
    gen1 = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 2)
    events1, labels1 = gen1.generate_baseline(start, end)

    gen2 = EventGenerator(seed=42)
    events2, labels2 = gen2.generate_baseline(start, end)

    assert events1[0].event_id == events2[0].event_id
    assert events1[0].raw_entity_id == events2[0].raw_entity_id
    assert events1[0].event_type in ["auth", "process"]
