from worker.resolver import resolve_entity

def test_resolve_entity():
    # Human
    eid, etype, conf = resolve_entity("user_123")
    assert eid == "user_123"
    assert etype == "human"
    assert conf == 1.0
    
    # Service account
    eid, etype, conf = resolve_entity("svc_456")
    assert eid == "svc_456"
    assert etype == "service_account"
    assert conf == 1.0
    
    # Unknown
    eid, etype, conf = resolve_entity("admin_789")
    assert eid == "admin_789"
    assert etype == "unknown"
    assert conf == 0.5
