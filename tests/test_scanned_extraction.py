from pathlib import Path

import app.services.extraction_service as extraction_service
from app.services.pdf_service import process_pdf


PDF_PATH = Path(
    r"C:\Users\ishas\Downloads\New Dataset 1\New Dataset"
    r"\Balance Sheet\Consolidated Balance Sheet 2022.pdf"
)


def test_scanned_pdf_uses_vision(monkeypatch):
    pdf_bytes = PDF_PATH.read_bytes()

    result = process_pdf(pdf_bytes)

    # Confirm the PDF is actually scanned/image-based.
    assert result.page_count == 1
    assert result.native_text_used is False
    assert result.vision_pages == [1]

    page = result.pages[0]

    assert page.needs_vision is True
    assert page.image_bytes is not None

    # The balance-sheet extraction path currently calls Groq directly,
    # so mock the Groq client instead of _call_vision_model().
    class FakeMessage:
        content = '{"document_type": "balance_sheet", "page_count": 1}'

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeUsage:
        completion_tokens = 10


    class FakeResponse:
      choices = [FakeChoice()]
      usage = FakeUsage()

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        extraction_service,
        "_get_client",
        lambda: FakeClient(),
    )

    extracted = extraction_service.extract_from_image(
        image_bytes=page.image_bytes,
        document_type="balance_sheet",
    )

    assert extracted["document_type"] == "balance_sheet"
    assert extracted["page_count"] == 1