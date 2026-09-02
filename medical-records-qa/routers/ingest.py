"""
Ingest router — handles medical record upload.

Endpoints:
    POST /ingest   — upload a medical document for a patient
"""

import logging
from typing import Annotated

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
from models.responses import IngestResponse, SourceChunk
from services.cache import get_document_cache
from services.document_loader import load_and_chunk
from services.embedder import Embedder, get_embedder
from services.vectorstore import VectorStore, generate_doc_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingest"])

# ---------------------------------------------------------------------------
# Shared VectorStore singleton
# ---------------------------------------------------------------------------

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
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a medical record",
    description=(
        "Upload a medical document (PDF, DOCX, XLSX, XLS, CSV, TXT, MD, RST) "
        "for a specific patient. The document is chunked, embedded, and stored "
        "in an isolated patient namespace in ChromaDB. Returns a `doc_id` for "
        "future reference.\n\n"
        "**`record_type` options:** `lab_report`, `prescription`, "
        "`discharge_summary`, `imaging`, `consultation_note`, `general`"
    ),
)
async def ingest_medical_record(
    file: Annotated[
        UploadFile,
        File(description="Medical document to ingest (PDF, DOCX, XLSX, XLS, CSV, TXT, MD, RST)."),
    ],
    patient_id: Annotated[
        str,
        Form(
            description=(
                "Unique patient identifier. Used as the isolated namespace in ChromaDB. "
                "Example: 'patient_001', 'PT-2024-00123'."
            )
        ),
    ],
    background_tasks: BackgroundTasks,
    record_type: Annotated[
        str,
        Form(
            description=(
                "Category of the medical document. "
                "One of: lab_report, prescription, discharge_summary, "
                "imaging, consultation_note, general."
            )
        ),
    ] = "general",
    embedder: Embedder = Depends(lambda: get_embedder(settings.embedding_model)),
    vector_store: VectorStore = Depends(get_vector_store),
) -> IngestResponse:
    # Validate patient_id
    patient_id = patient_id.strip()
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id must not be empty.")

    # Validate record_type
    valid_types = {
        "lab_report", "prescription", "discharge_summary",
        "imaging", "consultation_note", "general",
    }
    if record_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid record_type '{record_type}'. Valid: {sorted(valid_types)}",
        )

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

    # Embed all chunks
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
            patient_id=patient_id,
            record_type=record_type,
            chunks=chunks,
            embeddings=embeddings,
            file_type=ext,
        )
    except Exception as e:
        logger.exception("VectorStore insert failed for doc '%s'", doc_id)
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    logger.info(
        "Ingested '%s' → doc_id=%s (patient=%s, type=%s, %d chunks)",
        filename, doc_id, patient_id, record_type, chunks_stored,
    )

    # -----------------------------------------------------------------------
    # 1. Populate in-memory chunk cache (namespace = patient_id)
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
            record_type=record_type,
        )
        for c in chunks
    ]
    chunk_cache.put(patient_id, doc_id, list(zip(embeddings, source_chunks)))

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
        namespace=patient_id,
        doc_id=doc_id,
        chunks=source_chunks,
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )

    return IngestResponse(
        doc_id=doc_id,
        filename=filename,
        patient_id=patient_id,
        record_type=record_type,
        chunks_count=chunks_stored,
    )
