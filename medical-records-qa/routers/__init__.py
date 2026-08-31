"""
Medical Records Q&A — routers package.
"""

from routers.ingest import router as ingest_router, get_vector_store
from routers.query import router as query_router
from routers.patients import router as patients_router

__all__ = [
    "ingest_router",
    "query_router",
    "patients_router",
    "get_vector_store",
]
