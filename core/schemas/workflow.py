from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class AlertStateEnum(str, Enum):
    new = "new"
    acknowledged = "acknowledged"
    investigating = "investigating"
    cleared = "cleared"
    auto_resolved = "auto_resolved"

class AlertWorkflowState(BaseModel):
    decision_id: str
    entity_id: str
    state: AlertStateEnum = AlertStateEnum.new
    assignee: Optional[str] = None
    clear_reason: Optional[str] = None
    updated_at: datetime

class AlertStateUpdate(BaseModel):
    state: AlertStateEnum
    assignee: Optional[str] = None
    clear_reason: Optional[str] = None

class ReplayRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    old_scoring_config_version: str
    new_scoring_config_version: str
    author: str
    change_reason: str


class ExtendHaltRequest(BaseModel):
    justification: str = Field(min_length=1)
