from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.repository import DocumentRepository, document_to_response_data
from app.schemas.common import DocumentResponse, DocumentSummary, DocumentType
from app.services.document_processing_service import process_document


router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)

logger = get_logger(__name__)


@router.post("/process", response_model=DocumentResponse)
async def process_uploaded_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    db: Session = Depends(get_db),
):
    """
    Process one uploaded document and persist the latest result by document name.
    """

    logger.info(
        "Processing document: filename=%s, document_type=%s",
        file.filename,
        document_type.value,
    )

    file_bytes = await file.read()

    result = process_document(
        file_name=file.filename or "uploaded_document",
        file_bytes=file_bytes,
        document_type=document_type,
        content_type=file.content_type,
    )

    repository = DocumentRepository(db)

    repository.upsert(
        document_name=result["document_name"],
        document_type=result["document_type"],
        processing_status=result["processing_status"],
        file_validation=result["file_validation"],
        extracted_data=result["extracted_data"],
        financial_validations=result["financial_validations"],
        processing_metadata=result["processing_metadata"],
    )

    return result


@router.get(
    "/{document_name}",
    response_model=DocumentResponse,
)
async def get_document_by_name(
    document_name: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve the latest stored result for a document by name.
    """

    repository = DocumentRepository(db)

    document = repository.get_by_name(document_name)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_name}' not found",
        )

    return document_to_response_data(document)


@router.get(
    "/",
    response_model=List[DocumentSummary],
)
async def list_documents(
    db: Session = Depends(get_db),
) -> List[DocumentSummary]:
    """
    List all processed documents.
    """

    repository = DocumentRepository(db)

    documents = repository.list_all()

    return [
        DocumentSummary(
            document_name=document.document_name,
            document_type=document.document_type,
            processing_status=document.processing_status,
            processed_at=document.processed_at,
        )
        for document in documents
    ]