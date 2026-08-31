"""
Embedding service using sentence-transformers.

Downloads the model on first use (~80 MB for all-MiniLM-L6-v2).
Uses a module-level singleton to avoid reloading the model on every request.

IMPORTANT: model.encode() is a heavy synchronous CPU operation. Always call
`await embedder.async_embed(texts)` from async contexts so it runs in a
thread-pool executor instead of blocking the asyncio event loop.
"""

import asyncio
import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder:
    """
    Wraps a sentence-transformers model to produce fixed-size text embeddings.

    Usage:
        embedder = Embedder()
        vectors = embedder.embed(["hello world", "another sentence"])
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: "SentenceTransformer | None" = None

    def _load(self) -> "SentenceTransformer":
        if self._model is None:
            logger.info("Loading embedding model '%s'…", self.model_name)
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded (dim=%d).", self._model.get_embedding_dimension())
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings **synchronously**.

        ⚠️  Do NOT call this directly from an `async` function — it will block
        the asyncio event loop and freeze the server. Use `async_embed` instead.
        """
        if not texts:
            return []

        model = self._load()
        vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return vectors.tolist()

    async def async_embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings **without blocking the asyncio event loop**.

        Runs the CPU-heavy `model.encode()` call in the default thread-pool
        executor so the event loop remains free to handle other requests.
        """
        if not texts:
            return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed, texts)

    def embed_one(self, text: str) -> list[float]:
        """Convenience wrapper to embed a single string (sync, use for warmup only)."""
        return self.embed([text])[0]

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._load().get_embedding_dimension()


@lru_cache(maxsize=1)
def get_embedder(model_name: str = "all-MiniLM-L6-v2") -> Embedder:
    """
    Return a cached Embedder singleton.
    FastAPI dependency-injectable via `Depends(get_embedder)`.
    """
    return Embedder(model_name)
