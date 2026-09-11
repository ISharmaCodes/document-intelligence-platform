from pathlib import Path

import app.services.extraction_service as extraction_service
from app.services.pdf_service import process_pdf


PDF_PATH = Path(
    r"C:\Users\ishas\Downloads\New Dataset 1\New Dataset\Cash Flows\Consolidated Cash Flow Statement 2022.pdf"
)


def test_native_text_extraction(monkeypatch):
    pdf_bytes = PDF_PATH.read_bytes()

    result = process_pdf(pdf_bytes)

    assert result.native_text_used is True
    assert len(result.pages) == 1
    assert result.pages[0].native_text

    def fake_llm(
        prompt: str,
        *,
        image_bytes=None,
        mime_type: str = "image/png",
        max_completion_tokens: int = 2200,
    ):
        return {
            "document_type": "cash_flow_statement",
            "page_count": 1,
            "entity_name": {
                "value": "Test Entity",
                "page": 1,
                "evidence": "Test Entity",
            },
        }

    monkeypatch.setattr(
        extraction_service,
        "_call_llm",
        fake_llm,
    )

    extracted = extraction_service.extract_from_text(
        text=result.pages[0].native_text,
        document_type="cash_flow_statement",
        page_number=result.pages[0].page_number,
        page_count=result.page_count,
    )

    assert extracted["document_type"] == "cash_flow_statement"