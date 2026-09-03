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

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # ChromaDB
    chroma_db_path: str = "./chroma_db"

    # Chunking — HR policy documents and handbook sections can be longer;
    # slightly larger chunks help preserve policy context within one chunk.
    chunk_size: int = 800
    chunk_overlap: int = 150

    # Retrieval
    top_k: int = 5

    # Ollama generation / KV-context sizing
    num_ctx: int = 8192      # context window — large enough for a full policy section
    num_predict: int = 512   # max answer tokens
    max_doc_chunks: int = 20 # chunks fed to the LLM per document

    # Escalation — top retrieval score below this marks the answer low-confidence
    # so a human HR rep reviews it. Scores are cosine similarities remapped to
    # [0,1]; unrelated content lands near 0.4-0.5, so tune per corpus.
    escalation_min_relevance: float = 0.45

    # Server
    host: str = "0.0.0.0"
    port: int = 8400


settings = Settings()
