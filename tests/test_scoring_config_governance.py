import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pydantic import ValidationError

from core.database import Base
from core.schemas.config import ScoringConfig, FeatureConfig, CohortConfig
from worker.config_store import ConfigStore

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_scoring_config_is_frozen():
    config = ScoringConfig(
        version="1.0",
        anomaly_threshold=75.0,
        confidence_floor=0.6,
        drift_weight=1.0,
        features={"f1": FeatureConfig(weight=1.0)},
        cohort_minimums=CohortConfig(min_events_for_entity_baseline=10, min_entities_for_cohort=5),
        suppressed_decision_aging_days=7,
        replay_window_limits_days=30
    )
    with pytest.raises(ValidationError):
        config.anomaly_threshold = 80.0

def test_scoring_config_governance_chain(db_session):
    store = ConfigStore(db_session)
    
    config1 = ScoringConfig(
        version="1.0",
        anomaly_threshold=75.0,
        confidence_floor=0.6,
        drift_weight=1.0,
        features={"f1": FeatureConfig(weight=1.0)},
        cohort_minimums=CohortConfig(min_events_for_entity_baseline=10, min_entities_for_cohort=5),
        suppressed_decision_aging_days=7,
        replay_window_limits_days=30
    )
    
    # Save first config
    record1 = store.save_config(config1, author="omar", change_reason="initial")
    assert record1.previous_config_hash is None
    assert record1.config_hash == config1.compute_hash()
    
    # Save second config
    config2 = ScoringConfig(
        version="1.1",
        anomaly_threshold=80.0, # changed
        confidence_floor=0.6,
        drift_weight=1.0,
        features={"f1": FeatureConfig(weight=1.0)},
        cohort_minimums=CohortConfig(min_events_for_entity_baseline=10, min_entities_for_cohort=5),
        suppressed_decision_aging_days=7,
        replay_window_limits_days=30
    )
    
    record2 = store.save_config(config2, author="omar", change_reason="tightening threshold")
    assert record2.previous_config_hash == record1.config_hash
    assert record2.config_hash == config2.compute_hash()
    
    # Verify latest
    latest = store.get_latest_config()
    assert latest.version == "1.1"
    assert latest.config.anomaly_threshold == 80.0
