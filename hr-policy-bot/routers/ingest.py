"""
Ingest router — handles HR document upload.

Endpoints:
    POST /ingest   — upload an HR document (handbook, policy, SOP, onboarding doc)
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
from models.requests import DOC_TYPES
from models.responses import IngestResponse, SourceChunk
from services.cache import get_document_cache
from services.document_loader import load_and_chunk
from services.embedder import Embedder, get_embedder
from services.language import detect_language, is_supported, normalize_code
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
    summary="Ingest an HR document",
    description=(
        "Upload an HR document (PDF, DOCX, XLSX, XLS, CSV, TXT, MD, RST) for a "
        "company workspace. The document is chunked, embedded, and "
        "stored in an isolated tenant namespace in ChromaDB. Returns a `doc_id`.\n\n"
        "**`doc_type` options:** `policy`, `handbook`, `sop`, `onboarding`, "
        "`benefits`, `compliance`, `general`\n\n"
        "**`language`:** a 2-letter code, or `auto` (default) to detect it."
    ),
)
async def ingest_support_document(
    file: Annotated[
        UploadFile,
        File(description="Support document to ingest (PDF, DOCX, XLSX, XLS, CSV, TXT, MD, RST)."),
    ],
    tenant_id: Annotated[
        str,
        Form(
            description=(
                "Unique workspace identifier. Used as the isolated namespace in ChromaDB. "
                "Example: 'acme_saas', 'telco-eu'."
            )
        ),
    ],
    background_tasks: BackgroundTasks,
    doc_type: Annotated[
        str,
        Form(
            description=(
                "Category of the support document. "
                "One of: faq, help_article, policy, ticket, product_guide, "
                "troubleshooting, general."
            )
        ),
    ] = "general",
    language: Annotated[
        str,
        Form(description="2-letter language code of the document, or 'auto' to detect it."),
    ] = "auto",
    embedder: Embedder = Depends(lambda: get_embedder(settings.embedding_model)),
    vector_store: VectorStore = Depends(get_vector_store),
) -> IngestResponse:
    # Validate tenant_id
    tenant_id = tenant_id.strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id must not be empty.")

    # Validate doc_type
    if doc_type not in DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type '{doc_type}'. Valid: {sorted(DOC_TYPES)}",
        )

    # Validate language ('auto' is resolved after the text is extracted)
    language = normalize_code(language) or "auto"
    if language != "auto" and not is_supported(language):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{language}'. See GET /languages for the supported set.",
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

    # Resolve the document language. Detection samples the first few chunks
    # rather than one, so a title page or English boilerplate header doesn't
    # decide the language of a whole translated article.
    language_confidence: float | None = None
    if language == "auto":
        sample = "\n".join(c.text for c in chunks[:3])
        language, language_confidence = detect_language(sample)
        logger.info(
            "Detected language '%s' (confidence=%.2f) for '%s'",
            language, language_confidence, filename,
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
            tenant_id=tenant_id,
            doc_type=doc_type,
            language=language,
            chunks=chunks,
            embeddings=embeddings,
            file_type=ext,
        )
    except Exception as e:
        logger.exception("VectorStore insert failed for doc '%s'", doc_id)
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    logger.info(
        "Ingested '%s' → doc_id=%s (tenant=%s, type=%s, lang=%s, %d chunks)",
        filename, doc_id, tenant_id, doc_type, language, chunks_stored,
    )

    # -----------------------------------------------------------------------
    # 1. Populate in-memory chunk cache (namespace = tenant_id)
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
            doc_type=doc_type,
            language=language,
        )
        for c in chunks
    ]
    chunk_cache.put(tenant_id, doc_id, list(zip(embeddings, source_chunks)))

    # -----------------------------------------------------------------------
    # 2. Pre-compute Ollama KV context in the background.
    #    Ollama processes [system_prompt + full_document] once and caches the
    #    KV state. All follow-up questions only send the question tokens → fast.
    #
    #    The cached prefix is language-neutral (the reply-language instruction
    #    travels with the question), so this one pass serves customers writing
    #    in any supported language.
    #
    #    Uses BackgroundTasks rather than asyncio.create_task: a bare task with
    #    no retained reference can be garbage-collected mid-flight, silently
    #    losing the pre-warm.
    # -----------------------------------------------------------------------
    from services.rag_chain import precompute_ollama_context
    background_tasks.add_task(
        precompute_ollama_context,
        namespace=tenant_id,
        doc_id=doc_id,
        chunks=source_chunks,
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )

    return IngestResponse(
        doc_id=doc_id,
        filename=filename,
        tenant_id=tenant_id,
        doc_type=doc_type,
        language=language,
        language_confidence=language_confidence,
        chunks_count=chunks_stored,
    )
