from batch.synthetic.generator import EventGenerator
from datetime import datetime

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
