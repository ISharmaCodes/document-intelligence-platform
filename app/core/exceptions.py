"""Custom exceptions and their mapping to safe, structured HTTP responses.

Per the case study's non-functional requirements, the application must
"fail gracefully without exposing stack traces or secrets to end users."
The pattern used here is:

    1. Internal code raises a specific AppException subclass.
    2. A registered FastAPI exception handler converts it into the shared
       ErrorResponse schema (see app/schemas/common.py) with the right
       HTTP status code.
    3. The full exception (including traceback) is logged server-side only.
    4. Any *unexpected* exception is caught by a catch-all handler that
       returns a generic 500 message -- never the raw exception text.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.schemas.common import ErrorResponse

logger = get_logger(__name__)


class AppException(Exception):
    """Base class for all handled application errors.

    Attributes:
        message: Safe, user-facing message (never includes internals).
        status_code: HTTP status code to return.
        error_code: Short machine-readable code for API consumers.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


# --- File validation errors (case study §4.1) ------------------------------------------

class FileValidationError(AppException):
    """Base class for problems detected during input-control validation."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "file_validation_error"


class UnsupportedFileTypeError(FileValidationError):
    error_code = "unsupported_file_type"


class EmptyOrCorruptedFileError(FileValidationError):
    error_code = "empty_or_corrupted_file"


class PageLimitExceededError(FileValidationError):
    error_code = "page_limit_exceeded"


# --- Processing errors (extraction phase, wired in later) -------------------------------

class ExtractionError(AppException):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "extraction_error"


class ModelTimeoutError(ExtractionError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "model_timeout"


# --- Persistence / lookup errors (database phase, wired in later) -----------------------

class DocumentNotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "document_not_found"


class PersistenceError(AppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "persistence_error"


# --- Not-yet-implemented marker ----------------------------------------------------------

class NotImplementedYetError(AppException):
    """Raised by scaffold endpoints that are intentionally stubbed out.

    This keeps the route signatures, request/response shapes and Swagger
    documentation real and reviewable now, while being explicit that the
    underlying logic is a later phase of the 2-day plan -- not a bug.
    """

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    error_code = "not_implemented"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app instance."""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "Handled application error: %s (%s) on %s %s",
            exc.error_code,
            exc.message,
            request.method,
            request.url.path,
        )
        body = ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            detail=exc.detail,
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to the server log only -- never to the client.
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        body = ErrorResponse(
            error_code="internal_error",
            message="An unexpected error occurred while processing the request.",
            detail=None,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(),
        )
