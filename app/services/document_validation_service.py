from __future__ import annotations
from app.schemas.common import FileValidationStatus

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 3


@dataclass
class FileValidationResult:
    file_name: str
    file_type: str | None
    is_supported: bool
    is_readable: bool
    page_count: int | None
    status: FileValidationStatus
    issues: list[str]


def validate_document(
    file_name: str,
    file_bytes: bytes,
    content_type: str | None = None,
) -> FileValidationResult:
    """
    Validate an uploaded PDF, JPG/JPEG or PNG before processing.

    Validation includes:
    - supported extension
    - non-empty file
    - maximum file size
    - actual PDF/image readability
    - PDF page count <= 3

    The client-provided MIME type is treated only as supplementary
    information. The actual file content is inspected.
    """

    extension = Path(file_name).suffix.lower()

    # 1. Extension check
    if extension not in SUPPORTED_EXTENSIONS:
        return FileValidationResult(
            file_name=file_name,
            file_type=content_type,
            is_supported=False,
            is_readable=False,
            page_count=None,
            status=FileValidationStatus.FAILED,
            issues=["Only PDF, JPG/JPEG and PNG files are supported."],
        )

    # 2. Empty file
    if not file_bytes:
        return FileValidationResult(
            file_name=file_name,
            file_type=MIME_TYPES.get(extension),
            is_supported=True,
            is_readable=False,
            page_count=None,
           status=FileValidationStatus.FAILED,
            issues=["The uploaded file is empty."],
        )

    # 3. File size
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return FileValidationResult(
            file_name=file_name,
            file_type=MIME_TYPES.get(extension),
            is_supported=True,
            is_readable=False,
            page_count=None,
            status=FileValidationStatus.FAILED,
            issues=["File exceeds the maximum allowed size of 10 MB."],
        )

    # 4. PDF validation
    if extension == ".pdf":
        return _validate_pdf(file_name, file_bytes)

    # 5. Image validation
    return _validate_image(file_name, file_bytes)


def _validate_pdf(
    file_name: str,
    file_bytes: bytes,
) -> FileValidationResult:
    try:
        reader = PdfReader(BytesIO(file_bytes))

        page_count = len(reader.pages)

        if page_count == 0:
            return FileValidationResult(
                file_name=file_name,
                file_type="application/pdf",
                is_supported=True,
                is_readable=False,
                page_count=0,
                status=FileValidationStatus.FAILED,
                issues=["PDF contains no pages."],
            )

        if page_count > MAX_PDF_PAGES:
            return FileValidationResult(
                file_name=file_name,
                file_type="application/pdf",
                is_supported=True,
                is_readable=True,
                page_count=page_count,
                status=FileValidationStatus.FAILED,
                issues=[
                    f"PDF contains {page_count} pages. "
                    f"The maximum allowed is {MAX_PDF_PAGES}."
                ],
            )

        # Access each page to catch malformed/corrupted PDFs.
        for page in reader.pages:
            page.mediabox

        return FileValidationResult(
            file_name=file_name,
            file_type="application/pdf",
            is_supported=True,
            is_readable=True,
            page_count=page_count,
            status=FileValidationStatus.PASSED,
            issues=[],
        )

    except Exception:
        return FileValidationResult(
            file_name=file_name,
            file_type="application/pdf",
            is_supported=True,
            is_readable=False,
            page_count=None,
            status=FileValidationStatus.FAILED,
            issues=["The PDF is corrupted or cannot be read."],
        )


def _validate_image(
    file_name: str,
    file_bytes: bytes,
) -> FileValidationResult:
    extension = Path(file_name).suffix.lower()

    try:
        with Image.open(BytesIO(file_bytes)) as image:
            image.verify()

        # Reopen after verify() because verify() invalidates the image object.
        with Image.open(BytesIO(file_bytes)) as image:
            width, height = image.size

        if width <= 0 or height <= 0:
            raise ValueError("Invalid image dimensions.")

        return FileValidationResult(
            file_name=file_name,
            file_type=MIME_TYPES.get(extension),
            is_supported=True,
            is_readable=True,
            page_count=1,
            status=FileValidationStatus.PASSED,
            issues=[],
        )

    except (UnidentifiedImageError, OSError, ValueError):
        return FileValidationResult(
            file_name=file_name,
            file_type=MIME_TYPES.get(extension),
            is_supported=True,
            is_readable=False,
            page_count=None,
            status=FileValidationStatus.FAILED,
            issues=["The image is corrupted or cannot be read."],
        )