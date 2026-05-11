import os
import sys
sys.path.append(os.getcwd())
DB_PATH = "alter_ego_calibrate_v14.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

import json
import uuid
import logging
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import select, func
from core.database import SessionLocal, Base, engine
from core.models import ResolvedEventModel, DecisionRecordModel, ProfileArtifactModel, EventModel, EvalGroundTruthModel
from batch.synthetic.generator import EventGenerator
from worker.resolver import process_unresolved_events
from worker.scorer import process_unscored_events
from batch.profile_builder.builder import build_profiles
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def ingest_objects(events, labels, db):
    for e in events:
        db_event = EventModel(
            event_id=e.event_id,
            timestamp=e.timestamp,
            event_type=e.event_type,
            raw_entity_id=e.raw_entity_id,
            simulation_partition=e.simulation_partition,
            event_data=e.event_data.model_dump(mode='json') if hasattr(e.event_data, 'model_dump') else e.event_data
        )
        db.merge(db_event)
    for l in labels:
        db_label = EvalGroundTruthModel(
            event_id=l["event_id"],
            is_malicious=l["is_malicious"],
            scenario=l["scenario"]
        )
        db.merge(db_label)
    db.commit()

def run_simulation(generator_func, name, config_overrides=None):
    logger.info(f"--- Starting {name} ---")
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except PermissionError:
            logger.warning(f"Could not remove {DB_PATH}, skipping...")
            
    Base.metadata.create_all(engine)
    db = SessionLocal()
    
    gen = EventGenerator(seed=42)
    start_date = datetime(2026, 1, 1)
    
    # 1. Warm-up (14 days of benign for better profiles)
    logger.info(f"[{name}] Generating warm-up data (14 days)...")
    events, labels = gen.generate_baseline(start_date, start_date + timedelta(days=14))
    ingest_objects(events, labels, db)
    process_unresolved_events(db)
    build_profiles(db, as_of=start_date + timedelta(days=14))
    
    # 2. Simulation (14 days)
    logger.info(f"[{name}] Running simulation (14 days)...")
    sim_start = start_date + timedelta(days=14)
    
    for day in range(15):
        current_date = sim_start + timedelta(days=day)
        day_events, day_labels = gen.generate_baseline(current_date, current_date + timedelta(days=1))
        if generator_func:
            day_events, day_labels = generator_func(gen, day_events, day_labels, current_date)
        ingest_objects(day_events, day_labels, db)
        
        process_unresolved_events(db)
        process_unscored_events(db)
        
        # Build profiles every 3 days instead of daily to increase drift signal
        if day % 3 == 0:
            build_profiles(db, as_of=current_date.replace(hour=23, minute=59))
        
    # Analysis
    results = analyze_results(db, name)
    db.close()
    engine.dispose()
    return results

def analyze_results(db, name):
    logger.info(f"[{name}] Simulation complete. Analyzing results...")
    
    event_alerts = db.query(DecisionRecordModel).filter(
        DecisionRecordModel.is_anomaly == True,
        DecisionRecordModel.event_id != "PROFILE_BUILD"
    ).all()
    
    drift_alerts = db.query(DecisionRecordModel).filter(
        func.json_extract(DecisionRecordModel.flags, '$.drift_alert') == True
    ).all()
    
    malicious_event_ids = [r.event_id for r in db.query(EvalGroundTruthModel).filter(EvalGroundTruthModel.is_malicious == True).all()]
    
    recall_event = 0
    if malicious_event_ids:
        caught_ids = set([a.event_id for a in event_alerts])
        recall_event = len([eid for eid in malicious_event_ids if eid in caught_ids]) / len(malicious_event_ids)
        
    attackers_stmt = select(ResolvedEventModel.entity_id).join(EvalGroundTruthModel, ResolvedEventModel.event_id == EvalGroundTruthModel.event_id).where(EvalGroundTruthModel.is_malicious == True).distinct()
    attackers = set(db.execute(attackers_stmt).scalars().all())
    
    drift_caught_attackers = set([a.entity_id for a in drift_alerts if a.entity_id in attackers])
    
    scores = [d.score for d in db.query(DecisionRecordModel).filter(DecisionRecordModel.event_id != "PROFILE_BUILD").all()]
    max_score = max(scores) if scores else 0.0
    
    all_drifts = [p.features.get("cumulative_drift", 0.0) for p in db.query(ProfileArtifactModel).all()]
    all_drifts = [float(d) for d in all_drifts if d is not None]
    
    latency_days = None
    if attackers and malicious_event_ids:
        alert_times = []
        for a in event_alerts:
            if a.entity_id in attackers:
                evt = db.query(ResolvedEventModel).filter(ResolvedEventModel.event_id == a.event_id).first()
                if evt: alert_times.append(evt.timestamp)
        for a in drift_alerts:
            if a.entity_id in attackers:
                prof = db.query(ProfileArtifactModel).filter(ProfileArtifactModel.profile_version == a.profile_version).first()
                if prof: alert_times.append(prof.data_window_end)
        
        if alert_times:
            first_malicious_ts = db.query(func.min(ResolvedEventModel.timestamp)).filter(ResolvedEventModel.event_id.in_(malicious_event_ids)).scalar()
            latency_days = (min(alert_times) - first_malicious_ts).days
            
    res = {
        "name": name,
        "max_score": max_score,
        "event_alerts": len(event_alerts),
        "drift_alerts": len(drift_alerts),
        "recall": recall_event,
        "latency_days": latency_days,
        "drift_stats": {
            "count_gt_1": len([d for d in all_drifts if d > 1.0]),
            "mean": np.mean(all_drifts) if all_drifts else 0,
            "p95": np.percentile(all_drifts, 95) if all_drifts else 0,
            "max": max(all_drifts) if all_drifts else 0
        }
    }
    logger.info(f"Results for {name}: {res}")
    return res

def scenario_2_gen(gen, events, labels, ts):
    return gen.inject_scenario_2_slow_roll(events, labels, ts)

def scenario_3_subtle_gen(gen, events, labels, ts):
    # Attacker blends into 2 typical dimensions: Hour and Endpoint
    entities = [e for e in gen.entities.values() if e.role == "Finance"][:3]
    for e in entities:
        event_id = str(uuid.uuid4())
        from core.schemas.events import Event, ProcessEventData
        events.append(Event(
            event_id=event_id,
            timestamp=ts.replace(hour=9, minute=0), # Typical hour (9 AM)
            event_type="process",
            raw_entity_id=e.entity_id,
            simulation_partition="eval_scenario_3",
            event_data=ProcessEventData(
                process_name="mimikatz.exe", # Novel
                command_line="mimikatz.exe --attack", # Novel
                endpoint_id=e.primary_endpoint # Typical endpoint
            )
        ))
        labels.append({"event_id": event_id, "is_malicious": True, "scenario": "scenario_3_subtle"})
    return events, labels

def scenario_1_gen(gen, events, labels, ts):
    return gen.inject_scenario_1_sharp_misuse(events, labels, ts)

def scenario_4_gen(gen, events, labels, ts):
    return gen.inject_scenario_4_service_abuse(events, labels, ts)

def correlated_benign_gen(gen, events, labels, ts):
    # Tooling rollout: multiple users in Engineer cohort start using a new process
    if ts.hour == 10: # Rollout starts at 10 AM
        return gen.inject_tooling_rollout(events, ts, "Engineer", "new_sec_agent.exe"), labels
    return events, labels

if __name__ == "__main__":
    all_results = []
    
    # 1. Benign-Only (Sanity Check)
    all_results.append(run_simulation(None, "BENIGN-ONLY"))
    
    # 2. Correlated Benign
    all_results.append(run_simulation(correlated_benign_gen, "CORRELATED-BENIGN"))
    
    # 3. Scenario 1 (Sharp Misuse)
    all_results.append(run_simulation(scenario_1_gen, "SCENARIO 1"))
    
    # 4. Scenario 2 (Slow Roll)
    all_results.append(run_simulation(scenario_2_gen, "SCENARIO 2"))
    
    # 5. Scenario 3 (Coordinated Subtle)
    all_results.append(run_simulation(scenario_3_subtle_gen, "SCENARIO 3"))
    
    # 6. Scenario 4 (Service Abuse)
    all_results.append(run_simulation(scenario_4_gen, "SCENARIO 4"))
    
    print("\n--- FINAL SUMMARY ---")
    print(json.dumps(all_results, indent=2))
