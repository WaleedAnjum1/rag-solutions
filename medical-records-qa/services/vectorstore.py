"""
ChromaDB vector store abstraction — Medical Records Q&A.

Each patient_id maps to a separate ChromaDB collection for full patient isolation.
Document metadata is mirrored in a lightweight JSON registry file so we can list
documents without scanning all chunks.

Extended from doc-qa-service/services/vectorstore.py:
- Adds `patient_id` and `record_type` to chunk metadata
- Exposes list_patients() to enumerate all known patient IDs
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chromadb

from config import settings
from models.responses import PatientRecord, SourceChunk
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
    Thin wrapper around ChromaDB scoped per patient_id (used as the namespace).

    Handles:
    - patient-scoped collections
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

    def _collection(self, patient_id: str) -> chromadb.Collection:
        """Get or create a ChromaDB collection for the given patient_id."""
        safe_name = "pt_" + "".join(c if c.isalnum() else "_" for c in patient_id)
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
        patient_id: str,
        record_type: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        file_type: str,
    ) -> int:
        """
        Store all chunks + embeddings for a medical document.

        Returns the number of chunks stored.
        """
        if not chunks:
            raise ValueError("Cannot ingest a document with zero chunks.")

        collection = self._collection(patient_id)

        ids = [f"{doc_id}_chunk_{c.chunk_index}" for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "patient_id": patient_id,
                "record_type": record_type,
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
            "patient_id": patient_id,
            "record_type": record_type,
            "chunks_count": len(chunks),
            "file_type": file_type,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_registry(registry)

        logger.info(
            "Stored %d chunks for doc '%s' (patient=%s, type=%s)",
            len(chunks), doc_id, patient_id, record_type,
        )
        return len(chunks)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        patient_id: str,
        top_k: int = 6,
        record_type_filter: str | None = None,
        doc_id_filter: str | None = None,
    ) -> list[SourceChunk]:
        """
        Retrieve the top-k most relevant chunks for a query embedding.

        Args:
            query_embedding:    Embedding of the user's question.
            patient_id:         Patient whose collection to search.
            top_k:              Max chunks to return.
            record_type_filter: Optional — restrict to a document category.
            doc_id_filter:      Optional — restrict to a specific document.

        Returns:
            List of SourceChunk objects sorted by relevance (descending).
        """
        collection = self._collection(patient_id)

        if collection.count() == 0:
            logger.warning("Patient '%s' has no ingested records.", patient_id)
            return []

        conditions = []
        if record_type_filter:
            conditions.append({"record_type": {"$eq": record_type_filter}})
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
                    record_type=meta.get("record_type"),
                )
            )

        return source_chunks

    def get_all_chunks(self, patient_id: str, doc_id: str) -> list[SourceChunk]:
        """Fetch all chunks for a document without semantic search, sorted by index."""
        collection = self._collection(patient_id)
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
                    record_type=meta.get("record_type"),
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

        patient_id = entry["patient_id"]
        collection = self._collection(patient_id)

        results = collection.get(where={"doc_id": doc_id}, include=[])
        chunk_ids = results["ids"]

        if chunk_ids:
            collection.delete(ids=chunk_ids)
            logger.info("Deleted %d chunks for doc '%s'", len(chunk_ids), doc_id)

        del registry[doc_id]
        _save_registry(registry)
        return True

    def delete_patient(self, patient_id: str) -> int:
        """
        Delete ALL records for a patient (entire collection + registry entries).

        Returns the number of documents deleted.
        """
        registry = _load_registry()
        docs_to_delete = [
            doc_id for doc_id, entry in registry.items()
            if entry["patient_id"] == patient_id
        ]

        if not docs_to_delete:
            return 0

        # Drop the entire patient collection
        safe_name = "pt_" + "".join(c if c.isalnum() else "_" for c in patient_id)
        try:
            self._client.delete_collection(safe_name)
            logger.info("Dropped ChromaDB collection '%s'", safe_name)
        except Exception as e:
            logger.warning("Could not drop collection '%s': %s", safe_name, e)

        for doc_id in docs_to_delete:
            del registry[doc_id]
        _save_registry(registry)

        logger.info("Deleted %d documents for patient '%s'", len(docs_to_delete), patient_id)
        return len(docs_to_delete)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_records(self, patient_id: str) -> list[PatientRecord]:
        """List all ingested records for a specific patient."""
        registry = _load_registry()
        records: list[PatientRecord] = []

        for entry in registry.values():
            if entry["patient_id"] != patient_id:
                continue
            records.append(
                PatientRecord(
                    doc_id=entry["doc_id"],
                    patient_id=entry["patient_id"],
                    filename=entry["filename"],
                    record_type=entry["record_type"],
                    chunks_count=entry["chunks_count"],
                    ingested_at=datetime.fromisoformat(entry["ingested_at"]),
                )
            )

        return sorted(records, key=lambda r: r.ingested_at, reverse=True)

    def list_patients(self) -> list[str]:
        """Return a sorted list of all patient IDs that have ingested records."""
        registry = _load_registry()
        return sorted({entry["patient_id"] for entry in registry.values()})

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
