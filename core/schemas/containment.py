from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ContainmentQueue(BaseModel):
    queue_id: Optional[int] = None
    decision_id: str
    entity_id: str
    action: str
    status: str = "pending"
    queued_at: Optional[datetime] = None
