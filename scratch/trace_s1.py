from core.database import SessionLocal
from core.models import DecisionRecordModel, EvalGroundTruthModel
from sqlalchemy import select

db = SessionLocal()
res = db.execute(
    select(DecisionRecordModel.contributions, DecisionRecordModel.score, DecisionRecordModel.flags)
    .join(EvalGroundTruthModel, DecisionRecordModel.event_id == EvalGroundTruthModel.event_id)
    .where(EvalGroundTruthModel.scenario == 'scenario_1_sharp_misuse')
).first()

if res:
    print(f"Total Score: {res.score}")
    print(f"Flags: {res.flags}")
    for c in res.contributions:
        print(f"  {c['feature_name']}: raw={c['raw_value']:.2f}, score={c['contribution_score']:.2f}")
else:
    print("No results found.")
