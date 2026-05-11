from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
from core.models import ProfileArtifactModel
from core.schemas.profiles import ProfileArtifact

class ProfileStore:
    def __init__(self, db: Session):
        self.db = db

    def get_active_profile(self, entity_id: str, event_time: datetime) -> Optional[ProfileArtifact]:
        """
        Select the profile where promoted_at <= event_time < superseded_at and is_shadow=false.
        If superseded_at is null, it's the current active profile.
        """
        model = self.db.query(ProfileArtifactModel).filter(
            and_(
                ProfileArtifactModel.entity_id == entity_id,
                ProfileArtifactModel.is_shadow == False,
                ProfileArtifactModel.promoted_at <= event_time,
                or_(
                    ProfileArtifactModel.superseded_at > event_time,
                    ProfileArtifactModel.superseded_at == None
                )
            )
        ).first()

        if not model:
            return None

        return ProfileArtifact(
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            profile_version=model.profile_version,
            created_at=model.created_at,
            data_window_start=model.data_window_start,
            data_window_end=model.data_window_end,
            promoted_at=model.promoted_at,
            superseded_at=model.superseded_at,
            is_shadow=model.is_shadow,
            features=model.features,
            embedding=model.embedding,
            embedding_model_id=model.embedding_model_id,
            embedding_model_version=model.embedding_model_version,
            embedding_dimensionality=model.embedding_dimensionality,
            embedding_input_normalizer_version=model.embedding_input_normalizer_version
        )

    def promote_profile(self, profile_version: str, promoted_at: datetime):
        """Promote a profile and supersede the previous one for the same entity."""
        profile = self.db.query(ProfileArtifactModel).filter(ProfileArtifactModel.profile_version == profile_version).one()
        
        # Find the currently active profile (if any) and supersede it
        current_active = self.db.query(ProfileArtifactModel).filter(
            and_(
                ProfileArtifactModel.entity_id == profile.entity_id,
                ProfileArtifactModel.is_shadow == False,
                ProfileArtifactModel.promoted_at != None,
                ProfileArtifactModel.superseded_at == None
            )
        ).first()

        if current_active:
            current_active.superseded_at = promoted_at
        
        profile.promoted_at = promoted_at
        self.db.commit()
