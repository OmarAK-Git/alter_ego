import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.models import DecisionRecordModel, ProfileArtifactModel
from worker.explainer import generate_explanation, StubLLMProvider, LLMProvider

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_template_fallback_on_invalid_json(db_session):
    # Create mock Decision and Profile
    dec = DecisionRecordModel(
        decision_id="dec1",
        event_id="evt1",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=50.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="1",
        contributions=[
            {"contribution_id": "c1", "feature_name": "feat1", "contribution_score": 25.0, "confidence_weight": 0.8},
            {"contribution_id": "c2", "feature_name": "feat2", "contribution_score": 25.0, "confidence_weight": 0.8}
        ],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[]
    )
    prof = ProfileArtifactModel(
        profile_version="v1",
        entity_id="user_1",
        entity_type="human",
        created_at=datetime.utcnow(),
        data_window_start=datetime.utcnow(),
        data_window_end=datetime.utcnow(),
        features={"some": "data"}
    )
    db_session.add(dec)
    db_session.add(prof)
    db_session.commit()
    
    class BadLLM(LLMProvider):
        def generate(self, prompt, temperature=0.0):
            return "This is not JSON"
            
    record = generate_explanation("dec1", db_session, provider=BadLLM())
    assert record.validation_status.value == "template_fallback"
    assert len(record.claim_objects) == 2
    assert record.claim_objects[0].contribution_id in ["c1", "c2"]
    
def test_prohibited_content_validation(db_session):
    dec = DecisionRecordModel(
        decision_id="dec2",
        event_id="evt2",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=50.0,
        confidence=0.9,
        profile_version="v2",
        scoring_config_version="1",
        contributions=[
            {"contribution_id": "c1", "feature_name": "feat1", "contribution_score": 25.0, "confidence_weight": 0.8}
        ],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[]
    )
    prof = ProfileArtifactModel(
        profile_version="v2",
        entity_id="user_1",
        entity_type="human",
        created_at=datetime.utcnow(),
        data_window_start=datetime.utcnow(),
        data_window_end=datetime.utcnow(),
        features={}
    )
    db_session.add(dec)
    db_session.add(prof)
    db_session.commit()
    
    class EvilLLM(LLMProvider):
        def generate(self, prompt, temperature=0.0):
            import json
            return json.dumps({
                "summary_text": "This was caused by Lazarus.",
                "claim_objects": [
                    {
                        "contribution_id": "c1",
                        "claim_text": "Did something bad",
                        "evidence_binding": ["c1"]
                    }
                ]
            })
            
    record = generate_explanation("dec2", db_session, provider=EvilLLM())
    assert record.validation_status.value == "template_fallback"
    assert "Prohibited content" in record.validation_notes
