"""
Query router — answers customer questions and drafts agent replies.

Endpoints:
    POST /query              → batch answer (JSON)
    POST /query/stream       → streaming answer (SSE)
    POST /query/draft-reply  → agent-ready reply draft (JSON)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from config import settings
from models.requests import DraftReplyRequest, QueryRequest
from models.responses import DraftReplyResponse, QueryResponse
from services.embedder import Embedder, get_embedder
from services.language import is_supported, normalize_code
from services.rag_chain import SupportRAGChain
from services.vectorstore import VectorStore
from routers.ingest import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


# ---------------------------------------------------------------------------
# Dependency: SupportRAGChain
# ---------------------------------------------------------------------------

def get_rag_chain(
    embedder: Embedder = Depends(lambda: get_embedder(settings.embedding_model)),
    vector_store: VectorStore = Depends(get_vector_store),
) -> SupportRAGChain:
    return SupportRAGChain(embedder=embedder, vector_store=vector_store)


def _validate_language(value: str | None, field: str) -> str | None:
    """
    Reject unsupported language codes with a 400 instead of silently answering
    in the fallback language — a caller forcing `language="xx"` needs to know
    the request was wrong, not receive an English reply.
    """
    if value is None:
        return None

    code = normalize_code(value)
    if not code or code == "auto":
        return "auto" if field == "language" else None
    if not is_supported(code):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported {field} '{value}'. "
                "See GET /languages for the supported set."
            ),
        )
    return code


# ---------------------------------------------------------------------------
# POST /query  — Batch (full JSON response)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=QueryResponse,
    summary="Answer a customer question",
    description=(
        "Answer a customer question from a workspace's ingested support content. "
        "Returns a grounded reply with inline `[Source N]` citations.\n\n"
        "The reply language mirrors the customer's question by default — retrieval is "
        "cross-lingual, so a Spanish question is answered from English help articles. "
        "Set `language` to force a specific reply language.\n\n"
        "When the content does not cover the question, the reply is a localised "
        "hand-off message with `escalate: true` — never a guess.\n\n"
        "Use `doc_type_filter` to restrict retrieval to one content category and "
        "`language_filter` to restrict it to source content in one language.\n\n"
        "For streaming, use `POST /query/stream`."
    ),
)
async def query_support_content(
    request: QueryRequest,
    rag: SupportRAGChain = Depends(get_rag_chain),
) -> QueryResponse:
    if request.stream:
        raise HTTPException(
            status_code=400,
            detail="For streaming responses, use POST /query/stream instead.",
        )

    language = _validate_language(request.language, "language")
    language_filter = _validate_language(request.language_filter, "language_filter")

    try:
        response = await rag.query(
            question=request.question,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
            language=language,
            doc_type_filter=request.doc_type_filter,
            language_filter=language_filter,
            document_id=request.document_id,
            conversation_id=request.conversation_id,
        )
    except Exception as e:
        logger.exception("RAG query failed for tenant '%s'", request.tenant_id)
        raise HTTPException(status_code=500, detail=f"Query error: {e}")

    return response


# ---------------------------------------------------------------------------
# POST /query/stream  — Server-Sent Events
# ---------------------------------------------------------------------------

@router.post(
    "/stream",
    summary="Stream a customer reply",
    description=(
        "Answer a question and receive the reply token-by-token via Server-Sent Events "
        "(SSE). Each event is a JSON object: `{\"token\": \"...\", \"done\": false}`. "
        "The final event contains `{\"sources\": [...], \"escalate\": false, "
        "\"answer_language\": \"es\", \"done\": true}`."
    ),
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of reply tokens followed by source metadata.",
        }
    },
)
async def stream_query_support_content(
    request: QueryRequest,
    rag: SupportRAGChain = Depends(get_rag_chain),
) -> StreamingResponse:
    language = _validate_language(request.language, "language")
    language_filter = _validate_language(request.language_filter, "language_filter")

    async def event_generator():
        try:
            async for chunk in rag.stream_query(
                question=request.question,
                tenant_id=request.tenant_id,
                top_k=request.top_k,
                language=language,
                doc_type_filter=request.doc_type_filter,
                language_filter=language_filter,
                document_id=request.document_id,
                conversation_id=request.conversation_id,
            ):
                yield chunk
        except Exception as e:
            import json
            logger.exception("Streaming RAG query failed for tenant '%s'", request.tenant_id)
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )


# ---------------------------------------------------------------------------
# POST /query/draft-reply  — Agent-assist draft
# ---------------------------------------------------------------------------

@router.post(
    "/draft-reply",
    response_model=DraftReplyResponse,
    summary="Draft a reply for a human agent",
    description=(
        "Turn an incoming customer message (email or chat) into a complete, "
        "send-ready draft: greeting, grounded answer with `[Source N]` citations, and "
        "a closing line — written in the customer's language.\n\n"
        "This is the agent-assist path: unlike `POST /query`, the draft is meant for a "
        "human to review, so the retrieved chunks are returned in full for verification. "
        "`tone` selects the register (`friendly`, `formal`, `concise`).\n\n"
        "If the support content does not cover the request, `escalate` is `true` and no "
        "draft is invented."
    ),
)
async def draft_agent_reply(
    request: DraftReplyRequest,
    rag: SupportRAGChain = Depends(get_rag_chain),
) -> DraftReplyResponse:
    language = _validate_language(request.language, "language")

    try:
        response = await rag.draft_reply(
            message=request.message,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
            language=language,
            tone=request.tone,
        )
    except Exception as e:
        logger.exception("Reply drafting failed for tenant '%s'", request.tenant_id)
        raise HTTPException(status_code=500, detail=f"Draft error: {e}")

    return response
