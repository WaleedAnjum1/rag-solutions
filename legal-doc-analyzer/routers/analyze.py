from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from models.responses import Clause, RiskFlag, DocumentBrief
from routers.ingest import get_vector_store
from services.vectorstore import VectorStore
from services.clauses import analyze_clauses, analyze_risks, extract_brief

router = APIRouter(prefix="/analyze", tags=["Analyze"])

class AnalyzeRequest(BaseModel):
    tenant_id: str
    doc_id: str

class CompareRequest(BaseModel):
    tenant_id: str
    doc_id_a: str
    doc_id_b: str

@router.post("/clauses", response_model=List[Clause])
async def get_clauses(
    request: AnalyzeRequest,
    vector_store: VectorStore = Depends(get_vector_store)
) -> List[Clause]:
    chunks = vector_store.get_all_chunks(request.tenant_id, request.doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    
    clauses = await analyze_clauses(chunks, settings.ollama_model, settings.ollama_base_url)
    return clauses

@router.post("/risks", response_model=List[RiskFlag])
async def get_risks(
    request: AnalyzeRequest,
    vector_store: VectorStore = Depends(get_vector_store)
) -> List[RiskFlag]:
    chunks = vector_store.get_all_chunks(request.tenant_id, request.doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    
    clauses = await analyze_clauses(chunks, settings.ollama_model, settings.ollama_base_url)
    doc_type = chunks[0].doc_type or "general"
    risks = analyze_risks(clauses, doc_type)
    return risks

@router.post("/brief", response_model=DocumentBrief)
async def get_brief(
    request: AnalyzeRequest,
    vector_store: VectorStore = Depends(get_vector_store)
) -> DocumentBrief:
    chunks = vector_store.get_all_chunks(request.tenant_id, request.doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    
    clauses = await analyze_clauses(chunks, settings.ollama_model, settings.ollama_base_url)
    brief = await extract_brief(clauses, request.doc_id, settings.ollama_model, settings.ollama_base_url)
    return brief

from models.responses import CompareResponse
from services.clauses import compare_documents

@router.post("/compare", response_model=CompareResponse)
async def compare_docs(
    request: CompareRequest,
    vector_store: VectorStore = Depends(get_vector_store)
) -> CompareResponse:
    chunks_a = vector_store.get_all_chunks(request.tenant_id, request.doc_id_a)
    chunks_b = vector_store.get_all_chunks(request.tenant_id, request.doc_id_b)
    
    if not chunks_a or not chunks_b:
        raise HTTPException(status_code=404, detail="One or both documents not found")
        
    clauses_a = await analyze_clauses(chunks_a, settings.ollama_model, settings.ollama_base_url)
    clauses_b = await analyze_clauses(chunks_b, settings.ollama_model, settings.ollama_base_url)
    
    diffs = await compare_documents(clauses_a, clauses_b, settings.ollama_model, settings.ollama_base_url)
    
    return CompareResponse(
        doc_id_a=request.doc_id_a,
        doc_id_b=request.doc_id_b,
        differences=diffs
    )
