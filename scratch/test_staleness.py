from datetime import datetime
from core.database import SessionLocal, Base, engine
from worker.scorer import score_event, load_scoring_config
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact

def run_test():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    config = load_scoring_config()
    config["max_profile_staleness_days"] = 5 # Set low for test
    
    entity_id = "user_stale"
    
    # 1. Create a profile ending on Jan 1st
    profile_data = ProfileArtifact(
        entity_id=entity_id,
        entity_type="human",
        profile_version="v1",
        created_at=datetime(2026, 1, 1),
        data_window_start=datetime(2025, 12, 1),
        data_window_end=datetime(2026, 1, 1),
        features={"role": "dev", "login_hours": {}, "endpoints": {}, "process_names": {}},
        embedding=None
    )
    
    # 2. Test event within staleness window (Jan 3rd < Jan 1st + 5 days)
    event_fresh = ResolvedEvent(
        event_id="e1",
        timestamp=datetime(2026, 1, 3),
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={"process_name": "explorer.exe", "endpoint_id": "server_1", "command_line": "explorer.exe"}
    )
    
    dec_fresh = score_event(db, event_fresh, profile_data, config)
    print(f"Fresh event flags: {dec_fresh.flags}")
    assert "staleness_halt" not in dec_fresh.flags
    
    # 3. Test event outside staleness window (Jan 10th > Jan 1st + 5 days)
    event_stale = ResolvedEvent(
        event_id="e2",
        timestamp=datetime(2026, 1, 10),
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={"process_name": "explorer.exe", "endpoint_id": "server_1", "command_line": "explorer.exe"}
    )
    
    dec_stale = score_event(db, event_stale, profile_data, config)
    print(f"Stale event flags: {dec_stale.flags}")
    assert "staleness_halt" in dec_stale.flags
    print(f"Stale event score: {dec_stale.score}")
    
    print("\nStaleness Circuit Breaker Test Passed!")
    db.close()

if __name__ == "__main__":
    run_test()
