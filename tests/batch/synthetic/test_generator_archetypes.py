from datetime import datetime

from batch.synthetic.generator import EventGenerator


def test_ot_polling_archetype_fires_every_minute_with_zero_jitter():
    gen = EventGenerator(seed=42)
    ot_entities = [e for e in gen.entities.values() if getattr(e, "archetype", None) == "ot_polling"]
    assert len(ot_entities) >= 5, "expected a distinct ot_polling cohort, none found"
    for e in ot_entities:
        assert e.periodicity_minutes == 1
        assert e.jitter_minutes == 0.0


def test_it_automation_archetype_has_nonzero_jitter():
    gen = EventGenerator(seed=42)
    it_entities = [e for e in gen.entities.values() if getattr(e, "archetype", None) == "it_automation"]
    assert len(it_entities) >= 5
    for e in it_entities:
        assert e.jitter_minutes > 0.0


def test_ot_polling_events_are_tighter_interval_than_it_automation():
    gen = EventGenerator(seed=42)
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 1, 2, 0, 0)
    events, _ = gen.generate_baseline(start, end)

    ot_id = next(e.entity_id for e in gen.entities.values() if getattr(e, "archetype", None) == "ot_polling")
    it_id = next(e.entity_id for e in gen.entities.values() if getattr(e, "archetype", None) == "it_automation")

    def intervals(entity_id):
        ts = sorted(e.timestamp for e in events if e.raw_entity_id == entity_id)
        return [(ts[i + 1] - ts[i]).total_seconds() for i in range(len(ts) - 1)]

    ot_intervals = intervals(ot_id)
    it_intervals = intervals(it_id)
    assert ot_intervals, "ot_polling entity produced no events in the test window"
    assert max(ot_intervals) <= 60.0  # every-minute firing, allowing exact 60s spacing
    assert it_intervals
    assert (sum(it_intervals) / len(it_intervals)) > (sum(ot_intervals) / len(ot_intervals))
