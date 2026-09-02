"""
ChromaDB vector store abstraction — Multi-Language Customer Support Bot.

Each tenant_id maps to a separate ChromaDB collection so one workspace's support
content is never mixed with another's. Document metadata is mirrored in a
lightweight JSON registry file so we can list documents without scanning chunks.

Extended from medical-records-qa/services/vectorstore.py:
- Namespace is `tenant_id` instead of `patient_id`
- Adds `doc_type` and `language` to chunk metadata, both filterable at query time
- Retrieval is cross-lingual by default: the embedding model shares a vector
  space across languages, so a French question matches an English FAQ. Pass
  `language_filter` only when a tenant deliberately keeps per-language content.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb

from config import settings
from models.responses import SourceChunk, SupportDocument
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


def _collection_name(tenant_id: str) -> str:
    """ChromaDB collection name for a tenant (alphanumerics only)."""
    return "tn_" + "".join(c if c.isalnum() else "_" for c in tenant_id)


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Thin wrapper around ChromaDB scoped per tenant_id (used as the namespace).

    Handles:
    - tenant-scoped collections
    - chunk add / query / delete
    - document registry (for listing)
    """

    def __init__(self, db_path: str | None = None) -> None:
        path = db_path or settings.chroma_db_path
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=path)
        logger.info("ChromaDB initialised at '%s'", path)

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def _collection(self, tenant_id: str) -> chromadb.Collection:
        """Get or create a ChromaDB collection for the given tenant_id."""
        return self._client.get_or_create_collection(
            name=_collection_name(tenant_id),
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def add_document(
        self,
        doc_id: str,
        filename: str,
        tenant_id: str,
        doc_type: str,
        language: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        file_type: str,
    ) -> int:
        """
        Store all chunks + embeddings for a support document.

        Returns the number of chunks stored.
        """
        if not chunks:
            raise ValueError("Cannot ingest a document with zero chunks.")

        collection = self._collection(tenant_id)

        ids = [f"{doc_id}_chunk_{c.chunk_index}" for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "tenant_id": tenant_id,
                "doc_type": doc_type,
                "language": language,
                "chunk_index": c.chunk_index,
                "page": c.page if c.page is not None else -1,
                "file_type": file_type,
            }
            for c in chunks
        ]

        # Insert in batches to respect ChromaDB max_batch_size limits
        batch_size = 5000
        for i in range(0, len(chunks), batch_size):
            collection.add(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=texts[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

        # Update registry
        registry = _load_registry()
        registry[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "tenant_id": tenant_id,
            "doc_type": doc_type,
            "language": language,
            "chunks_count": len(chunks),
            "file_type": file_type,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_registry(registry)

        logger.info(
            "Stored %d chunks for doc '%s' (tenant=%s, type=%s, lang=%s)",
            len(chunks), doc_id, tenant_id, doc_type, language,
        )
        return len(chunks)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        tenant_id: str,
        top_k: int = 6,
        doc_type_filter: str | None = None,
        language_filter: str | None = None,
        doc_id_filter: str | None = None,
    ) -> list[SourceChunk]:
        """
        Retrieve the top-k most relevant chunks for a query embedding.

        Args:
            query_embedding: Embedding of the customer's question.
            tenant_id:       Workspace whose collection to search.
            top_k:           Max chunks to return.
            doc_type_filter: Optional — restrict to a content category.
            language_filter: Optional — restrict to source content in one language.
            doc_id_filter:   Optional — restrict to a specific document.

        Returns:
            List of SourceChunk objects sorted by relevance (descending).
        """
        collection = self._collection(tenant_id)

        if collection.count() == 0:
            logger.warning("Tenant '%s' has no ingested support content.", tenant_id)
            return []

        conditions = []
        if doc_type_filter:
            conditions.append({"doc_type": {"$eq": doc_type_filter}})
        if language_filter:
            conditions.append({"language": {"$eq": language_filter}})
        if doc_id_filter:
            conditions.append({"doc_id": {"$eq": doc_id_filter}})

        where_filter = None
        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        query_kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        source_chunks: list[SourceChunk] = []
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            # ChromaDB cosine distance: 0 = identical → convert to [0,1] similarity
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
                    doc_type=meta.get("doc_type"),
                    language=meta.get("language"),
                )
            )

        return source_chunks

    def get_all_chunks(self, tenant_id: str, doc_id: str) -> list[SourceChunk]:
        """Fetch all chunks for a document without semantic search, sorted by index."""
        collection = self._collection(tenant_id)
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
                    doc_type=meta.get("doc_type"),
                    language=meta.get("language"),
                )
            )
        chunks.sort(key=lambda c: c.chunk_index)
        return chunks

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete all chunks belonging to a document.

        Returns True if found and deleted, False if not found.
        """
        registry = _load_registry()
        entry = registry.get(doc_id)
        if not entry:
            return False

        tenant_id = entry["tenant_id"]
        collection = self._collection(tenant_id)

        results = collection.get(where={"doc_id": doc_id}, include=[])
        chunk_ids = results["ids"]

        if chunk_ids:
            collection.delete(ids=chunk_ids)
            logger.info("Deleted %d chunks for doc '%s'", len(chunk_ids), doc_id)

        del registry[doc_id]
        _save_registry(registry)
        return True

    def delete_tenant(self, tenant_id: str) -> int:
        """
        Delete ALL support content for a tenant (collection + registry entries).

        Returns the number of documents deleted.
        """
        registry = _load_registry()
        docs_to_delete = [
            doc_id for doc_id, entry in registry.items()
            if entry["tenant_id"] == tenant_id
        ]

        if not docs_to_delete:
            return 0

        # Drop the entire tenant collection
        safe_name = _collection_name(tenant_id)
        try:
            self._client.delete_collection(safe_name)
            logger.info("Dropped ChromaDB collection '%s'", safe_name)
        except Exception as e:
            logger.warning("Could not drop collection '%s': %s", safe_name, e)

        for doc_id in docs_to_delete:
            del registry[doc_id]
        _save_registry(registry)

        logger.info("Deleted %d documents for tenant '%s'", len(docs_to_delete), tenant_id)
        return len(docs_to_delete)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_documents(self, tenant_id: str) -> list[SupportDocument]:
        """List all ingested support documents for a specific tenant."""
        registry = _load_registry()
        documents: list[SupportDocument] = []

        for entry in registry.values():
            if entry["tenant_id"] != tenant_id:
                continue
            documents.append(
                SupportDocument(
                    doc_id=entry["doc_id"],
                    tenant_id=entry["tenant_id"],
                    filename=entry["filename"],
                    doc_type=entry["doc_type"],
                    language=entry.get("language", "unknown"),
                    chunks_count=entry["chunks_count"],
                    ingested_at=datetime.fromisoformat(entry["ingested_at"]),
                )
            )

        return sorted(documents, key=lambda d: d.ingested_at, reverse=True)

    def list_tenants(self) -> list[str]:
        """Return a sorted list of all tenant IDs that have ingested content."""
        registry = _load_registry()
        return sorted({entry["tenant_id"] for entry in registry.values()})

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
