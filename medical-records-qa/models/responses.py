"""
Pydantic response schemas for the Medical Records Q&A API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    doc_id: str = Field(description="Unique document identifier (UUID).")
    filename: str = Field(description="Original uploaded filename.")
    patient_id: str = Field(description="Patient this record belongs to.")
    record_type: str = Field(description="Category of the medical document.")
    chunks_count: int = Field(description="Number of text chunks created.")
    message: str = Field(default="Medical record ingested successfully.")


class SourceChunk(BaseModel):
    chunk_id: str = Field(description="Unique chunk identifier.")
    doc_id: str = Field(description="Parent document ID.")
    filename: str = Field(description="Source filename.")
    text: str = Field(description="Text content of the retrieved chunk.")
    relevance_score: Optional[float] = Field(
        default=None,
        description="Cosine similarity score (0–1, higher is more relevant).",
    )
    page: Optional[int] = Field(default=None, description="Page number (PDFs only).")
    chunk_index: int = Field(description="Index of this chunk within the document.")
    record_type: Optional[str] = Field(
        default=None,
        description="Category of the source document.",
    )


class Reading(BaseModel):
    name: str = Field(description="Name of the test or reading.")
    value: str = Field(description="Recorded value.")
    unit: str = Field(description="Unit of measurement.")
    reference_range: str = Field(description="Normal or reference range, if provided.")
    result_type: str = Field(description="Type of result, e.g. numeric.")
    status: str = Field(description="Status of the result, e.g. low, normal, high.")
    note: str = Field(description="Any additional notes.")
    source_id: str = Field(description="ID of the source document or chunk.")


class Source(BaseModel):
    id: str = Field(description="Source identifier used in citations.")
    kind: str = Field(description="Kind of document, e.g. report.")
    title: str = Field(description="Title or filename.")
    page: Optional[int] = Field(default=None, description="Page number.")
    url: Optional[str] = Field(default=None, description="URL if applicable.")


class QueryResponse(BaseModel):
    status: str = Field(default="answered")
    answer: str = Field(description="Generated answer grounded in the patient records.")
    document_id: Optional[str] = Field(default=None, description="ID of the primary document.")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation ID.")
    readings: list[Reading] = Field(default_factory=list, description="Extracted laboratory readings.")
    sources: list[Source] = Field(default_factory=list, description="Simplified sources for citation mapping.")
    notice: str = Field(default="Inside a reference range does not prove health, and outside a range does not by itself establish a diagnosis. Seek urgent medical care for severe or rapidly worsening symptoms regardless of these labels.")
    
    # Retained for backward compatibility or extra context
    question: Optional[str] = Field(default=None, description="The original question asked.")
    patient_id: Optional[str] = Field(default=None, description="Patient whose records were queried.")
    model: Optional[str] = Field(default=None, description="Ollama model used for generation.")


class PatientSummaryResponse(BaseModel):
    patient_id: str = Field(description="Patient identifier.")
    summary: str = Field(description="Narrative clinical summary of the patient.")
    conditions: list[str] = Field(
        default_factory=list,
        description="List of diagnosed conditions/diseases found in records.",
    )
    medications: list[str] = Field(
        default_factory=list,
        description="Current medications with dosage and frequency.",
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="Known allergies and adverse reactions.",
    )
    last_visit: Optional[str] = Field(
        default=None,
        description="Date of the most recent clinical encounter found in records.",
    )
    sources: list[SourceChunk] = Field(
        default_factory=list,
        description="Source chunks used to generate this summary.",
    )
    model: str = Field(description="Ollama model used for generation.")


class PatientRecord(BaseModel):
    doc_id: str
    patient_id: str
    filename: str
    record_type: str
    chunks_count: int
    ingested_at: datetime


class PatientRecordListResponse(BaseModel):
    patient_id: str
    records: list[PatientRecord]
    total: int


class PatientListResponse(BaseModel):
    patients: list[str] = Field(description="List of patient IDs with ingested records.")
    total: int


class HealthResponse(BaseModel):
    status: str = Field(description="Overall service status: 'ok' or 'degraded'.")
    ollama: str = Field(description="Ollama connectivity status.")
    chromadb: str = Field(description="ChromaDB status.")
    embedding_model: str = Field(description="Loaded embedding model name.")
    ollama_model: str = Field(description="Configured Ollama generation model.")
