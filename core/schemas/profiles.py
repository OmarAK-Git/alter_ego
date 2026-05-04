from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

class ProfileArtifact(BaseModel):
    entity_id: str
    entity_type: str
    profile_version: str
    created_at: datetime
    data_window_start: datetime
    data_window_end: datetime
    is_shadow: bool = False
    features: Dict[str, Any]
    embedding: Optional[List[float]] = None
    embedding_model_id: str = "nomic-embed-text"
    embedding_model_version: str = "1.0"
    embedding_dimensionality: int = 768
