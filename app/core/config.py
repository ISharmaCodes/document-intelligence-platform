"""Centralized application configuration.

All configurable values are read from environment variables (optionally via
a local .env file during development). Nothing here is hardcoded to a
specific deployment target so the same code runs locally and on whatever
free-tier host is chosen later.

No secrets have real default values -- see .env.example for the full list
of variables an operator must supply.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Document Intelligence Platform.

    Fields are intentionally grouped by concern (app, files, LLM, OCR,
    database, CORS) so future contributors can find the right knob quickly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General application settings -------------------------------------------------
    app_name: str = Field(default="Document Intelligence Platform")
    environment: Literal["local", "development", "production"] = Field(default="local")
    log_level: str = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # --- File validation limits (case-study §3 / §4.1) ---------------------------------
    max_file_size_mb: int = Field(default=10)
    max_page_count: int = Field(default=3)
    allowed_content_types: List[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/jpeg",
            "image/png",
        ]
    )

    # --- LLM / extraction provider (used by the extraction layer, not yet implemented) -
    llm_provider: Literal["anthropic", "openai", "none"] = Field(default="none")
    llm_api_key: str = Field(default="")
    llm_model_name: str = Field(default="")
    llm_request_timeout_seconds: int = Field(default=60)

    # --- OCR provider (optional corroboration path, not yet implemented) ---------------
    ocr_provider: Literal["none", "tesseract", "ocr_space"] = Field(default="none")
    ocr_space_api_key: str = Field(default="")

    # --- Persistence (database wiring comes in a later phase) --------------------------
    database_url: str = Field(default="sqlite:///./document_intelligence.db")

    # --- CORS (frontend, added in a later phase) ----------------------------------------
    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"])

    @field_validator("allowed_content_types", "cors_allow_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        """Allow comma-separated strings in .env to become a list.

        e.g. ALLOWED_CONTENT_TYPES=application/pdf,image/jpeg,image/png
        """
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Using lru_cache means the .env file is only parsed once per process,
    while still being easy to override in tests via dependency overrides.
    """
    return Settings()
