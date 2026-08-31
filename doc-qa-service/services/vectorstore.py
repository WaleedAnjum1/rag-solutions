"""
ChromaDB vector store abstraction.

Each namespace maps to a separate ChromaDB collection for full tenant isolation.
Document metadata is mirrored in a lightweight JSON registry file so we can
list documents without scanning all chunks.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb

from config import settings
from models.responses import DocumentInfo, SourceChunk
from services.document_loader import TextChunk

logger = logging.getLogger(__name__)

# Path to the JSON document registry
REGISTRY_PATH = Path(settings.chroma_db_path) / "registry.json"


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {}


def _save_registry(registry: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Thin wrapper around ChromaDB that handles:
    - Namespace-scoped collections
    - Chunk add / query / delete
    - Document registry (for listing)
    """

    def __init__(self, db_path: str | None = None) -> None:
        path = db_path or settings.chroma_db_path
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=path)
        logger.info("ChromaDB initialised at '%s'", path)

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def _collection(self, namespace: str) -> chromadb.Collection:
        """Get or create a ChromaDB collection for the given namespace."""
        safe_name = "ns_" + "".join(c if c.isalnum() else "_" for c in namespace)
        return self._client.get_or_create_collection(
            name=safe_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def add_document(
        self,
        doc_id: str,
        filename: str,
        namespace: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        file_type: str,
    ) -> int:
        """
        Store all chunks + embeddings for a document.

        Returns the number of chunks stored.
        """
        if not chunks:
            raise ValueError("Cannot ingest a document with zero chunks.")

        collection = self._collection(namespace)

        ids = [f"{doc_id}_chunk_{c.chunk_index}" for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "namespace": namespace,
                "chunk_index": c.chunk_index,
                "page": c.page if c.page is not None else -1,
                "file_type": file_type,
            }
            for c in chunks
        ]

        # Insert into ChromaDB in batches to avoid max_batch_size limits (typically 5461 or 41666)
        batch_size = 5000
        for i in range(0, len(chunks), batch_size):
            collection.add(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=texts[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size]
            )

        # Update registry
        registry = _load_registry()
        registry[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "namespace": namespace,
            "chunks_count": len(chunks),
            "file_type": file_type,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_registry(registry)

        logger.info("Stored %d chunks for doc '%s' in namespace '%s'", len(chunks), doc_id, namespace)
        return len(chunks)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        namespace: str,
        top_k: int = 5,
        doc_id_filter: str | None = None,
    ) -> list[SourceChunk]:
        """
        Retrieve the top-k most relevant chunks for a query embedding.

        Returns a list of SourceChunk objects sorted by relevance (descending).
        """
        collection = self._collection(namespace)

        if collection.count() == 0:
            logger.warning("Namespace '%s' has no documents.", namespace)
            return []

        query_kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        
        if doc_id_filter:
            query_kwargs["where"] = {"doc_id": {"$eq": doc_id_filter}}

        results = collection.query(**query_kwargs)

        source_chunks: list[SourceChunk] = []
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score [0, 1]
            similarity = max(0.0, 1.0 - distance / 2.0)

            source_chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    doc_id=meta["doc_id"],
                    filename=meta["filename"],
                    text=results["documents"][0][i],
                    relevance_score=round(similarity, 4),
                    page=meta["page"] if meta.get("page", -1) != -1 else None,
                    chunk_index=meta["chunk_index"],
                )
            )

        return source_chunks

    def get_all_chunks(self, namespace: str, doc_id: str) -> list[SourceChunk]:
        """Fetch all chunks for a document without semantic search, sorted by index."""
        collection = self._collection(namespace)
        results = collection.get(
            where={"doc_id": {"$eq": doc_id}},
            include=["documents", "metadatas"],
        )
        if not results or not results.get("ids"):
            return []
            
        chunks = []
        for i, chunk_id in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    doc_id=meta["doc_id"],
                    filename=meta["filename"],
                    text=results["documents"][i],
                    relevance_score=1.0,  # Fixed relevance for static doc fetch
                    page=meta.get("page") if meta.get("page", -1) != -1 else None,
                    chunk_index=meta["chunk_index"],
                )
            )
        chunks.sort(key=lambda c: c.chunk_index)
        return chunks

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks belonging to a document from its namespace.

        Returns True if the document existed, False if not found.
        """
        registry = _load_registry()
        entry = registry.get(doc_id)
        if not entry:
            return False

        namespace = entry["namespace"]
        collection = self._collection(namespace)

        # Get all chunk IDs for this doc
        results = collection.get(where={"doc_id": doc_id}, include=[])
        chunk_ids = results["ids"]

        if chunk_ids:
            collection.delete(ids=chunk_ids)
            logger.info("Deleted %d chunks for doc '%s'", len(chunk_ids), doc_id)

        del registry[doc_id]
        _save_registry(registry)
        return True

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_documents(self, namespace: str | None = None) -> list[DocumentInfo]:
        """
        List all ingested documents, optionally filtered by namespace.
        """
        registry = _load_registry()
        docs: list[DocumentInfo] = []

        for entry in registry.values():
            if namespace and entry["namespace"] != namespace:
                continue
            docs.append(
                DocumentInfo(
                    doc_id=entry["doc_id"],
                    filename=entry["filename"],
                    namespace=entry["namespace"],
                    chunks_count=entry["chunks_count"],
                    file_type=entry["file_type"],
                    ingested_at=datetime.fromisoformat(entry["ingested_at"]),
                )
            )

        return sorted(docs, key=lambda d: d.ingested_at, reverse=True)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if ChromaDB is accessible."""
        try:
            self._client.heartbeat()
            return True
        except Exception:
            return False


def generate_doc_id() -> str:
    """Generate a unique document ID."""
    return str(uuid.uuid4())
