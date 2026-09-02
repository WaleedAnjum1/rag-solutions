"""
Multi-Language Customer Support Bot — services package.
"""

from services.document_loader import TextChunk, load_and_chunk
from services.embedder import Embedder, get_embedder
from services.language import (
    SUPPORTED_LANGUAGES,
    detect_language,
    is_supported,
    language_name,
    localized_refusal,
    normalize_code,
)
from services.rag_chain import SupportRAGChain
from services.vectorstore import VectorStore, generate_doc_id

__all__ = [
    "TextChunk",
    "load_and_chunk",
    "Embedder",
    "get_embedder",
    "SUPPORTED_LANGUAGES",
    "detect_language",
    "is_supported",
    "language_name",
    "localized_refusal",
    "normalize_code",
    "SupportRAGChain",
    "VectorStore",
    "generate_doc_id",
]
