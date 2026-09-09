"""
Pydantic response schemas for the Multi-Language Customer Support Bot API.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    doc_id: str = Field(description="Unique document identifier (UUID).")
    filename: str = Field(description="Original uploaded filename.")
    tenant_id: str = Field(description="Workspace this document belongs to.")
    doc_type: str = Field(description="Category of the support document.")
    practice_area: Optional[str] = Field(default=None, description="Practice area.")
    jurisdiction: Optional[str] = Field(default=None, description="Jurisdiction.")
    language: str = Field(description="Language of the document (detected or supplied).")
    language_confidence: Optional[float] = Field(
        default=None,
        description="Detector confidence (0–1). Null when the language was supplied.",
    )
    chunks_count: int = Field(description="Number of text chunks created.")
    message: str = Field(default="Support document ingested successfully.")


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
    doc_type: Optional[str] = Field(
        default=None,
        description="Category of the source document.",
    )
    practice_area: Optional[str] = Field(
        default=None,
        description="Practice area.",
    )
    jurisdiction: Optional[str] = Field(
        default=None,
        description="Jurisdiction.",
    )
    language: Optional[str] = Field(
        default=None,
        description="Language the source content is written in.",
    )


class Source(BaseModel):
    id: str = Field(description="Source identifier used in citations, e.g. 'Source 1'.")
    kind: str = Field(description="Category of the document, e.g. faq.")
    title: str = Field(description="Title or filename.")
    page: Optional[int] = Field(default=None, description="Page number.")
    language: Optional[str] = Field(default=None, description="Language of the source.")
    url: Optional[str] = Field(default=None, description="URL if applicable.")


class QueryResponse(BaseModel):
    status: str = Field(
        default="answered",
        description="'answered' or 'escalated' when a human agent should take over.",
    )
    answer: str = Field(description="Reply grounded in the tenant's support content.")
    answer_language: str = Field(description="Language the answer is written in.")
    detected_language: Optional[str] = Field(
        default=None,
        description="Language detected in the customer's question.",
    )
    language_confidence: Optional[float] = Field(
        default=None,
        description="Detector confidence for `detected_language` (0–1).",
    )
    escalate: bool = Field(
        default=False,
        description="True when a human agent should review or take over.",
    )
    escalation_reason: Optional[str] = Field(
        default=None,
        description="Machine-readable reason: 'no_matching_content', 'not_covered_by_sources', 'low_confidence'.",
    )
    retrieval_score: Optional[float] = Field(
        default=None,
        description="Relevance score of the best retrieved chunk (0–1).",
    )
    document_id: Optional[str] = Field(default=None, description="ID of the primary document.")
    conversation_id: Optional[str] = Field(default=None, description="Echoed conversation ID.")
    sources: list[Source] = Field(
        default_factory=list,
        description="Simplified sources for citation mapping.",
    )
    notice: str = Field(
        default=(
            "General information from this firm's published materials, not legal advice. "
            "It does not create a lawyer-client relationship. Laws vary by jurisdiction "
            "and change over time - speak to a lawyer about your specific situation."
        )
    )

    # Retained for backward compatibility or extra context
    question: Optional[str] = Field(default=None, description="The original question asked.")
    tenant_id: Optional[str] = Field(default=None, description="Workspace that was queried.")
    model: Optional[str] = Field(default=None, description="Ollama model used for generation.")


class DraftReplyResponse(BaseModel):
    tenant_id: str = Field(description="Workspace that was queried.")
    customer_message: str = Field(description="The incoming message the draft answers.")
    draft: str = Field(description="Agent-ready reply draft in the customer's language.")
    language: str = Field(description="Language the draft is written in.")
    detected_language: Optional[str] = Field(
        default=None,
        description="Language detected in the customer's message.",
    )
    tone: str = Field(description="Tone preset used for the draft.")
    escalate: bool = Field(
        default=False,
        description="True when the support content does not cover the request.",
    )
    escalation_reason: Optional[str] = Field(default=None)
    sources: list[SourceChunk] = Field(
        default_factory=list,
        description="Source chunks the draft was grounded in.",
    )
    model: str = Field(description="Ollama model used for generation.")


class SupportDocument(BaseModel):
    doc_id: str
    tenant_id: str
    filename: str
    doc_type: str
    practice_area: Optional[str] = None
    jurisdiction: Optional[str] = None
    language: str
    chunks_count: int
    ingested_at: datetime


class Clause(BaseModel):
    id: str
    clause_number: Optional[str] = None
    heading: Optional[str] = None
    text: str
    clause_type: str
    summary: str
    page: Optional[int] = None


class RiskFlag(BaseModel):
    id: str
    severity: Literal["high", "medium", "low"]
    title: str
    rationale: str
    clause_ref: Optional[str] = None
    source_id: Optional[str] = None


class DocumentBrief(BaseModel):
    doc_id: str
    parties: list[str]
    effective_date: Optional[str] = None
    term: Optional[str] = None
    governing_law: Optional[str] = None
    key_obligations: list[str]
    termination_triggers: list[str]
    unusual_provisions: list[str]


class SupportDocumentListResponse(BaseModel):
    tenant_id: str
    documents: list[SupportDocument]
    total: int


class ClauseDiff(BaseModel):
    clause_type: str
    status: Literal["present_in_a", "present_in_b", "different", "identical"]
    clause_a: Optional[Clause] = None
    clause_b: Optional[Clause] = None
    explanation: Optional[str] = None

class CompareResponse(BaseModel):
    doc_id_a: str
    doc_id_b: str
    differences: list[ClauseDiff]


class TenantListResponse(BaseModel):
    tenants: list[str] = Field(description="Workspace IDs with ingested support content.")
    total: int


class LanguageInfo(BaseModel):
    code: str = Field(description="2-letter language code.")
    name: str = Field(description="English name of the language.")


class LanguageListResponse(BaseModel):
    languages: list[LanguageInfo] = Field(description="Languages the bot can reply in.")
    total: int
    default_answer_language: str = Field(
        description="Configured default: 'auto' mirrors the customer's language."
    )


class HealthResponse(BaseModel):
    status: str = Field(description="Overall service status: 'ok' or 'degraded'.")
    ollama: str = Field(description="Ollama connectivity status.")
    chromadb: str = Field(description="ChromaDB status.")
    embedding_model: str = Field(description="Loaded embedding model name.")
    ollama_model: str = Field(description="Configured Ollama generation model.")


class TaxonomyResponse(BaseModel):
    doc_types: list[str]
    practice_areas: list[str]
    jurisdictions: list[str]
