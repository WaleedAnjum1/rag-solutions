"""
Query router — answers clinical questions and generates patient summaries.

Endpoints:
    POST /query           → batch answer (JSON)
    POST /query/stream    → streaming answer (SSE)
    POST /query/summarise → structured patient summary (JSON)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from config import settings
from models.requests import QueryRequest, SummaryRequest
from models.responses import PatientSummaryResponse, QueryResponse
from services.embedder import Embedder, get_embedder
from services.rag_chain import MedicalRAGChain
from services.vectorstore import VectorStore
from routers.ingest import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


# ---------------------------------------------------------------------------
# Dependency: MedicalRAGChain
# ---------------------------------------------------------------------------

def get_rag_chain(
    embedder: Embedder = Depends(lambda: get_embedder(settings.embedding_model)),
    vector_store: VectorStore = Depends(get_vector_store),
) -> MedicalRAGChain:
    return MedicalRAGChain(embedder=embedder, vector_store=vector_store)


# ---------------------------------------------------------------------------
# POST /query  — Batch (full JSON response)
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=QueryResponse,
    summary="Ask a clinical question",
    description=(
        "Ask a natural language clinical question against a patient's ingested records. "
        "Returns a grounded answer with inline source citations and the retrieved chunks.\n\n"
        "Use `record_type_filter` to restrict retrieval to a specific document category "
        "(e.g., only `lab_report` or only `prescription`).\n\n"
        "For streaming, use `POST /query/stream`."
    ),
)
async def query_patient_records(
    request: QueryRequest,
    rag: MedicalRAGChain = Depends(get_rag_chain),
) -> QueryResponse:
    if request.stream:
        raise HTTPException(
            status_code=400,
            detail="For streaming responses, use POST /query/stream instead.",
        )

    try:
        response = await rag.query(
            question=request.question,
            patient_id=request.patient_id,
            top_k=request.top_k,
            record_type_filter=request.record_type_filter,
            document_id=request.document_id,
        )
    except Exception as e:
        logger.exception("RAG query failed for patient '%s'", request.patient_id)
        raise HTTPException(status_code=500, detail=f"Query error: {e}")

    return response


# ---------------------------------------------------------------------------
# POST /query/stream  — Server-Sent Events
# ---------------------------------------------------------------------------

@router.post(
    "/stream",
    summary="Stream a clinical answer",
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
async def stream_query_patient_records(
    request: QueryRequest,
    rag: MedicalRAGChain = Depends(get_rag_chain),
) -> StreamingResponse:
    async def event_generator():
        try:
            async for chunk in rag.stream_query(
                question=request.question,
                patient_id=request.patient_id,
                top_k=request.top_k,
                record_type_filter=request.record_type_filter,
                document_id=request.document_id,
            ):
                yield chunk
        except Exception as e:
            import json
            logger.exception("Streaming RAG query failed for patient '%s'", request.patient_id)
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
# POST /query/summarise  — Structured patient summary
# ---------------------------------------------------------------------------

@router.post(
    "/summarise",
    response_model=PatientSummaryResponse,
    summary="Generate a structured patient summary",
    description=(
        "Retrieve up to `top_k` chunks from all of a patient's records and instruct "
        "the LLM to extract a structured clinical summary including:\n\n"
        "- **summary**: Narrative overview of the patient's medical history\n"
        "- **conditions**: List of diagnosed conditions\n"
        "- **medications**: Current medications with dosage and frequency\n"
        "- **allergies**: Known allergies and reactions\n"
        "- **last_visit**: Date of most recent clinical encounter\n\n"
        "All data is grounded strictly in the ingested documents."
    ),
)
async def summarise_patient(
    request: SummaryRequest,
    rag: MedicalRAGChain = Depends(get_rag_chain),
) -> PatientSummaryResponse:
    try:
        response = await rag.summarise(
            patient_id=request.patient_id,
            top_k=request.top_k,
        )
    except Exception as e:
        logger.exception("Summary generation failed for patient '%s'", request.patient_id)
        raise HTTPException(status_code=500, detail=f"Summary error: {e}")

    return response
