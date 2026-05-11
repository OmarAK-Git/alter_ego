import pytest
from datetime import datetime
from pydantic import ValidationError
from core.schemas.profiles import ProfileArtifact

def test_profile_artifact_is_frozen():
    p = ProfileArtifact(
        entity_id="user_1",
        entity_type="user",
        profile_version="v1",
        created_at=datetime.utcnow(),
        data_window_start=datetime.utcnow(),
        data_window_end=datetime.utcnow(),
        features={"f1": 1.0}
    )
    
    with pytest.raises(ValidationError):
        p.features = {"f1": 2.0}
    
    with pytest.raises(ValidationError):
        p.entity_id = "user_2"
