import json
from datetime import datetime, timedelta
from batch.synthetic.generator import EventGenerator

def generate_benign_only(events_path: str, labels_path: str):
    gen = EventGenerator(seed=42)
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 15)
    
    # Baseline only, no injections
    events, labels = gen.generate_baseline(start_date, end_date)
    
    gen.save_to_disk(events, labels, events_path, labels_path)
    print(f"Generated {len(events)} benign events.")

def generate_correlated_benign(events_path: str, labels_path: str):
    gen = EventGenerator(seed=42)
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 15)
    
    events, labels = gen.generate_baseline(start_date, end_date)
    # Inject correlated benign change (tooling rollout)
    events = gen.inject_tooling_rollout(events, start_date + timedelta(days=5), "Engineer", "new_sec_agent.exe")
    
    gen.save_to_disk(events, labels, events_path, labels_path)
    print(f"Generated {len(events)} correlated benign events.")

if __name__ == "__main__":
    generate_benign_only("benign_only_events.jsonl", "benign_only_labels.jsonl")
    generate_correlated_benign("correlated_benign_events.jsonl", "correlated_benign_labels.jsonl")
