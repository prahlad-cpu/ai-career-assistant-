"""Lazy CPU embedding model with a deterministic offline fallback."""

from __future__ import annotations

import hashlib
from importlib import import_module
import logging
import re
from collections.abc import Iterable, Sequence
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]+", re.IGNORECASE)
FALLBACK_DIMENSIONS = 384


class EmbeddingService(Protocol):
    """Interface shared by the semantic and deterministic embedding backends."""

    @property
    def backend_name(self) -> str:
        """Return a stable identifier for the active embedding backend."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed each supplied text into a dense numeric vector."""


class HashEmbeddingService:
    """Small deterministic local feature hashing used when the model is unavailable."""

    @property
    def backend_name(self) -> str:
        """Return the fallback backend identifier."""
        return "feature-hash-384"

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized token and word-bigram feature vectors."""
        vectors: list[list[float]] = []
        for text in texts:
            vector = np.zeros(FALLBACK_DIMENSIONS, dtype=np.float32)
            tokens = TOKEN_PATTERN.findall(text.casefold())
            features = list(tokens)
            features.extend(
                f"{left}_{right}" for left, right in zip(tokens, tokens[1:])
            )
            for feature in features:
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest, "little") % FALLBACK_DIMENSIONS
                sign = 1.0 if digest[-1] & 1 else -1.0
                vector[index] += sign
            norm = float(np.linalg.norm(vector))
            if norm:
                vector /= norm
            vectors.append(vector.tolist())
        return vectors


class FastEmbedService:
    """Lazy adapter for the CPU-only BAAI/bge-small-en-v1.5 ONNX model."""

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None

    @property
    def backend_name(self) -> str:
        """Return the model identifier used for embeddings."""
        return self.model_name

    def _get_model(self):
        if self._model is None:
            TextEmbedding = import_module("fastembed").TextEmbedding
            options = {"model_name": self.model_name}
            if self.cache_dir:
                options["cache_dir"] = self.cache_dir
            self._model = TextEmbedding(**options)
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of text using FastEmbed on CPU."""
        if not texts:
            return []
        return [np.asarray(vector, dtype=np.float32).tolist() for vector in self._get_model().embed(texts)]


class ResilientEmbeddingService:
    """Use FastEmbed when it is ready and fall back locally if it cannot load."""

    def __init__(self, primary: EmbeddingService, fallback: EmbeddingService) -> None:
        self.primary = primary
        self.fallback = fallback
        self._fallback_active = False

    @property
    def backend_name(self) -> str:
        """Return the backend that produced vectors for the latest call."""
        return self.fallback.backend_name if self._fallback_active else self.primary.backend_name

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed text and explicitly degrade if the ONNX model is unavailable."""
        if self._fallback_active:
            return self.fallback.embed_texts(texts)
        try:
            return self.primary.embed_texts(texts)
        except Exception as error:
            self._fallback_active = True
            logger.warning(
                "FastEmbed unavailable; using deterministic local embeddings (%s).",
                type(error).__name__,
            )
            return self.fallback.embed_texts(texts)


_embedding_service: ResilientEmbeddingService | None = None
_embedding_service_key: tuple[str, str | None] | None = None


def get_embedding_service(
    model_name: str = "BAAI/bge-small-en-v1.5",
    cache_dir: str | None = None,
) -> ResilientEmbeddingService:
    """Return the process-wide lazy embedding service."""
    global _embedding_service, _embedding_service_key
    service_key = (model_name, cache_dir)
    if _embedding_service is None or _embedding_service_key != service_key:
        _embedding_service = ResilientEmbeddingService(
            FastEmbedService(model_name=model_name, cache_dir=cache_dir),
            HashEmbeddingService(),
        )
        _embedding_service_key = service_key
    return _embedding_service


def mean_embedding(vectors: Iterable[Sequence[float]]) -> list[float]:
    """Average and normalize chunk vectors into one profile vector."""
    matrix = np.asarray(list(vectors), dtype=np.float32)
    if matrix.size == 0:
        return []
    result = matrix.mean(axis=0)
    norm = float(np.linalg.norm(result))
    if norm:
        result /= norm
    return result.tolist()


def cosine_similarity_matrix(
    query_vectors: Sequence[Sequence[float]],
    document_vectors: Sequence[Sequence[float]],
) -> np.ndarray:
    """Compute all query-to-document cosine similarities with NumPy."""
    queries = np.asarray(query_vectors, dtype=np.float32)
    documents = np.asarray(document_vectors, dtype=np.float32)
    if queries.ndim == 1:
        queries = queries.reshape(1, -1)
    if documents.ndim == 1:
        documents = documents.reshape(1, -1)
    if queries.shape[1] != documents.shape[1]:
        raise ValueError("Query and document embeddings have different dimensions.")
    query_norms = np.linalg.norm(queries, axis=1, keepdims=True)
    document_norms = np.linalg.norm(documents, axis=1, keepdims=True).T
    denominator = query_norms @ document_norms
    similarities = np.divide(
        queries @ documents.T,
        denominator,
        out=np.zeros((len(queries), len(documents)), dtype=np.float32),
        where=denominator > 0,
    )
    return np.clip(similarities, -1.0, 1.0)
