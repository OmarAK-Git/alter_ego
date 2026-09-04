import sqlite3
from pathlib import Path
from datetime import datetime
root = Path("C:/Users/oalan/alter_ego")
for db in sorted(root.glob("alter_ego_calibrate_series_i_ws_*.db")):
    c = sqlite3.connect(str(db))
    cols = [r[1] for r in c.execute("PRAGMA table_info(profiles)")]
    # try common time columns
    for col in ("as_of", "built_at", "window_end", "created_at", "profile_as_of"):
        if col in cols:
            mx = c.execute(f"SELECT MAX({col}) FROM profiles").fetchone()[0]
            n = c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            print(f"{db.name}: profiles n={n} max_{col}={mx} db_mtime={datetime.fromtimestamp(db.stat().st_mtime):%Y-%m-%d %H:%M}")
            break
    else:
        print(f"{db.name}: profile cols={cols}")
    c.close()
