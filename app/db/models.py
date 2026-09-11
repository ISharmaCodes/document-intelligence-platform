from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    file_validation_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    extracted_data_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    financial_validations_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    processing_metadata_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )