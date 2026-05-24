import sqlite3
import os
import json

def check_db():
    for f in os.listdir("."):
        if f.endswith(".db"):
            con = sqlite3.connect(f)
            cursor = con.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'")
            if cursor.fetchone():
                print(f"Database: {f}")
                cursor.execute("SELECT profile_version, length(embedding), embedding FROM profiles LIMIT 2")
                rows = cursor.fetchall()
                for row in rows:
                    p_ver, emb_len, emb_val = row
                    if emb_val:
                        try:
                            emb_list = json.loads(emb_val)
                            print(f"  profile: {p_ver}, embedding size: {len(emb_list)}")
                        except Exception:
                            print(f"  profile: {p_ver}, raw embedding length in chars: {emb_len}")
                    else:
                        print(f"  profile: {p_ver}, embedding: None")
            con.close()

if __name__ == "__main__":
    check_db()
