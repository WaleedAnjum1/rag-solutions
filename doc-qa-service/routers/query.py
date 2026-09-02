"""
Query router — answers questions against ingested documents.

Endpoints:
    POST /query          → batch answer (JSON)
    POST /query/stream   → streaming answer (SSE)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from config import settings
from models.requests import QueryRequest
from models.responses import QueryResponse
from services.embedder import Embedder, get_embedder
from services.rag_chain import RAGChain
from services.vectorstore import VectorStore
from routers.ingest import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


# ---------------------------------------------------------------------------
# Dependency: RAGChain
# ---------------------------------------------------------------------------

def get_rag_chain(
    embedder: Embedder = Depends(lambda: get_embedder(settings.embedding_model)),
    vector_store: VectorStore = Depends(get_vector_store),
) -> RAGChain:
    return RAGChain(embedder=embedder, vector_store=vector_store)


# ---------------------------------------------------------------------------
# POST /query  — Batch (full response)
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=QueryResponse,
    summary="Query documents",
    description=(
        "Ask a natural language question and receive a generated answer grounded "
        "in the ingested documents, with source chunks cited. "
        "Set `stream: true` in the request body to use the SSE streaming endpoint instead."
    ),
)
async def query_documents(
    request: QueryRequest,
    rag: RAGChain = Depends(get_rag_chain),
) -> QueryResponse:
    if request.stream:
        raise HTTPException(
            status_code=400,
            detail="For streaming, use POST /query/stream instead.",
        )

    try:
        response = await rag.query(
            question=request.question,
            namespace=request.namespace,
            top_k=request.top_k,
            document_id=request.document_id,
        )
    except Exception as e:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail=f"Query error: {e}")

    return response


# ---------------------------------------------------------------------------
# POST /query/stream  — Server-Sent Events
# ---------------------------------------------------------------------------

@router.post(
    "/stream",
    summary="Stream a query response",
    description=(
        "Ask a question and receive the answer token-by-token via Server-Sent Events (SSE). "
        "Each event is a JSON object: `{\"token\": \"...\", \"done\": false}`. "
        "The final event contains `{\"sources\": [...], \"done\": true}`."
    ),
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of answer tokens followed by source metadata.",
        }
    },
)
async def stream_query_documents(
    request: QueryRequest,
    rag: RAGChain = Depends(get_rag_chain),
) -> StreamingResponse:
    async def event_generator():
        try:
            async for chunk in rag.stream_query(
                question=request.question,
                namespace=request.namespace,
                top_k=request.top_k,
                document_id=request.document_id,
            ):
                yield chunk
        except Exception as e:
            import json
            logger.exception("Streaming RAG query failed")
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )
