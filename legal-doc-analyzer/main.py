"""
Multi-Language Customer Support Bot — Entry Point

Start with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8300

Swagger UI: http://localhost:8300/docs
ReDoc:       http://localhost:8300/redoc
"""

# ---------------------------------------------------------------------------
# SQLite patch — must run before ANY chromadb import.
# ChromaDB requires sqlite3 >= 3.35.0; Ubuntu 20/22 ships 3.31.
# pysqlite3-binary bundles its own up-to-date SQLite.
# ---------------------------------------------------------------------------
try:
    __import__("pysqlite3")
    import sys as _sys
    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except ImportError:
    pass  # pysqlite3-binary not installed; hope the system sqlite3 is new enough

import logging
import sys
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models.requests import DOC_TYPES, PRACTICE_AREAS
from models.responses import HealthResponse, LanguageInfo, LanguageListResponse, TaxonomyResponse
from routers.ingest import get_vector_store, router as ingest_router
from routers.query import router as query_router
from routers.tenants import router as tenants_router
from routers.analyze import router as analyze_router
from services.embedder import get_embedder
from services.language import SUPPORTED_LANGUAGES

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Warm up the embedding model and verify Ollama connectivity on startup.
    """
    logger.info("═" * 60)
    logger.info("  Multi-Language Customer Support Bot starting…")
    logger.info("  Ollama:    %s  (model: %s)", settings.ollama_base_url, settings.ollama_model)
    logger.info("  Embedder:  %s", settings.embedding_model)
    logger.info("  ChromaDB:  %s", settings.chroma_db_path)
    logger.info("  Languages: %d supported (reply default: %s)",
                len(SUPPORTED_LANGUAGES), settings.default_answer_language)
    logger.info("═" * 60)

    # Pre-load embedding model
    try:
        embedder = get_embedder(settings.embedding_model)
        embedder.embed_one("warmup")
        logger.info("✓ Embedding model ready (dim=%d)", embedder.dimension)
    except Exception as e:
        logger.error("✗ Embedding model failed to load: %s", e)

    # Verify Ollama is reachable
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
        logger.info("✓ Ollama is reachable")
    except Exception as e:
        logger.warning("⚠ Ollama not reachable at startup: %s", e)

    # Load the LLM into memory now. Without this the first real request also
    # pays model load (10-30s) on top of prompt processing. keep_alive=-1 keeps
    # it resident so the KV-context fast path stays warm.
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": "ok",
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_predict": 1},
                },
            )
            resp.raise_for_status()
        logger.info("✓ LLM '%s' loaded and resident", settings.ollama_model)
    except Exception as e:
        logger.warning("⚠ LLM warmup failed (first query will be slower): %s", e)

    # Initialise VectorStore
    get_vector_store()
    logger.info("✓ ChromaDB ready")
    logger.info("✓ Service ready → http://%s:%d/docs", settings.host, settings.port)

    yield  # Application runs here

    logger.info("Multi-Language Customer Support Bot shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Multi-Language Customer Support Bot",
    redirect_slashes=False,
    description=(
        "A RAG-based microservice that ingests a company's support content "
        "(FAQs, help articles, policies, past tickets) and answers customer questions "
        "in their own language using Ollama + ChromaDB.\n\n"
        "Retrieval is **cross-lingual**: a multilingual embedding model puts a Turkish "
        "question and an English help article in the same vector space, so one "
        "knowledge base serves every market without translating it first.\n\n"
        "**Key endpoints:**\n"
        "- `POST /ingest` — upload a support document for a workspace\n"
        "- `POST /query` — answer a customer question in their language\n"
        "- `POST /query/stream` — stream the reply token-by-token (SSE)\n"
        "- `POST /query/draft-reply` — draft a send-ready reply for a human agent\n"
        "- `GET /tenants` — list all workspaces\n"
        "- `GET /tenants/{tenant_id}/documents` — list a workspace's documents\n"
        "- `DELETE /tenants/{tenant_id}` — remove all content for a workspace\n"
        "- `GET /languages` — languages the bot can reply in\n\n"
        "All replies are strictly grounded in ingested content. When the content does "
        "not cover a question, the bot escalates to a human instead of guessing — it "
        "never invents a refund, price, or policy."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(tenants_router)
app.include_router(analyze_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Meta"],
    summary="Service health check",
    description="Returns the status of Ollama, ChromaDB, and the embedding model.",
)
async def health_check() -> HealthResponse:
    # Check Ollama
    ollama_status = "ok"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
    except Exception as e:
        ollama_status = f"unreachable: {e}"

    # Check ChromaDB
    chroma_status = "ok"
    try:
        vs = get_vector_store()
        if not vs.ping():
            chroma_status = "error"
    except Exception as e:
        chroma_status = f"error: {e}"

    # Check embedder
    embedder_status = settings.embedding_model
    try:
        get_embedder(settings.embedding_model)
    except Exception as e:
        embedder_status = f"error: {e}"

    overall = "ok" if ollama_status == "ok" and chroma_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        ollama=ollama_status,
        chromadb=chroma_status,
        embedding_model=embedder_status,
        ollama_model=settings.ollama_model,
    )


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

@app.get(
    "/taxonomy",
    response_model=TaxonomyResponse,
    tags=["Meta"],
    summary="List taxonomy options",
    description="Returns doc types, practice areas, and jurisdictions present in the corpus.",
)
async def get_taxonomy() -> TaxonomyResponse:
    vs = get_vector_store()
    jurisdictions = vs.list_jurisdictions()
    
    return TaxonomyResponse(
        doc_types=sorted(list(DOC_TYPES)),
        practice_areas=sorted(list(PRACTICE_AREAS)),
        jurisdictions=jurisdictions,
    )

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

@app.get(
    "/languages",
    response_model=LanguageListResponse,
    tags=["Meta"],
    summary="List supported reply languages",
    description=(
        "Codes accepted by the `language` and `language_filter` fields, each with a "
        "localised hand-off message for escalations. Useful for building a language "
        "picker in a support widget.\n\n"
        "The underlying model handles more languages than these; this is the set the "
        "service can name and escalate in."
    ),
)
async def list_languages() -> LanguageListResponse:
    languages = [
        LanguageInfo(code=code, name=name)
        for code, name in sorted(SUPPORTED_LANGUAGES.items(), key=lambda kv: kv[1])
    ]
    return LanguageListResponse(
        languages=languages,
        total=len(languages),
        default_answer_language=settings.default_answer_language,
    )


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
