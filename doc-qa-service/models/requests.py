"""
Pydantic request schemas for the Document Q&A API.
"""

from pydantic import BaseModel, Field, field_validator


def _require_text(value: str) -> str:
    """Strip surrounding whitespace and reject a value that was only whitespace."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty or whitespace only")
    return stripped


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Natural language question to ask against the ingested documents.",
        examples=["What are the payment terms?"],
    )
    namespace: str = Field(
        default="default",
        description="Namespace (collection) to query. Use per-project namespaces for isolation.",
        examples=["udharmaster", "voiceclone", "default"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve for context.",
    )
    stream: bool = Field(
        default=False,
        description="If true, returns a Server-Sent Events stream of tokens.",
    )
    document_id: str | None = Field(
        default=None,
        description="Optionally restrict retrieval to a specific document.",
    )

    _clean_text = field_validator("namespace", "question")(_require_text)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "What are the refund policies?",
                    "namespace": "default",
                    "stream": False,
                    "document_id": "optional_doc_id_here"
                }
            ]
        }
    }
