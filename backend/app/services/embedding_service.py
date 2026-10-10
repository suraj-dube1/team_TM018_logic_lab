"""Local vector embedding generation using sentence-transformers."""

from functools import lru_cache
import logging
from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the sentence-transformers model."""
    settings = get_settings()
    logger.info("Loading embedding model '%s'", settings.embedding_model_name)
    return SentenceTransformer(settings.embedding_model_name)


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Generate normalized embedding vectors for a batch of text strings.

    Returns:
        np.ndarray: 2D array of shape (N, 384) with dtype float32, L2-normalized.
    """
    if not texts:
        return np.empty((0, EMBEDDING_DIMENSION), dtype=np.float32)

    model = get_embedding_model()
    embeddings = model.encode(
        list(texts),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.astype(np.float32)


def embed_text(text: str) -> np.ndarray:
    """Generate a normalized embedding vector for a single text string.

    Returns:
        np.ndarray: 1D array of shape (384,) with dtype float32, L2-normalized.
    """
    batch_embeddings = embed_texts([text])
    return batch_embeddings[0]
