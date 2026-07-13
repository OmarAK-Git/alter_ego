from datetime import datetime
from core.schemas.events import Event, AuthEventData, ProcessEventData

def test_auth_event_schema_validation():
    data = AuthEventData(
        action="login",
        ip_address="192.168.1.1",
        endpoint_id="ep_1"
    )
    event = Event(
        event_id="test_id",
        timestamp=datetime.utcnow(),
        event_type="auth",
        raw_entity_id="user_1",
        event_data=data
    )
    assert event.event_type == "auth"
    assert event.event_data.ip_address == "192.168.1.1"

def test_process_event_schema_validation():
    data = ProcessEventData(
        process_name="cmd.exe",
        command_line="cmd.exe /c dir",
        endpoint_id="ep_1"
    )
    event = Event(
        event_id="test_process_id",
        timestamp=datetime.utcnow(),
        event_type="process",
        raw_entity_id="svc_1",
        event_data=data
    )
    assert event.event_type == "process"
    assert event.event_data.process_name == "cmd.exe"
