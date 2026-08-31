"""
Ingest router — handles document upload, listing, and deletion.

Endpoints:
    POST   /ingest
    GET    /documents
    DELETE /documents/{doc_id}
"""

import logging
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from config import settings
from models.responses import DocumentInfo, DocumentListResponse, IngestResponse, SourceChunk
from services.cache import get_document_cache, get_ollama_context_cache
from services.document_loader import load_and_chunk
from services.embedder import Embedder, get_embedder
from services.vectorstore import VectorStore, generate_doc_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingest"])

# ---------------------------------------------------------------------------
# Shared dependency: VectorStore instance
# ---------------------------------------------------------------------------
# We use a module-level singleton here (not recreated per request).
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document",
    description=(
        "Upload a file (PDF, DOCX, XLSX, XLS, CSV, TXT, MD, RST) to be chunked, embedded, and stored "
        "in the specified namespace. Returns a `doc_id` for future reference."
    ),
)
async def ingest_document(
    file: Annotated[
        UploadFile,
        File(description="Document to ingest (PDF, DOCX, XLSX, XLS, CSV, TXT, MD, RST)."),
    ],
    background_tasks: BackgroundTasks,
    namespace: Annotated[
        str,
        Form(description="Namespace / tenant identifier. Defaults to 'default'."),
    ] = "default",
    embedder: Embedder = Depends(lambda: get_embedder(settings.embedding_model)),
    vector_store: VectorStore = Depends(get_vector_store),
) -> IngestResponse:
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50 MB.")

    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Load and chunk
    try:
        chunks = load_and_chunk(
            content=content,
            filename=filename,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception as e:
        logger.exception("Failed to load document '%s'", filename)
        raise HTTPException(status_code=500, detail=f"Failed to parse document: {e}")

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="Document produced no text content. Is the file readable?",
        )

    # Embed all chunks — use async_embed to avoid blocking the event loop
    try:
        texts = [c.text for c in chunks]
        embeddings = await embedder.async_embed(texts)
    except Exception as e:
        logger.exception("Embedding failed for '%s'", filename)
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")

    # Store in ChromaDB
    doc_id = generate_doc_id()
    try:
        chunks_stored = vector_store.add_document(
            doc_id=doc_id,
            filename=filename,
            namespace=namespace,
            chunks=chunks,
            embeddings=embeddings,
            file_type=ext,
        )
    except Exception as e:
        logger.exception("VectorStore insert failed for doc '%s'", doc_id)
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    logger.info("Ingested '%s' → doc_id=%s (%d chunks)", filename, doc_id, chunks_stored)

    # -----------------------------------------------------------------------
    # 1. Populate the in-memory chunk cache so ChromaDB is bypassed on queries
    # -----------------------------------------------------------------------
    chunk_cache = get_document_cache()
    source_chunks = [
        SourceChunk(
            chunk_id=f"{doc_id}_chunk_{c.chunk_index}",
            doc_id=doc_id,
            filename=filename,
            text=c.text,
            relevance_score=None,
            page=c.page,
            chunk_index=c.chunk_index,
        )
        for c in chunks
    ]
    chunk_cache.put(namespace, doc_id, list(zip(embeddings, source_chunks)))

    # -----------------------------------------------------------------------
    # 2. Pre-compute Ollama KV context in the background.
    #    Ollama processes [system_prompt + full_document] once and caches the
    #    KV state. All follow-up questions only send the question tokens → fast.
    #
    #    Uses BackgroundTasks rather than asyncio.create_task: a bare task with
    #    no retained reference can be garbage-collected mid-flight, silently
    #    losing the pre-warm.
    # -----------------------------------------------------------------------
    from services.rag_chain import precompute_ollama_context
    background_tasks.add_task(
        precompute_ollama_context,
        namespace=namespace,
        doc_id=doc_id,
        chunks=source_chunks,
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )

    return IngestResponse(
        doc_id=doc_id,
        filename=filename,
        namespace=namespace,
        chunks_count=chunks_stored,
    )


# ---------------------------------------------------------------------------
# GET /documents  (note: placed here even though path differs, grouped logically)
# ---------------------------------------------------------------------------

documents_router = APIRouter(prefix="/documents", tags=["Documents"])


@documents_router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List all ingested documents",
    description="Returns all documents, optionally filtered by namespace.",
)
async def list_documents(
    namespace: Optional[str] = None,
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentListResponse:
    docs: list[DocumentInfo] = vector_store.list_documents(namespace=namespace)
    return DocumentListResponse(documents=docs, total=len(docs), namespace=namespace)


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id}
# ---------------------------------------------------------------------------

@documents_router.delete(
    "/{doc_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document",
    description="Removes a document and all its chunks from the vector store.",
)
async def delete_document(
    doc_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    found = vector_store.delete_document(doc_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found.",
        )
    # Evict from both caches. invalidate_doc sweeps every namespace holding the
    # doc_id — the old loop only visited namespaces present in the *chunk* cache,
    # so an Ollama context whose chunk entry had been LRU-evicted leaked.
    get_document_cache().invalidate_doc(doc_id)
    get_ollama_context_cache().invalidate_doc(doc_id)
    return {"message": f"Document '{doc_id}' deleted successfully.", "doc_id": doc_id}
