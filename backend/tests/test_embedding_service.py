"""Unit tests for local embedding generation."""

import numpy as np
import pytest

from app.services.embedding_service import (
    EMBEDDING_DIMENSION,
    embed_text,
    embed_texts,
)


def test_embed_text_shape_and_normalization() -> None:
    vec = embed_text("Secure Multi-Modal RAG architecture")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (EMBEDDING_DIMENSION,)
    assert vec.dtype == np.float32

    # Verify L2 norm is 1.0 (normalized)
    norm = float(np.linalg.norm(vec))
    assert pytest.approx(norm, rel=1e-3) == 1.0


def test_embed_texts_batch() -> None:
    chunks = [
        "First document paragraph regarding student policies.",
        "Second document paragraph describing administrative budgets.",
        "Third paragraph on cybersecurity access rules.",
    ]
    vectors = embed_texts(chunks)
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (3, EMBEDDING_DIMENSION)
    assert vectors.dtype == np.float32

    for row in vectors:
        assert pytest.approx(float(np.linalg.norm(row)), rel=1e-3) == 1.0


def test_embed_texts_empty() -> None:
    empty = embed_texts([])
    assert empty.shape == (0, EMBEDDING_DIMENSION)
    assert empty.dtype == np.float32


def test_semantic_similarity() -> None:
    sentence_a = "Student attendance policy requires 85% attendance."
    sentence_b = "Students must attend at least 85 percent of all classes."
    unrelated = "Quantum thermodynamics studies microscopic fluctuations."

    vec_a = embed_text(sentence_a)
    vec_b = embed_text(sentence_b)
    vec_u = embed_text(unrelated)

    # Dot product of unit-normalized vectors equals cosine similarity
    sim_similar = float(np.dot(vec_a, vec_b))
    sim_unrelated = float(np.dot(vec_a, vec_u))

    assert sim_similar > 0.65
    assert sim_similar > (sim_unrelated + 0.4)
