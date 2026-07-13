from core.database import SessionLocal
from worker.config_store import ConfigStore
from core.schemas.config import ScoringConfig
import yaml
from pathlib import Path

def persist_calibrated_config():
    db = SessionLocal()
    store = ConfigStore(db)
    
    config_path = Path("config/scoring_config.yaml")
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)
    
    config = ScoringConfig(**config_data)
    
    store.save_config(
        config, 
        author="antigravity_ai", 
        change_reason="Phase 2 Calibration v2.1: Resolved service account periodicity FPs and novelty recall gaps."
    )
    print(f"Persisted calibrated config version {config.version} to DB.")
    db.close()

if __name__ == "__main__":
    persist_calibrated_config()
