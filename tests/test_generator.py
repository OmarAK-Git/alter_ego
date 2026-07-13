from batch.synthetic.generator import EventGenerator
from core.schemas.events import ProcessEventData
from datetime import datetime, timedelta


def test_scenario_2_attack_events_use_eval_partition():
    gen = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 15)
    events, labels = gen.generate_baseline(start, end)
    events, labels = gen.inject_scenario_2_slow_roll(
        events, labels, start + timedelta(days=8)
    )

    attack_event_ids = {label["event_id"] for label in labels}
    attack_events = [e for e in events if e.event_id in attack_event_ids]

    assert len(attack_events) == 35
    assert all(e.simulation_partition == "eval_scenario_2" for e in attack_events)


def test_scenario_3_attack_events_use_eval_partition():
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


def test_attack_partitions_remain_eval_scenario_after_s1_1():
    """Full eval mix: attacks use eval_scenario_*; benign paths stay production."""
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
    assert not any(e.simulation_partition == "production" for e in attack_events)
    assert all(e.simulation_partition == "production" for e in benign_events)

    event_by_id = {e.event_id: e for e in events}
    scenario_expected = {
        "scenario_1_sharp_misuse": "eval_scenario_1",
        "scenario_2_slow_roll": "eval_scenario_2",
        "scenario_3_subtle": "eval_scenario_3",
        "scenario_4_service_abuse": "eval_scenario_4",
    }
    for label in labels:
        assert (
            event_by_id[label["event_id"]].simulation_partition
            == scenario_expected[label["scenario"]]
        )


def test_event_generator_deterministic():
    gen1 = EventGenerator(seed=42)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 2)
    events1, labels1 = gen1.generate_baseline(start, end)
    
    gen2 = EventGenerator(seed=42)
    events2, labels2 = gen2.generate_baseline(start, end)
    
    # Event IDs must be identical for the same seed
    assert events1[0].event_id == events2[0].event_id
    assert events1[0].raw_entity_id == events2[0].raw_entity_id

    # The schemas should be well-formed
    assert events1[0].event_type in ["auth", "process"]
