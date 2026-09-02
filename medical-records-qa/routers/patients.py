"""
Patients router — patient-level record management.

Endpoints:
    GET    /patients                              → list all patient IDs
    GET    /patients/{patient_id}/records         → list records for a patient
    DELETE /patients/{patient_id}                 → delete ALL records for a patient
    DELETE /patients/{patient_id}/records/{doc_id} → delete a single record
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from models.responses import PatientListResponse, PatientRecord, PatientRecordListResponse
from services.cache import get_document_cache, get_ollama_context_cache
from services.vectorstore import VectorStore
from routers.ingest import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])


# ---------------------------------------------------------------------------
# GET /patients
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PatientListResponse,
    summary="List all patients",
    description="Returns a sorted list of all patient IDs that have at least one ingested record.",
)
async def list_patients(
    vector_store: VectorStore = Depends(get_vector_store),
) -> PatientListResponse:
    patients = vector_store.list_patients()
    return PatientListResponse(patients=patients, total=len(patients))


# ---------------------------------------------------------------------------
# GET /patients/{patient_id}/records
# ---------------------------------------------------------------------------

@router.get(
    "/{patient_id}/records",
    response_model=PatientRecordListResponse,
    summary="List records for a patient",
    description="Returns all ingested documents for the specified patient, sorted newest first.",
)
async def list_patient_records(
    patient_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> PatientRecordListResponse:
    records: list[PatientRecord] = vector_store.list_records(patient_id)
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No records found for patient '{patient_id}'.",
        )
    return PatientRecordListResponse(
        patient_id=patient_id,
        records=records,
        total=len(records),
    )


# ---------------------------------------------------------------------------
# DELETE /patients/{patient_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete all records for a patient",
    description=(
        "Permanently removes all ingested documents and their vector embeddings "
        "for the specified patient. This action is irreversible."
    ),
)
async def delete_patient(
    patient_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    deleted = vector_store.delete_patient(patient_id)
    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No records found for patient '{patient_id}'.",
        )

    # Both caches are keyed by (patient_id, doc_id); without this the next query
    # would answer from the stale chunk cache and stale Ollama KV context.
    get_document_cache().invalidate_namespace(patient_id)
    get_ollama_context_cache().invalidate_namespace(patient_id)

    return {
        "message": f"All records for patient '{patient_id}' deleted successfully.",
        "patient_id": patient_id,
        "documents_deleted": deleted,
    }


# ---------------------------------------------------------------------------
# DELETE /patients/{patient_id}/records/{doc_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{patient_id}/records/{doc_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a single record",
    description="Removes a specific document and all its chunks from the patient's records.",
)
async def delete_patient_record(
    patient_id: str,
    doc_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    found = vector_store.delete_document(doc_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found for patient '{patient_id}'.",
        )

    # Evict from both caches, or queries with this document_id keep answering
    # from RAM long after the vectors are gone.
    get_document_cache().invalidate_doc(doc_id)
    get_ollama_context_cache().invalidate_doc(doc_id)

    return {
        "message": f"Document '{doc_id}' deleted successfully.",
        "patient_id": patient_id,
        "doc_id": doc_id,
    }
