"""
Application settings loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # Embeddings — multilingual by default so a question in one language can
    # retrieve support content written in another.
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # ChromaDB
    chroma_db_path: str = "./chroma_db"

    # Chunking — FAQ entries and help articles are short; keep chunks small
    # enough that one chunk maps to roughly one answer.
    chunk_size: int = 700
    chunk_overlap: int = 140

    # Retrieval
    top_k: int = 6

    # Ollama generation / KV-context sizing
    num_ctx: int = 8192          # context window — large enough for a long help article
    num_predict: int = 512       # max answer tokens
    max_doc_chunks: int = 20     # chunks fed to the LLM per document

    # Language handling
    # "auto" mirrors the customer's language; a fixed code (e.g. "en") forces
    # every reply into that language regardless of what the customer wrote.
    default_answer_language: str = "auto"
    fallback_language: str = "en"  # used when detection has nothing to go on

    # Escalation — top retrieval score below this marks the answer low-confidence
    # so a human agent reviews it. Scores are cosine similarities remapped to
    # [0,1]; unrelated content lands near 0.4-0.5, so tune per corpus.
    escalation_min_relevance: float = 0.45

    # Server
    host: str = "0.0.0.0"
    port: int = 8300


settings = Settings()
