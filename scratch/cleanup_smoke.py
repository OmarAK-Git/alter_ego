import sqlite3
c = sqlite3.connect('alter_ego_calibrate_v2.db')
c.execute("DELETE FROM decisions WHERE decision_id LIKE 'smoke_test_%'")
c.execute("DELETE FROM alert_workflow_state WHERE decision_id LIKE 'smoke_test_%'")
c.execute("DELETE FROM explanations WHERE decision_id LIKE 'smoke_test_%'")
c.commit()
print(f"Cleaned {c.total_changes} rows")
c.close()
