"""
Pydantic request schemas for the Multi-Language Customer Support Bot API.
"""

from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field, field_validator

# Recognised legal document categories
DocType = Literal[
    "statute", "case_law", "regulation",
    "legal_guide", "faq", "firm_policy",
    "contract", "nda", "lease",
    "employment_agreement", "court_filing", "general",
]

PracticeArea = Literal[
    "family",
    "child_welfare",
    "property",
    "corporate",
    "employment", "criminal", "civil", "tax", "general",
]

# Single source of truth for form-data validation in the ingest router.
DOC_TYPES: frozenset[str] = frozenset(get_args(DocType))
PRACTICE_AREAS: frozenset[str] = frozenset(get_args(PracticeArea))

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
        description="Workspace/brand identifier. Used as the ChromaDB namespace.",
        examples=["acme_saas", "telco-eu"],
    )
    doc_type: DocType = Field(
        default="general",
        description="Category of the uploaded support document.",
    )
    language: str = Field(
        default="auto",
        description=(
            "Language of the document as a 2-letter code, or 'auto' to detect it. "
            "Stored as metadata so retrieval can optionally be language-filtered."
        ),
        examples=["auto", "en", "es"],
    )
    practice_area: Optional[PracticeArea] = Field(
        default=None,
        description="Legal practice area of the document.",
    )
    jurisdiction: Optional[str] = Field(
        default=None,
        description="Jurisdiction (e.g., 'PK', 'AE'). Regex validated during ingest.",
    )

    _clean_tenant = field_validator("tenant_id")(_require_text)


class QueryRequest(BaseModel):
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Workspace whose support content to search.",
        examples=["acme_saas"],
    )
    question: str = Field(
        ...,
        min_length=3,
        description="Customer question in any supported language.",
        examples=["¿Cuánto tarda un reembolso?"],
    )
    top_k: int = Field(
        default=6,
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
            "mirror the language the customer wrote in."
        ),
        examples=["auto", "de"],
    )
    doc_type_filter: Optional[DocType] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific content category.",
    )
    language_filter: Optional[str] = Field(
        default=None,
        description=(
            "Optionally restrict retrieval to source content in one language. "
            "Leave unset for cross-lingual retrieval (the default and usually best)."
        ),
    )
    practice_area_filter: Optional[PracticeArea] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific practice area.",
    )
    jurisdiction_filter: Optional[str] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific jurisdiction.",
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
                    "tenant_id": "acme_saas",
                    "question": "¿Cuánto tarda un reembolso?",
                    "top_k": 6,
                    "stream": False,
                    "language": "auto",
                    "doc_type_filter": None,
                    "conversation_id": "chat_7781",
                }
            ]
        }
    }


class DraftReplyRequest(BaseModel):
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Workspace whose support content to search.",
        examples=["acme_saas"],
    )
    message: str = Field(
        ...,
        min_length=3,
        description="The customer's incoming message (email or chat).",
        examples=["Merhaba, siparişim iki haftadır gelmedi. Ne yapmalıyım?"],
    )
    top_k: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Number of content chunks to retrieve for context.",
    )
    language: Optional[str] = Field(
        default=None,
        description="Force the draft language. Omit to mirror the customer.",
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
                    "tenant_id": "acme_saas",
                    "message": "Merhaba, siparişim iki haftadır gelmedi. Ne yapmalıyım?",
                    "top_k": 6,
                    "tone": "friendly",
                }
            ]
        }
    }
