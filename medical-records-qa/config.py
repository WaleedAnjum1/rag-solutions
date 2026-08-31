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

    # Chunking — tighter chunks for higher retrieval precision on medical data
    chunk_size: int = 600
    chunk_overlap: int = 120

    # Retrieval
    top_k: int = 6

    # Ollama generation / KV-context sizing
    num_ctx: int = 8192          # context window — large enough for a multi-page PDF
    num_predict: int = 512       # max answer tokens
    max_doc_chunks: int = 20     # chunks fed to the LLM per document

    # Server
    host: str = "0.0.0.0"
    port: int = 8200


settings = Settings()
