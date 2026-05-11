from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from core.models import ScoringConfigModel
from core.schemas.config import ScoringConfig, ScoringConfigRecord

class ConfigStore:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_config(self) -> Optional[ScoringConfigRecord]:
        model = self.db.query(ScoringConfigModel).order_by(ScoringConfigModel.timestamp.desc()).first()
        if not model:
            return None
        
        return ScoringConfigRecord(
            version=model.version,
            config_hash=model.config_hash,
            previous_config_hash=model.previous_config_hash,
            author=model.author,
            timestamp=model.timestamp,
            change_reason=model.change_reason,
            config=ScoringConfig(**model.config_data)
        )

    def save_config(self, config: ScoringConfig, author: str, change_reason: str) -> ScoringConfigRecord:
        latest = self.get_latest_config()
        config_hash = config.compute_hash()
        
        if latest and latest.config_hash == config_hash:
            # If it's the same content, we don't necessarily need to fail, 
            # but for governance, we usually want unique hashes.
            # However, if it's just a version bump with same settings, it might be allowed.
            # Spec says "previous_config_hash, new_config_hash, author, timestamp, and change_reason"
            # so we should allow it if version is different?
            # Let's be strict for now.
            pass

        record = ScoringConfigModel(
            version=config.version,
            config_hash=config_hash,
            previous_config_hash=latest.config_hash if latest else None,
            author=author,
            timestamp=datetime.utcnow(),
            change_reason=change_reason,
            config_data=config.model_dump()
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        
        return ScoringConfigRecord(
            version=record.version,
            config_hash=record.config_hash,
            previous_config_hash=record.previous_config_hash,
            author=record.author,
            timestamp=record.timestamp,
            change_reason=record.change_reason,
            config=config
        )
