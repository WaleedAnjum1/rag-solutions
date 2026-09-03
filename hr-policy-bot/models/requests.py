"""
Pydantic request schemas for the HR Policy & Onboarding Bot API.
"""

from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field, field_validator

# Recognised HR content categories
DocType = Literal[
    "policy",
    "handbook",
    "sop",
    "onboarding",
    "benefits",
    "compliance",
    "general",
]

# Single source of truth for form-data validation in the ingest router.
DOC_TYPES: frozenset[str] = frozenset(get_args(DocType))

# Tone presets for POST /query/draft-reply
ReplyTone = Literal["friendly", "formal", "concise"]


def _require_text(value: str) -> str:
    """
    Strip surrounding whitespace and reject a value that was only whitespace.

    `min_length` alone counts spaces, so "   " passes it. That matters twice
    here: a blank question would otherwise reach Ollama and burn a generation
    on nothing, and " acme" and "acme" would resolve to two different tenant
    collections — silently splitting one customer's knowledge base in half.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty or whitespace only")
    return stripped


class IngestRequest(BaseModel):
    """Used as form-data companion to the file upload — not sent as JSON body."""
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Company/workspace identifier. Used as the ChromaDB namespace.",
        examples=["acme_corp", "globex-hr"],
    )
    doc_type: DocType = Field(
        default="general",
        description="Category of the uploaded HR document.",
    )
    language: str = Field(
        default="auto",
        description=(
            "Language of the document as a 2-letter code, or 'auto' to detect it. "
            "Stored as metadata so retrieval can optionally be language-filtered."
        ),
        examples=["auto", "en"],
    )

    _clean_tenant = field_validator("tenant_id")(_require_text)


class QueryRequest(BaseModel):
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Company workspace to search HR content in.",
        examples=["acme_corp"],
    )
    question: str = Field(
        ...,
        min_length=3,
        description="Employee question about company policy or HR procedures.",
        examples=["What is the remote work policy?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of content chunks to retrieve for context.",
    )
    stream: bool = Field(
        default=False,
        description="If true, use POST /query/stream for SSE instead.",
    )
    language: Optional[str] = Field(
        default=None,
        description=(
            "Force the reply language (2-letter code). Omit or send 'auto' to "
            "mirror the language the employee wrote in."
        ),
        examples=["auto", "en"],
    )
    doc_type_filter: Optional[DocType] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific HR content category.",
    )
    language_filter: Optional[str] = Field(
        default=None,
        description="Optionally restrict retrieval to source content in one language.",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific document.",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Opaque conversation identifier echoed back in the response.",
    )

    _clean_text = field_validator("tenant_id", "question")(_require_text)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenant_id": "acme_corp",
                    "question": "How many days of PTO do I get per year?",
                    "top_k": 5,
                    "stream": False,
                    "language": "auto",
                    "doc_type_filter": None,
                    "conversation_id": "chat_1234",
                }
            ]
        }
    }


class DraftReplyRequest(BaseModel):
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Company workspace to search HR content in.",
        examples=["acme_corp"],
    )
    message: str = Field(
        ...,
        min_length=3,
        description="The employee's incoming question or message.",
        examples=["What is the process for requesting extended parental leave?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of content chunks to retrieve for context.",
    )
    language: Optional[str] = Field(
        default=None,
        description="Force the draft language. Omit to mirror the employee's language.",
    )
    tone: ReplyTone = Field(
        default="friendly",
        description="Writing style of the drafted reply.",
    )

    _clean_text = field_validator("tenant_id", "message")(_require_text)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenant_id": "acme_corp",
                    "message": "What is the process for requesting extended parental leave?",
                    "top_k": 5,
                    "tone": "friendly",
                }
            ]
        }
    }
