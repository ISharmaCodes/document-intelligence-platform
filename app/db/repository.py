import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document


class DocumentRepository:
    """Persistence operations for processed documents."""

    def __init__(self, db: Session):
        self.db = db

    def upsert(
        self,
        document_name: str,
        document_type: str,
        processing_status: str,
        file_validation: dict[str, Any],
        extracted_data: dict[str, Any] | None,
        financial_validations: list[dict[str, Any]],
        processing_metadata: dict[str, Any],
    ) -> Document:
        document = self.get_by_name(document_name)

        if document is None:
            document = Document(
                document_name=document_name,
                document_type=document_type,
            )
            self.db.add(document)

        document.document_type = document_type
        document.processing_status = processing_status
        document.file_validation_json = json.dumps(file_validation)
        document.extracted_data_json = (
            json.dumps(extracted_data)
            if extracted_data is not None
            else None
        )
        document.financial_validations_json = json.dumps(
            financial_validations
        )
        document.processing_metadata_json = json.dumps(
            processing_metadata
        )

        self.db.commit()
        self.db.refresh(document)

        return document

    def get_by_name(self, document_name: str) -> Document | None:
        statement = select(Document).where(
            Document.document_name == document_name
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_all(self) -> list[Document]:
        statement = select(Document).order_by(
            Document.processed_at.desc()
        )
        return list(self.db.execute(statement).scalars().all())


def document_to_response_data(document: Document) -> dict[str, Any]:
    """Convert a database record back into API response data."""

    return {
        "document_name": document.document_name,
        "document_type": document.document_type,
        "file_validation": json.loads(document.file_validation_json),
        "extracted_data": (
            json.loads(document.extracted_data_json)
            if document.extracted_data_json
            else None
        ),
        "financial_validations": json.loads(
            document.financial_validations_json
        ),
        "processing_status": document.processing_status,
        "processing_metadata": json.loads(
            document.processing_metadata_json
        ),
    }