from core.database import engine, Base
from core.models import *

print("Creating tables...")
Base.metadata.create_all(engine)
print("Tables created.")

from sqlalchemy import inspect
inspector = inspect(engine)
print(f"Tables in DB: {inspector.get_table_names()}")
if "decisions" in inspector.get_table_names():
    cols = [c["name"] for c in inspector.get_columns("decisions")]
    print(f"Columns in 'decisions': {cols}")
