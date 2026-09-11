from pathlib import Path

from app.services.pdf_service import process_pdf


NATIVE_TEXT_PDF = Path(
    r"C:\Users\ishas\Downloads\New Dataset 1\New Dataset\Cash Flows\Consolidated Cash Flow Statement 2022.pdf"
)

SCANNED_PDF = Path(
    r"C:\Users\ishas\Downloads\New Dataset 1\New Dataset\Balance Sheet\Consolidated Balance Sheet 2022.pdf"
)

def inspect_pdf(label: str, path: Path):
    print(f"\n--- {label} ---")
    print(f"File: {path.name}")

    result = process_pdf(path.read_bytes())

    print(f"Pages: {result.page_count}")
    print(f"Native text used: {result.native_text_used}")
    print(f"Vision pages: {result.vision_pages}")

    for page in result.pages:
        text_length = len(page.native_text or "")

        print(
            f"Page {page.page_number}: "
            f"text_chars={text_length}, "
            f"needs_vision={page.needs_vision}, "
            f"image_created={page.image_bytes is not None}"
        )


if __name__ == "__main__":
    inspect_pdf("Native-text test", NATIVE_TEXT_PDF)
    inspect_pdf("Scanned PDF test", SCANNED_PDF)