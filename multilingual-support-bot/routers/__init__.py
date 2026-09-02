"""
Multi-Language Customer Support Bot — routers package.
"""

from routers.ingest import get_vector_store, router as ingest_router
from routers.query import router as query_router
from routers.tenants import router as tenants_router

__all__ = [
    "ingest_router",
    "query_router",
    "tenants_router",
    "get_vector_store",
]
