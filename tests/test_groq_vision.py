from pathlib import Path
import json

from app.services.extraction_service import extract_from_image


IMAGE_PATH = Path(
    r"C:\Users\ishas\Downloads\New Dataset 1\New Dataset\Invoices\batch1-1109.jpg  "
)


def main():
    result = extract_from_image(
        image_bytes=IMAGE_PATH.read_bytes(),
        document_type="invoice",
        mime_type="image/jpeg",
    )

    print("\n--- EXTRACTION SERVICE RESPONSE ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()