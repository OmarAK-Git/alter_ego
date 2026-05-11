import json
import uuid
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select
from core.database import SessionLocal, Base, engine
from core.models import ResolvedEventModel, ProfileArtifactModel, DecisionRecordModel, ContainmentQueueModel
from batch.profile_builder.builder import build_profiles

def create_event(entity_id, role, process_name, timestamp, partition="production"):
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.isoformat(),
        "entity_id": entity_id,
        "entity_type": "human",
        "role": role,
        "event_data": {
            "action": "process_start",
            "endpoint_id": "server_1",
            "process_name": process_name,
            "command_line": f"{process_name} --args"
        },
        "simulation_partition": partition,
        "resolution_confidence": 1.0
    }

def run_test():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    
    entity_id_1 = "user_test_1"
    entity_id_2 = "user_test_2"
    role = "dev"
    
    # 1. Establish baseline (Clean Profile 1)
    events = []
    base_time = datetime(2026, 1, 1)
    for i in range(10):
        ts = base_time + timedelta(days=i)
        events.append(create_event(entity_id_1, role, "explorer.exe", ts))
        events.append(create_event(entity_id_2, role, "explorer.exe", ts))
    
    for e in events:
        db_e = ResolvedEventModel(
            event_id=e["event_id"],
            timestamp=datetime.fromisoformat(e["timestamp"]),
            entity_id=e["entity_id"],
            entity_type=e["entity_type"],
            raw_entity_id=e["entity_id"],
            event_type="process",
            simulation_partition=e["simulation_partition"],
            event_data=e["event_data"],
            resolution_confidence=e["resolution_confidence"]
        )
        db.add(db_e)
    db.commit()
    
    print("Building Baseline Profile...")
    build_profiles(db, as_of=base_time + timedelta(days=10))
    
    # 2. Add Drifting Activity (Clean Profile 2)
    # Entity 1 drifts to powershell. Entity 2 stays on explorer.
    drift_events = []
    for i in range(10, 20):
        ts = base_time + timedelta(days=i)
        drift_events.append(create_event(entity_id_1, role, "powershell.exe", ts))
        drift_events.append(create_event(entity_id_2, role, "explorer.exe", ts))
        
    for e in drift_events:
        db_e = ResolvedEventModel(
            event_id=e["event_id"],
            timestamp=datetime.fromisoformat(e["timestamp"]),
            entity_id=e["entity_id"],
            entity_type=e["entity_type"],
            raw_entity_id=e["entity_id"],
            event_type="process",
            simulation_partition=e["simulation_partition"],
            event_data=e["event_data"],
            resolution_confidence=e["resolution_confidence"]
        )
        db.add(db_e)
    db.commit()
    
    print("Building Second Profile (Expect Drift for Entity 1)...")
    build_profiles(db, as_of=base_time + timedelta(days=20))
    
    # Verify drift accumulator
    p1 = db.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id_1).order_by(ProfileArtifactModel.data_window_end.desc()).first()
    p2 = db.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id_2).order_by(ProfileArtifactModel.data_window_end.desc()).first()
    
    print(f"Entity 1 Cumulative Drift: {p1.features.get('cumulative_drift', 0.0):.2f}")
    print(f"Entity 2 Cumulative Drift: {p2.features.get('cumulative_drift', 0.0):.2f}")
    
    # Check for Drift Alert
    decision = db.query(DecisionRecordModel).filter(DecisionRecordModel.entity_id == entity_id_1).first()
    if decision:
        print(f"Drift Alert Fired! Score: {decision.score:.2f}, Flags: {decision.flags}")
    else:
        print("No Drift Alert (Threshold likely higher than drift).")

    # 3. Test Active-alert blocking
    print("\nTesting Active-alert blocking...")
    # Put entity under containment
    db.add(ContainmentQueueModel(entity_id=entity_id_1, decision_id="manual", action="block", status="pending"))
    db.commit()
    
    # Add more activity
    shadow_events = []
    for i in range(20, 25):
        ts = base_time + timedelta(days=i)
        shadow_events.append(create_event(entity_id_1, role, "malicious.exe", ts))
        
    for e in shadow_events:
        db_e = ResolvedEventModel(
            event_id=e["event_id"],
            timestamp=datetime.fromisoformat(e["timestamp"]),
            entity_id=e["entity_id"],
            entity_type=e["entity_type"],
            raw_entity_id=e["entity_id"],
            event_type="process",
            simulation_partition=e["simulation_partition"],
            event_data=e["event_data"],
            resolution_confidence=e["resolution_confidence"]
        )
        db.add(db_e)
    db.commit()
    
    build_profiles(db, as_of=base_time + timedelta(days=25))
    
    latest_profile = db.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id_1).order_by(ProfileArtifactModel.data_window_end.desc()).first()
    print(f"Latest Profile is shadow: {latest_profile.is_shadow}")
    
    db.close()

if __name__ == "__main__":
    run_test()
