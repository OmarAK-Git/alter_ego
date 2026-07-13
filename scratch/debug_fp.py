from core.database import SessionLocal
from core.models import DecisionRecordModel, EvalGroundTruthModel
from sqlalchemy import select, outerjoin

db = SessionLocal()
# Use the correct way to reference the right table in outer join
res = db.execute(
    select(DecisionRecordModel.contributions, DecisionRecordModel.score, DecisionRecordModel.confidence)
    .select_from(outerjoin(DecisionRecordModel, EvalGroundTruthModel, DecisionRecordModel.event_id==EvalGroundTruthModel.event_id))
    .where(EvalGroundTruthModel.event_id == None, DecisionRecordModel.score >= 30.0)
    .limit(1)
).first()

if res:
    print(f"Total Score: {res.score}, Confidence: {res.confidence}")
    for c in res.contributions:
        print(f"  {c['feature_name']}: score={c['contribution_score']:.2f}, raw={c['raw_value']:.2f}")
else:
    print("No FPs found at threshold 30.")
