from pydantic import BaseModel
from typing import Dict

class FeatureConfig(BaseModel):
    weight: float

class CohortConfig(BaseModel):
    min_events_for_entity_baseline: int
    min_entities_for_cohort: int

class ScoringConfig(BaseModel):
    version: str
    anomaly_threshold: float
    confidence_floor: float
    drift_weight: float
    features: Dict[str, FeatureConfig]
    cohort_minimums: CohortConfig
    suppressed_decision_aging_days: int
    replay_window_limits_days: int
