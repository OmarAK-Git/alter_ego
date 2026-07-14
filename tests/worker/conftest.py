"""Shared worker test helpers."""

from core.schemas.profiles import (
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL_ID,
    DEFAULT_EMBEDDING_MODEL_VERSION,
)
from worker.vectorizer import NORMALIZER_VERSION

COMPATIBLE_EMBEDDING_PROFILE_FIELDS = {
    "embedding_model_id": DEFAULT_EMBEDDING_MODEL_ID,
    "embedding_model_version": DEFAULT_EMBEDDING_MODEL_VERSION,
    "embedding_dimensionality": DEFAULT_EMBEDDING_DIMENSIONALITY,
    "embedding_input_normalizer_version": NORMALIZER_VERSION,
}
