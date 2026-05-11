import json
from datetime import datetime, timedelta
from batch.synthetic.generator import EventGenerator

def generate_scenario3_mixed(events_path: str, labels_path: str):
    gen = EventGenerator(seed=42)
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 15)
    
    events, labels = gen.generate_baseline(start_date, end_date)
    # Inject Scenario 3
    events, labels = gen.inject_scenario_3_coordinated(events, labels, start_date + timedelta(days=11))
    
    gen.save_to_disk(events, labels, events_path, labels_path)
    print(f"Generated {len(events)} events with Scenario 3 injection.")

if __name__ == "__main__":
    generate_scenario3_mixed("scenario3_events.jsonl", "scenario3_labels.jsonl")
