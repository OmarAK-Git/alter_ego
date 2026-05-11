import hashlib
import json
from pydantic import BaseModel, ConfigDict
from typing import Dict, Optional
from datetime import datetime

class FeatureConfig(BaseModel):
    weight: float

class CohortConfig(BaseModel):
    min_events_for_entity_baseline: int
    min_entities_for_cohort: int

class ScoringConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    version: str
    anomaly_threshold: float
    confidence_floor: float
    drift_weight: float
    features: Dict[str, FeatureConfig]
    cohort_minimums: CohortConfig
    suppressed_decision_aging_days: int
    replay_window_limits_days: int

    def compute_hash(self) -> str:
        """Compute a deterministic SHA-256 hash of the config data."""
        # Use sort_keys to ensure determinism
        config_json = self.model_dump_json()
        return hashlib.sha256(config_json.encode()).hexdigest()

class ScoringConfigRecord(BaseModel):
    version: str
    config_hash: str
    previous_config_hash: Optional[str]
    author: str
    timestamp: datetime
    change_reason: str
    config: ScoringConfig
