"""
Tenants router — workspace-level support content management.

Endpoints:
    GET    /tenants                                  → list all tenant IDs
    GET    /tenants/{tenant_id}/documents            → list a tenant's documents
    DELETE /tenants/{tenant_id}                      → delete ALL content for a tenant
    DELETE /tenants/{tenant_id}/documents/{doc_id}   → delete a single document
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from models.responses import (
    SupportDocument,
    SupportDocumentListResponse,
    TenantListResponse,
)
from services.cache import get_document_cache, get_ollama_context_cache
from services.vectorstore import VectorStore
from routers.ingest import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# ---------------------------------------------------------------------------
# GET /tenants
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=TenantListResponse,
    summary="List all tenants",
    description="Returns a sorted list of all workspace IDs with at least one ingested document.",
)
async def list_tenants(
    vector_store: VectorStore = Depends(get_vector_store),
) -> TenantListResponse:
    tenants = vector_store.list_tenants()
    return TenantListResponse(tenants=tenants, total=len(tenants))


# ---------------------------------------------------------------------------
# GET /tenants/{tenant_id}/documents
# ---------------------------------------------------------------------------

@router.get(
    "/{tenant_id}/documents",
    response_model=SupportDocumentListResponse,
    summary="List a tenant's support documents",
    description=(
        "Returns all ingested support documents for the specified workspace, newest "
        "first, including each document's category and language."
    ),
)
async def list_tenant_documents(
    tenant_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> SupportDocumentListResponse:
    documents: list[SupportDocument] = vector_store.list_documents(tenant_id)
    if not documents:
        raise HTTPException(
            status_code=404,
            detail=f"No support documents found for tenant '{tenant_id}'.",
        )
    return SupportDocumentListResponse(
        tenant_id=tenant_id,
        documents=documents,
        total=len(documents),
    )


# ---------------------------------------------------------------------------
# DELETE /tenants/{tenant_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete all support content for a tenant",
    description=(
        "Permanently removes all ingested documents and their vector embeddings for "
        "the specified workspace. This action is irreversible."
    ),
)
async def delete_tenant(
    tenant_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    deleted = vector_store.delete_tenant(tenant_id)
    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No support documents found for tenant '{tenant_id}'.",
        )

    # Both caches are keyed by (tenant_id, doc_id); without this the next query
    # would answer from the stale chunk cache and stale Ollama KV context.
    get_document_cache().invalidate_namespace(tenant_id)
    get_ollama_context_cache().invalidate_namespace(tenant_id)

    return {
        "message": f"All support content for tenant '{tenant_id}' deleted successfully.",
        "tenant_id": tenant_id,
        "documents_deleted": deleted,
    }


# ---------------------------------------------------------------------------
# DELETE /tenants/{tenant_id}/documents/{doc_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{tenant_id}/documents/{doc_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a single support document",
    description="Removes a specific document and all its chunks from the workspace.",
)
async def delete_tenant_document(
    tenant_id: str,
    doc_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    found = vector_store.delete_document(doc_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found for tenant '{tenant_id}'.",
        )

    # Evict from both caches, or queries with this document_id keep answering
    # from RAM long after the vectors are gone — a real risk when a policy is
    # deleted precisely because it was wrong.
    get_document_cache().invalidate_doc(doc_id)
    get_ollama_context_cache().invalidate_doc(doc_id)

    return {
        "message": f"Document '{doc_id}' deleted successfully.",
        "tenant_id": tenant_id,
        "doc_id": doc_id,
    }
