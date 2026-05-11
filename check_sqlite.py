from datetime import datetime, timedelta
from sqlalchemy import create_engine, select, and_, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

class TestModel(Base):
    __tablename__ = "test"
    id = Column(String, primary_key=True)
    ts = Column(DateTime)

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

t0 = datetime(2026, 1, 1, 0, 0, 0)
t1 = t0 + timedelta(days=1)

db.add(TestModel(id="1", ts=t0))
db.add(TestModel(id="2", ts=t1))
db.commit()

stmt = select(TestModel).where(TestModel.ts <= t0)
res = db.execute(stmt).scalars().all()
print(f"Query at {t0}: found {len(res)} items")
for r in res:
    print(f"  Item {r.id} ts={r.ts}")

stmt2 = select(TestModel).where(TestModel.ts <= t1)
res2 = db.execute(stmt2).scalars().all()
print(f"Query at {t1}: found {len(res2)} items")
