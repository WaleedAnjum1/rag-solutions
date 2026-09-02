"""
Pydantic request schemas for the Medical Records Q&A API.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Recognised medical record categories
RecordType = Literal[
    "lab_report",
    "prescription",
    "discharge_summary",
    "imaging",
    "consultation_note",
    "general",
]


def _require_text(value: str) -> str:
    """Strip surrounding whitespace and reject a value that was only whitespace."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty or whitespace only")
    return stripped


class IngestRequest(BaseModel):
    """Used as form-data companion to the file upload — not sent as JSON body."""
    patient_id: str = Field(
        ...,
        min_length=1,
        description="Unique patient identifier. Used as the ChromaDB namespace.",
        examples=["patient_001", "PT-2024-00123"],
    )
    record_type: RecordType = Field(
        default="general",
        description="Category of the uploaded medical document.",
    )

    _clean_text = field_validator("patient_id")(_require_text)


class QueryRequest(BaseModel):
    patient_id: str = Field(
        ...,
        min_length=1,
        description="Patient whose records to query.",
        examples=["patient_001"],
    )
    question: str = Field(
        ...,
        min_length=3,
        description="Natural language clinical question.",
        examples=["What medications is this patient currently on?"],
    )
    top_k: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve for context.",
    )
    stream: bool = Field(
        default=False,
        description="If true, use POST /query/stream for SSE instead.",
    )
    record_type_filter: Optional[RecordType] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific record category.",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Optionally restrict retrieval to a specific document.",
    )

    _clean_text = field_validator("patient_id", "question")(_require_text)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "patient_id": "patient_001",
                    "question": "What were the last recorded blood pressure values?",
                    "stream": False,
                    "record_type_filter": None,
                    "document_id": "optional_doc_id_here"
                }
            ]
        }
    }


class SummaryRequest(BaseModel):
    patient_id: str = Field(
        ...,
        min_length=1,
        description="Patient whose records to summarise.",
        examples=["patient_001"],
    )
    top_k: int = Field(
        default=8,
        ge=1,
        le=20,
        description=(
            "Number of chunks to retrieve for summary generation. "
            "Keep low (8) on CPU-only hardware. Increase only with GPU inference."
        ),
    )

    _clean_text = field_validator("patient_id")(_require_text)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "patient_id": "patient_001",
                    "top_k": 15,
                }
            ]
        }
    }
