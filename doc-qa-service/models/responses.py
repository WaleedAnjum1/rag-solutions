"""
Pydantic response schemas for the Document Q&A API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    doc_id: str = Field(description="Unique document identifier (UUID).")
    filename: str = Field(description="Original uploaded filename.")
    namespace: str = Field(description="Namespace the document was indexed into.")
    chunks_count: int = Field(description="Number of text chunks created from the document.")
    message: str = Field(default="Document ingested successfully.")


class SourceChunk(BaseModel):
    chunk_id: str = Field(description="Unique chunk identifier.")
    doc_id: str = Field(description="Parent document ID.")
    filename: str = Field(description="Source filename.")
    text: str = Field(description="Text content of the retrieved chunk.")
    relevance_score: Optional[float] = Field(
        default=None,
        description="Cosine similarity score (0–1, higher is more relevant).",
    )
    page: Optional[int] = Field(default=None, description="Page number (for PDFs).")
    chunk_index: int = Field(description="Index of this chunk within the document.")


class Source(BaseModel):
    id: str = Field(description="Source identifier used in citations.")
    kind: str = Field(description="Kind of document, e.g. report.")
    title: str = Field(description="Title or filename.")
    page: Optional[int] = Field(default=None, description="Page number.")
    url: Optional[str] = Field(default=None, description="URL if applicable.")


class QueryResponse(BaseModel):
    status: str = Field(default="answered")
    answer: str = Field(description="Generated answer from the LLM.")
    document_id: Optional[str] = Field(default=None, description="ID of the primary document.")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation ID.")
    sources: list[Source] = Field(
        default_factory=list,
        description="Simplified sources for citation mapping.",
    )
    notice: str = Field(default="The generated answer is based solely on the provided documents. Ensure you review the original sources for accuracy.")
    
    # Retained for backward compatibility
    question: Optional[str] = Field(default=None)
    namespace: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    namespace: str
    chunks_count: int
    file_type: str
    ingested_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int
    namespace: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = Field(description="Overall service status: 'ok' or 'degraded'.")
    ollama: str = Field(description="Ollama connectivity status.")
    chromadb: str = Field(description="ChromaDB status.")
    embedding_model: str = Field(description="Loaded embedding model name.")
    ollama_model: str = Field(description="Configured Ollama generation model.")
