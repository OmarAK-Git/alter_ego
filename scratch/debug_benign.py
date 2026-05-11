import json
from core.database import SessionLocal
from core.models import DecisionRecordModel, EvalGroundTruthModel
from sqlalchemy import select, outerjoin

db = SessionLocal()
res = db.execute(
    select(DecisionRecordModel.contributions, DecisionRecordModel.score)
    .select_from(outerjoin(DecisionRecordModel, EvalGroundTruthModel, DecisionRecordModel.event_id==EvalGroundTruthModel.event_id))
    .where(EvalGroundTruthModel.event_id==None)
    .order_by(DecisionRecordModel.score.desc())
    .limit(1)
).first()

if res:
    print(f"Total Score: {res.score}")
    for c in res.contributions:
        print(f"  {c['feature_name']}: score={c['contribution_score']:.2f}, raw={c['raw_value']:.2f}")
else:
    print("No benign decisions found.")
