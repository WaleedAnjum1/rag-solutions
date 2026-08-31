"""
In-memory document chunk cache + Ollama KV-state cache.

DocumentChunkCache:
  After a document is ingested, all SourceChunk objects are stored in RAM.
  On subsequent queries the RAGChain checks here first, skipping ChromaDB.

OllamaContextCache:
  Stores Ollama's 'context' token array returned after the first time a
  document is processed. Passing this array back in later requests lets
  Ollama skip re-reading the document entirely (the KV states are already
  in GPU memory). This is what turns 40-60s follow-up answers into 2-5s.

Cache lifecycle:
  - Populated: immediately after VectorStore.add_document()
  - Evicted:   when VectorStore.delete_document() is called
  - Max size:  MAX_CACHED_DOCS most-recently-used documents (LRU eviction)

This cache is per-process. With a single uvicorn worker (the default dev
setup) it works perfectly.
"""

import logging
import math
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)

MAX_CACHED_DOCS = 50


# ---------------------------------------------------------------------------
# DocumentChunkCache
# ---------------------------------------------------------------------------

class DocumentChunkCache:
    """
    LRU cache that stores all SourceChunk objects for recently-ingested docs.

    Each entry is keyed by (namespace, doc_id) and holds a list of
    (embedding_vector, SourceChunk) tuples so we can do fast in-process
    cosine similarity search.
    """

    def __init__(self, max_size: int = MAX_CACHED_DOCS) -> None:
        self._max_size = max_size
        self._store: OrderedDict[tuple[str, str], list[tuple[list[float], object]]] = OrderedDict()

    def put(
        self,
        namespace: str,
        doc_id: str,
        entries: list[tuple[list[float], object]],
    ) -> None:
        """Store (embedding, chunk) pairs for a document."""
        key = (namespace, doc_id)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = entries

        while len(self._store) > self._max_size:
            evicted_key, _ = self._store.popitem(last=False)
            logger.debug("Cache evicted doc_id=%s ns=%s", evicted_key[1], evicted_key[0])

        logger.info(
            "Chunk cache warmed: ns=%s doc_id=%s (%d chunks)",
            namespace, doc_id, len(entries),
        )

    def search(
        self,
        namespace: str,
        doc_id: Optional[str],
        query_vector: list[float],
        top_k: int,
    ) -> Optional[list]:
        if doc_id:
            key = (namespace, doc_id)
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            candidates = self._store[key]
        else:
            candidates = []
            for (ns, _did), entries in self._store.items():
                if ns == namespace:
                    candidates.extend(entries)
            if not candidates:
                return None

        q_norm = _l2(query_vector)
        scored = [(_cosine(query_vector, vec, q_norm), chunk) for vec, chunk in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for (_, chunk) in scored[:top_k]]

    def get_all_chunks(self, namespace: str, doc_id: str) -> Optional[list]:
        """Return all chunks for a document sorted by chunk_index."""
        key = (namespace, doc_id)
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        chunks = [chunk for (_, chunk) in self._store[key]]
        chunks.sort(key=lambda c: c.chunk_index)
        return chunks

    def invalidate(self, namespace: str, doc_id: str) -> None:
        key = (namespace, doc_id)
        removed = self._store.pop(key, None)
        if removed is not None:
            logger.info("Chunk cache invalidated: ns=%s doc_id=%s", namespace, doc_id)

    def invalidate_doc(self, doc_id: str) -> int:
        """Drop a document from every namespace that holds it. Returns entries removed."""
        keys = [k for k in self._store if k[1] == doc_id]
        for key in keys:
            del self._store[key]
        if keys:
            logger.info("Chunk cache invalidated doc_id=%s from %d namespace(s)", doc_id, len(keys))
        return len(keys)

    def invalidate_namespace(self, namespace: str) -> int:
        """Drop every document belonging to a namespace. Returns entries removed."""
        keys = [k for k in self._store if k[0] == namespace]
        for key in keys:
            del self._store[key]
        if keys:
            logger.info("Chunk cache invalidated ns=%s (%d document(s))", namespace, len(keys))
        return len(keys)

    def has(self, namespace: str, doc_id: str) -> bool:
        return (namespace, doc_id) in self._store

    def size(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# OllamaContextCache — the core of fast follow-up queries
# ---------------------------------------------------------------------------

class OllamaContextCache:
    """
    Stores Ollama's KV-cache token array per (namespace, doc_id).

    How it works:
      1. During ingestion a background task sends [system_prompt + full_document]
         to Ollama with num_predict=1.  Ollama processes every document token
         and returns a 'context' list of ints representing the KV state.
      2. We store that list here.
      3. On every follow-up query we send ONLY the question (a few tokens)
         plus the cached 'context' array.  Ollama's KV cache is already warm
         so it skips re-reading the document and responds in 2-5 seconds.

    Important: We only cache the *document-only* context (not the answers)
    so each question starts from a clean document baseline.
    """

    def __init__(self, max_size: int = MAX_CACHED_DOCS) -> None:
        self._max_size = max_size
        self._store: OrderedDict[tuple[str, str], list[int]] = OrderedDict()

    def put(self, namespace: str, doc_id: str, context_arr: list[int]) -> None:
        """Store the Ollama KV token array for a document."""
        if not context_arr:
            return
        key = (namespace, doc_id)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = context_arr
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
        logger.info(
            "Ollama context cached: ns=%s doc_id=%s (%d tokens)",
            namespace, doc_id, len(context_arr),
        )

    def get(self, namespace: str, doc_id: str) -> Optional[list[int]]:
        """Return the cached context array, or None if not present."""
        key = (namespace, doc_id)
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def invalidate(self, namespace: str, doc_id: str) -> None:
        removed = self._store.pop((namespace, doc_id), None)
        if removed is not None:
            logger.info("Ollama context invalidated: ns=%s doc_id=%s", namespace, doc_id)

    def invalidate_doc(self, doc_id: str) -> int:
        """Drop a document's context from every namespace that holds it."""
        keys = [k for k in self._store if k[1] == doc_id]
        for key in keys:
            del self._store[key]
        if keys:
            logger.info("Ollama context invalidated doc_id=%s from %d namespace(s)", doc_id, len(keys))
        return len(keys)

    def invalidate_namespace(self, namespace: str) -> int:
        """Drop every cached context belonging to a namespace."""
        keys = [k for k in self._store if k[0] == namespace]
        for key in keys:
            del self._store[key]
        if keys:
            logger.info("Ollama context invalidated ns=%s (%d document(s))", namespace, len(keys))
        return len(keys)

    def has(self, namespace: str, doc_id: str) -> bool:
        return (namespace, doc_id) in self._store

    def size(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _l2(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec)) or 1e-10


def _cosine(a: list[float], b: list[float], a_norm: float) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    b_norm = _l2(b)
    return dot / (a_norm * b_norm)


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_chunk_cache: DocumentChunkCache | None = None
_ollama_ctx_cache: OllamaContextCache | None = None


def get_document_cache() -> DocumentChunkCache:
    """Return the process-wide DocumentChunkCache singleton."""
    global _chunk_cache
    if _chunk_cache is None:
        _chunk_cache = DocumentChunkCache()
    return _chunk_cache


def get_ollama_context_cache() -> OllamaContextCache:
    """Return the process-wide OllamaContextCache singleton."""
    global _ollama_ctx_cache
    if _ollama_ctx_cache is None:
        _ollama_ctx_cache = OllamaContextCache()
    return _ollama_ctx_cache
