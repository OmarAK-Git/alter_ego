from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
import logging

from core.settings import settings

logger = logging.getLogger(__name__)

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None
    logger.warning("pgvector not found. Falling back to SQLite/JSON storage for vectors. Phase 3 semantic search may fail.")

print(f"Connecting to: {settings.database_url}")
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

if Vector:
    @compiles(Vector, "sqlite")
    def compile_vector_sqlite(type_, compiler, **kw):
        return "JSON"

    from sqlalchemy import TypeDecorator, JSON

    class SQLiteVector(TypeDecorator):
        impl = JSON
        cache_ok = True

        def process_bind_param(self, value, dialect):
            return value # List is already JSON serializable

        def process_result_value(self, value, dialect):
            return value # List is already JSON serializable

    # Override Vector for sqlite
    # (This is a bit hacky, better to use a factory, but let's try to monkeypatch or just use the decorator in models)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
