from pydantic import BaseModel, Field
from typing import Literal, Optional, Union
from datetime import datetime

class AuthEventData(BaseModel):
    action: str  # e.g., login, logout, failed_login
    ip_address: str
    geolocation: Optional[str] = None
    endpoint_id: str

class ProcessEventData(BaseModel):
    process_name: str
    command_line: str
    parent_process_name: Optional[str] = None
    endpoint_id: str

class Event(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: Literal["auth", "process"]
    raw_entity_id: str
    simulation_partition: bool = False
    event_data: Union[AuthEventData, ProcessEventData]

class ResolvedEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: Literal["auth", "process"]
    raw_entity_id: str
    entity_id: str
    entity_type: Literal["human", "service_account"]
    resolution_confidence: float
    simulation_partition: bool = False
    event_data: Union[AuthEventData, ProcessEventData]
