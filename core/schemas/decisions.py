from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class FeatureContribution(BaseModel):
    contribution_id: str
    feature_name: str
    raw_value: float
    contribution_score: float
    confidence_weight: float

class DecisionRecord(BaseModel):
    decision_id: str
    event_id: str
    entity_id: str
    timestamp: datetime
    score: float
    confidence: float
    profile_version: str
    scoring_config_version: str
    contributions: List[FeatureContribution]
    is_anomaly: bool
    cohort_used: str
    cohort_unsupported: bool
    flags: List[str]

from enum import Enum

class ConfidenceLabel(str, Enum):
    very_low = "very_low"
    low = "low"
    moderate = "moderate"
    high = "high"
    very_high = "very_high"

class ClaimObject(BaseModel):
    contribution_id: str           # references decision_record.feature_contributions[i].contribution_id
    claim_text: str                # natural-language claim, length-capped
    evidence_binding: list[str]    # contribution_ids this claim is grounded in (must resolve)
    confidence_label: ConfidenceLabel  # SET BY EXPLAINER SERVICE, NOT BY LLM

class CounterfactualEntry(BaseModel):
    contribution_id: str
    counterfactual_text: str       # "if logon_hour had been within typical range, score would have been X lower"
    score_delta: float             # quantitative impact

class ValidationStatus(str, Enum):
    passed = "passed"
    template_fallback = "template_fallback"
    rejected = "rejected"

class ExplanationRecord(BaseModel):
    decision_id: str
    summary_text: str
    claim_objects: list[ClaimObject]
    counterfactuals: list[CounterfactualEntry]
    validation_status: ValidationStatus
    validation_notes: Optional[str] = None
    llm_model_id: str              # pinned, non-alias
    prompt_hash: str               # SHA-256 of the exact prompt sent
    response_hash: str             # SHA-256 of the exact response received
    created_at: datetime
