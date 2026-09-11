"""Health check endpoint (case study §5, GET /api/v1/health)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness/readiness probe.

    Deliberately dependency-free for now (no DB/LLM/OCR calls) since those
    layers are not wired up yet -- this only confirms the API process is
    running and configuration loaded successfully. Once persistence is
    added, extend this to verify DB connectivity as well.
    """
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
    )
