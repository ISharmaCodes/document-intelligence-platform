"""FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Swagger/OpenAPI docs are available at /docs once running, satisfying the
case study's "Swagger/OpenAPI documentation must be available" requirement
with no extra work.
"""

from __future__ import annotations
from app.db.database import init_db

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import documents, health
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


def create_app() -> FastAPI:
    init_db()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Intelligent Document Extraction, Validation & API Platform -- "
            "AI Engineer Internship case study."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")

    logger.info(
        "Application initialized: environment=%s log_level=%s",
        settings.environment,
        settings.log_level,
    )
    return app


app = create_app()
