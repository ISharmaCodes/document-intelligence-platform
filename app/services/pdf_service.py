from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pymupdf
from pypdf import PdfReader


NATIVE_TEXT_THRESHOLD = 50
RENDER_DPI = 200


@dataclass
class PDFPageContent:
    page_number: int
    native_text: str | None
    needs_vision: bool
    image_bytes: bytes | None


@dataclass
class PDFProcessingResult:
    page_count: int
    pages: list[PDFPageContent]
    native_text_used: bool
    vision_pages: list[int]


def process_pdf(file_bytes: bytes) -> PDFProcessingResult:
    """
    Process a PDF using a native-text-first strategy.

    For each page:
    1. Attempt native text extraction.
    2. If meaningful text is below the threshold, render the page
       as an image for the vision extraction path.
    """

    reader = PdfReader(BytesIO(file_bytes))

    page_count = len(reader.pages)
    pages: list[PDFPageContent] = []
    vision_pages: list[int] = []
    native_text_used = False

    # Open the PDF with PyMuPDF for rendering.
    pdf_document = pymupdf.open(stream=file_bytes, filetype="pdf")

    try:
        for index, page in enumerate(reader.pages):
            page_number = index + 1

            # --------------------------------------------------
            # 1. Try native text extraction
            # --------------------------------------------------
            try:
                native_text = page.extract_text() or ""
            except Exception:
                native_text = ""

            meaningful_text = " ".join(native_text.split())

            # --------------------------------------------------
            # 2. Decide whether vision rendering is required
            # --------------------------------------------------
            needs_vision = len(meaningful_text) < NATIVE_TEXT_THRESHOLD

            image_bytes = None

            if needs_vision:
                vision_pages.append(page_number)

                image_bytes = _render_page(
                    pdf_document,
                    index,
                )
            else:
                native_text_used = True

            pages.append(
                PDFPageContent(
                    page_number=page_number,
                    native_text=(
                        native_text
                        if meaningful_text
                        else None
                    ),
                    needs_vision=needs_vision,
                    image_bytes=image_bytes,
                )
            )

    finally:
        pdf_document.close()

    return PDFProcessingResult(
        page_count=page_count,
        pages=pages,
        native_text_used=native_text_used,
        vision_pages=vision_pages,
    )


def _render_page(
    pdf_document: pymupdf.Document,
    page_index: int,
) -> bytes:
    """
    Render one PDF page to PNG bytes.

    200 DPI is a reasonable balance between readability,
    image size and processing cost.
    """

    page = pdf_document.load_page(page_index)

    zoom = RENDER_DPI / 72
    matrix = pymupdf.Matrix(zoom, zoom)

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    return pixmap.tobytes("png")