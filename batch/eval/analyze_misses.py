from core.database import SessionLocal
from core.models import DecisionRecordModel, EvalGroundTruthModel, ProfileArtifactModel
from sqlalchemy import select

def analyze():
    db = SessionLocal()
    
    # Missed malicious events
    stmt = select(EvalGroundTruthModel).where(EvalGroundTruthModel.is_malicious == True)
    malicious = db.execute(stmt).scalars().all()
    
    print("--- Analysis of Missed Malicious Events ---")
    for m in malicious:
        d = db.query(DecisionRecordModel).filter(DecisionRecordModel.event_id == m.event_id).first()
        score = d.score if d else "N/A"
        print(f"Scenario: {m.scenario} | Event: {m.event_id} | Score: {score}")
        if d:
             print(f"  Contributions: {d.contributions}")
             p = db.query(ProfileArtifactModel).filter(ProfileArtifactModel.profile_version == d.profile_version).first()
             if p:
                 print(f"  Profile Version: {p.profile_version}")
                 # print(f"  Profile Features: {p.features}")
             else:
                 print("  Profile not found!")

    # False Positives
    print("\n--- Analysis of False Positives (Top 5 by Score) ---")
    stmt = select(DecisionRecordModel).outerjoin(
        EvalGroundTruthModel, DecisionRecordModel.event_id == EvalGroundTruthModel.event_id
    ).where(
        DecisionRecordModel.is_anomaly == True,
        (EvalGroundTruthModel.is_malicious == False) | (EvalGroundTruthModel.event_id == None)
    ).order_by(DecisionRecordModel.score.desc()).limit(5)
    
    fps = db.execute(stmt).scalars().all()
    for fp in fps:
        print(f"Event: {fp.event_id} | Score: {fp.score} | Entity: {fp.entity_id}")
        print(f"  Contributions: {fp.contributions}")

if __name__ == "__main__":
    analyze()
