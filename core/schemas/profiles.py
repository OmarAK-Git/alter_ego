from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, Optional, List
from datetime import datetime

DEFAULT_EMBEDDING_MODEL_ID = "alter-ego-ngram-v1"
DEFAULT_EMBEDDING_MODEL_VERSION = "1.0"
DEFAULT_EMBEDDING_DIMENSIONALITY = 128
DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION = "1.0"


class ProfileArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str
    entity_type: str
    profile_version: str
    created_at: datetime
    data_window_start: datetime
    data_window_end: datetime
    promoted_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    is_shadow: bool = False
    features: Dict[str, Any]
    embedding: Optional[List[float]] = None
    embedding_model_id: str = DEFAULT_EMBEDDING_MODEL_ID
    embedding_model_version: str = DEFAULT_EMBEDDING_MODEL_VERSION
    embedding_dimensionality: int = DEFAULT_EMBEDDING_DIMENSIONALITY
    embedding_input_normalizer_version: str = DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION
