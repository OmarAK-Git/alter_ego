import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from core.database import SessionLocal, Base, engine
from core.models import ResolvedEventModel, ProfileArtifactModel
from worker.scorer import score_event, load_scoring_config
from core.schemas.events import ResolvedEvent
from worker import scorer

def setup_test_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return SessionLocal()

def create_profiles(db, role, cohort_size=15):
    scorer._COHORT_MEMBERS_CACHE = {}
    scorer._NOVELTY_FRACTION_CACHE = {}
    
    # Typical profile data
    features = {
        "role": role,
        "login_hours": {str(h): 100 for h in range(9, 18)}, # 9 AM to 5 PM
        "geolocations": {"US": 1000},
        "endpoints": {"EP_BASE": 100},
        "process_names": {"explorer.exe": 1000, "chrome.exe": 500},
        "cohort_data": {
            "primary": {
                role: {
                    "login_hours": {str(h): 1000 for h in range(9, 18)},
                    "geolocations": {"US": 10000},
                    "endpoints": {"EP_BASE": 1000},
                    "process_names": {"explorer.exe": 10000}
                }
            }
        }
    }
    
    entity_ids = [f"user_{role}_{i}" for i in range(cohort_size)]
    for eid in entity_ids:
        # Give each entity a unique primary endpoint
        ent_features = features.copy()
        ent_features["endpoints"] = {f"EP_{eid}": 100}
        
        profile = ProfileArtifactModel(
            profile_version=f"v1_{eid}",
            entity_id=eid,
            entity_type="human",
            data_window_start=datetime.utcnow() - timedelta(days=30),
            data_window_end=datetime.utcnow(),
            promoted_at=datetime.utcnow(),
            features=ent_features
        )
        db.add(profile)
    db.commit()
    return entity_ids

def add_event(db, entity_id, process_name="mimikatz.exe", geo="CN", hour=0, endpoint=None):
    ts = datetime(2026, 1, 12, hour, 0) # Fixed date, variable hour
    if endpoint is None:
        endpoint = f"EP_{entity_id}"
        
    event = ResolvedEventModel(
        event_id=str(uuid.uuid4()),
        timestamp=ts,
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        event_data={
            "process_name": process_name, 
            "endpoint_id": endpoint, 
            "geolocation": geo,
            "command_line": f"{process_name} --attack"
        }
    )
    db.add(event)
    db.commit()
    return event

def run_sweep():
    db = setup_test_db()
    config = load_scoring_config()
    config["anomaly_threshold"] = 45.0 # Keep user threshold
    
    role = "Finance"
    cohort_size = 15
    entity_ids = create_profiles(db, role, cohort_size)
    
    results = []
    
    target_counts = [1, 2, 3, 4, 5, 8, 15]
    
    for count in target_counts:
        # Clear previous events
        db.query(ResolvedEventModel).delete()
        db.commit()
        scorer._NOVELTY_FRACTION_CACHE = {}
        
        # Inject attack for N entities
        attackers = entity_ids[:count]
        for aid in attackers:
            add_event(db, aid)
            
        # Score the first attacker
        target_id = attackers[0]
        p_db = db.execute(select(ProfileArtifactModel).where(ProfileArtifactModel.entity_id == target_id)).scalar()
        from core.schemas.profiles import ProfileArtifact
        p = ProfileArtifact(**{c.name: getattr(p_db, c.name) for c in p_db.__table__.columns})
        
        # We need the actual event record to score
        e_db = db.execute(select(ResolvedEventModel).where(ResolvedEventModel.entity_id == target_id)).scalar()
        re = ResolvedEvent(
            event_id=e_db.event_id, timestamp=e_db.timestamp, event_type=e_db.event_type,
            raw_entity_id=e_db.raw_entity_id, entity_id=e_db.entity_id,
            entity_type=e_db.entity_type, resolution_confidence=e_db.resolution_confidence,
            event_data=e_db.event_data
        )
        
        res = score_event(db, re, p, config)
        
        gate_fired = any("novelty_suppressed" in f for f in res.flags)
        results.append({
            "count": count,
            "fraction": count/cohort_size,
            "gate_fired": gate_fired,
            "alert": res.is_anomaly,
            "score": res.score,
            "flags": res.flags
        })

    print("| Count | Fraction | Gate Fired | Alert | Score | Flags |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in results:
        print(f"| {r['count']}/15 | {r['fraction']:.2%} | {r['gate_fired']} | {r['alert']} | {r['score']:.2f} | {r['flags']} |")

    # Sensitivity Check
    print("\n--- Sensitivity Check (Count=3) ---")
    scorer._NOVELTY_FRACTION_CACHE = {}
    db.query(ResolvedEventModel).delete()
    db.commit()
    
    # 3 attackers
    attackers = entity_ids[:3]
    for aid in attackers:
        add_event(db, aid)
    
    # Re-score target with variations
    target_id = attackers[0]
    p_db = db.execute(select(ProfileArtifactModel).where(ProfileArtifactModel.entity_id == target_id)).scalar()
    p = ProfileArtifact(**{c.name: getattr(p_db, c.name) for c in p_db.__table__.columns})

    def score_var(msg, hour=0, geo="CN", proc="mimikatz.exe"):
        e_var = add_event(db, target_id, process_name=proc, geo=geo, hour=hour)
        re_var = ResolvedEvent(
            event_id=e_var.event_id, timestamp=e_var.timestamp, event_type=e_var.event_type,
            raw_entity_id=e_var.raw_entity_id, entity_id=e_var.entity_id,
            entity_type=e_var.entity_type, resolution_confidence=e_var.resolution_confidence,
            event_data=e_var.event_data
        )
        res_var = score_event(db, re_var, p, config)
        print(f"{msg}: Score={res_var.score:.2f}, Alert={res_var.is_anomaly}")

    score_var("Baseline Attack (Rare Hour, Rare Geo, Rare Proc)")
    score_var("Typical Hour (12 PM)", hour=12)
    score_var("Typical Geo (US)", geo="US")
    score_var("Typical Hour + Typical Geo", hour=12, geo="US")
    score_var("Typical Proc (chrome.exe)", proc="chrome.exe")

if __name__ == "__main__":
    run_sweep()
