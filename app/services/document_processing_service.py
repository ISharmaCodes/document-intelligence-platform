from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.schemas.common import DocumentType, FileValidationStatus
from app.schemas.invoice import InvoiceExtraction
from app.schemas.balance_sheet import BalanceSheetExtraction
from app.schemas.profit_and_loss import ProfitAndLossExtraction
from app.schemas.cash_flow import CashFlowExtraction
from app.services.document_validation_service import validate_document
from app.services.pdf_service import process_pdf
from app.services.extraction_service import (
    extract_from_image,
    extract_from_text,
)
from app.services.financial_validation_service import (
    validate_financial_document,
)

MODEL_NAME = "qwen/qwen3.6-27b"


def process_document(
    *,
    file_bytes: bytes,
    file_name: str,
    document_type: DocumentType | str,
    content_type: str | None = None,
) -> dict[str, Any]:
    """
    Full document-processing pipeline:

    1. File validation
    2. PDF native-text extraction or vision fallback
    3. Image vision extraction
    4. Structured Pydantic extraction
    5. Deterministic financial validation
    6. Response envelope construction
    """

    started_at = time.perf_counter()

    if hasattr(document_type, "value"):
        document_type = document_type.value

    # ------------------------------------------------------------------
    # 1. FILE VALIDATION
    # ------------------------------------------------------------------

    file_validation = validate_document(
        file_name=file_name,
        file_bytes=file_bytes,
        content_type=content_type,
    )

    file_validation_data = {
        "file_name": file_validation.file_name,
        "file_type": file_validation.file_type,
        "is_supported": file_validation.is_supported,
        "is_readable": file_validation.is_readable,
        "page_count": file_validation.page_count,
        "status": file_validation.status.value,
        "issues": file_validation.issues,
    }

    # IMPORTANT:
    # Enum value is "PASSED", not "passed".
    if file_validation.status != FileValidationStatus.PASSED:
        return {
            "document_name": file_name,
            "document_type": document_type,
            "file_validation": file_validation_data,
            "extracted_data": None,
            "financial_validations": [],
            "processing_status": "FAILED",
            "processing_metadata": {
                "processed_at": _timestamp(),
                "ocr_used": False,
                "model_used": None,
                "page_count": file_validation.page_count,
                "duration_ms": _duration_ms(started_at),
            },
        }

    # ------------------------------------------------------------------
    # 2. EXTRACTION
    # ------------------------------------------------------------------

    try:
        if file_name.lower().endswith(".pdf"):
            pdf_result = process_pdf(file_bytes)

            page_results: list[dict[str, Any]] = []

            for page in pdf_result.pages:

                # ------------------------------------------------------
                # Scanned / image page -> vision model
                # ------------------------------------------------------

                if page.needs_vision:

                    if page.image_bytes is None:
                        raise RuntimeError(
                            f"Vision image was not generated for page "
                            f"{page.page_number}."
                        )

                    extracted = extract_from_image(
                        image_bytes=page.image_bytes,
                        document_type=document_type,
                        mime_type="image/png",
                    )

                # ------------------------------------------------------
                # Native-text page -> text model
                # ------------------------------------------------------

                else:

                    if not page.native_text:
                        raise RuntimeError(
                            f"No usable native text found for page "
                            f"{page.page_number}."
                        )

                    extracted = extract_from_text(
                        text=page.native_text,
                        document_type=document_type,
                        page_number=page.page_number,
                        page_count=pdf_result.page_count,
                    )

                page_results.append(extracted)

            # Merge all PDF pages into one document-level result.
            extracted_data = _merge_page_results(
                page_results=page_results,
                document_type=document_type,
                page_count=pdf_result.page_count,
            )

            ocr_used = bool(pdf_result.vision_pages)
            page_count = pdf_result.page_count

        else:
            # JPG / JPEG / PNG
            extracted_data = extract_from_image(
                image_bytes=file_bytes,
                document_type=document_type,
                mime_type=_guess_mime_type(file_name),
            )

            ocr_used = True
            page_count = 1

        # ------------------------------------------------------------------
        # 3. CONVERT RAW EXTRACTION TO TYPED PYDANTIC MODEL
        # ------------------------------------------------------------------

        extraction_model = _build_extraction_model(
            document_type=document_type,
            extracted_data=extracted_data,
        )

        # Use the validated Pydantic model as the canonical
        # JSON-compatible extraction response.
        extracted_data = extraction_model.model_dump(
            mode="json",
        )

        # ------------------------------------------------------------------
        # 4. DETERMINISTIC FINANCIAL VALIDATION
        # ------------------------------------------------------------------

        financial_validations = validate_financial_document(
            document_type=document_type,
            extracted_data=extraction_model,
        )

        # ------------------------------------------------------------------
        # 4. PROCESSING STATUS
        # ------------------------------------------------------------------

        validation_statuses = [
            validation.get("status")
            for validation in financial_validations
        ]

        # Extraction itself succeeded.
        #
        # A financial FAIL does not mean the document-processing pipeline
        # failed. It means the document contains a financial inconsistency.
        #
        # Therefore:
        #   SUCCESS = extraction completed
        #   PARTIAL = extraction completed but some financial checks failed
        #   FAILED  = processing itself failed
        if any(status == "FAIL" for status in validation_statuses):
            processing_status = "PARTIAL"
        else:
            processing_status = "SUCCESS"

        # ------------------------------------------------------------------
        # 5. FINAL RESPONSE
        # ------------------------------------------------------------------

        return {
            "document_name": file_name,
            "document_type": document_type,
            "file_validation": file_validation_data,
            "extracted_data": extracted_data,
            "financial_validations": financial_validations,
            "processing_status": processing_status,
            "processing_metadata": {
                "processed_at": _timestamp(),
                "ocr_used": ocr_used,
                "model_used": MODEL_NAME,
                "page_count": page_count,
                "duration_ms": _duration_ms(started_at),
            },
        }

    except Exception as exc:
        # Keep the API response clean.
        # Do not expose stack traces or secrets to the client.
        return {
            "document_name": file_name,
            "document_type": document_type,
            "file_validation": file_validation_data,
            "extracted_data": None,
            "financial_validations": [],
            "processing_status": "FAILED",
            "processing_metadata": {
                "processed_at": _timestamp(),
                "ocr_used": False,
                "model_used": MODEL_NAME,
                "page_count": file_validation.page_count,
                "duration_ms": _duration_ms(started_at),
            },
            "error": str(exc),
        }


def _build_extraction_model(
    *,
    document_type: str,
    extracted_data: dict[str, Any],
) -> Any:
    """
    Convert the raw LLM extraction dictionary into the
    appropriate Pydantic extraction model.
    """

    if document_type == DocumentType.INVOICE.value:
        return InvoiceExtraction.model_validate(extracted_data)

    if document_type == DocumentType.BALANCE_SHEET.value:
        return BalanceSheetExtraction.model_validate(extracted_data)

    if document_type == DocumentType.PROFIT_AND_LOSS.value:
        return ProfitAndLossExtraction.model_validate(extracted_data)

    if document_type == DocumentType.CASH_FLOW_STATEMENT.value:
        return CashFlowExtraction.model_validate(extracted_data)

    raise ValueError(
        f"Unsupported document type for extraction model: {document_type}"
    )


# ======================================================================
# PAGE MERGING
# ======================================================================

def _merge_page_results(
    *,
    page_results: list[dict[str, Any]],
    document_type: str,
    page_count: int,
) -> dict[str, Any]:

    if not page_results:
        raise RuntimeError("No extraction result was produced.")

    if len(page_results) == 1:
        result = page_results[0].copy()
        result["page_count"] = page_count
        return result

    merged = page_results[0].copy()

    for page_result in page_results[1:]:
        merged = _merge_page(
            base=merged,
            incoming=page_result,
            document_type=document_type,
        )

    merged["page_count"] = page_count

    return merged


def _merge_page(
    *,
    base: dict[str, Any],
    incoming: dict[str, Any],
    document_type: str,
) -> dict[str, Any]:

    result = base.copy()

    if document_type == "invoice":

        result["line_items"] = _merge_list(
            result.get("line_items"),
            incoming.get("line_items"),
        )

        result["tax_breakdown"] = _merge_list(
            result.get("tax_breakdown"),
            incoming.get("tax_breakdown"),
        )

        result["notes_terms"] = _merge_list(
            result.get("notes_terms"),
            incoming.get("notes_terms"),
        )

        for key in [
            "vendor",
            "buyer",
            "invoice_number",
            "invoice_date",
            "invoice_date_raw",
            "due_date",
            "currency",
            "subtotal",
            "discount_total",
            "shipping_amount",
            "rounding_adjustment",
            "grand_total",
            "amount_paid",
            "amount_due",
            "payment",
            "bank_details",
        ]:
            result[key] = _fill_if_missing(
                result.get(key),
                incoming.get(key),
            )

    elif document_type == "balance_sheet":

        result["capital_and_liabilities"] = _merge_section(
            result.get("capital_and_liabilities"),
            incoming.get("capital_and_liabilities"),
        )

        result["assets"] = _merge_section(
            result.get("assets"),
            incoming.get("assets"),
        )

        result["memo_items"] = _merge_list(
            result.get("memo_items"),
            incoming.get("memo_items"),
        )

        for key in [
            "entity_name",
            "reporting_date",
            "comparative_reporting_date",
            "currency",
            "unit_multiplier_raw_label",
        ]:
            result[key] = _fill_if_missing(
                result.get(key),
                incoming.get(key),
            )

    elif document_type == "profit_and_loss":

        for section_name in [
            "income",
            "expenditure",
            "profit",
            "appropriations",
        ]:
            result[section_name] = _merge_section(
                result.get(section_name),
                incoming.get(section_name),
            )

        for key in [
            "entity_name",
            "period_ended",
            "comparative_period_ended",
            "currency",
            "unit_multiplier_raw_label",
            "earnings_per_share",
        ]:
            result[key] = _fill_if_missing(
                result.get(key),
                incoming.get(key),
            )

    elif document_type == "cash_flow_statement":

        for section_name in [
            "operating_activities",
            "investing_activities",
            "financing_activities",
        ]:
            result[section_name] = _merge_section(
                result.get(section_name),
                incoming.get(section_name),
            )

        result["fx_translation_effect"] = _fill_if_missing(
            result.get("fx_translation_effect"),
            incoming.get("fx_translation_effect"),
        )

        result["cash_reconciliation"] = _merge_dict(
            result.get("cash_reconciliation"),
            incoming.get("cash_reconciliation"),
        )

        for key in [
            "entity_name",
            "period_ended",
            "comparative_period_ended",
            "currency",
            "unit_multiplier_raw_label",
        ]:
            result[key] = _fill_if_missing(
                result.get(key),
                incoming.get(key),
            )

    return result


def _merge_section(
    base: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any] | None:

    if base is None:
        return incoming

    if incoming is None:
        return base

    result = base.copy()

    result["line_items"] = _merge_list(
        result.get("line_items"),
        incoming.get("line_items"),
    )

    for key in [
        "reported_total",
        "net_cash_flow",
        "interest_earned",
        "other_income",
        "interest_expended",
        "operating_expenses",
        "provisions_and_contingencies",
        "net_profit_before_minority_interest",
        "minority_interest",
        "net_profit_attributable_to_group",
        "brought_forward_profit",
    ]:
        if key in incoming:
            result[key] = _fill_if_missing(
                result.get(key),
                incoming.get(key),
            )

    return result


def _merge_dict(
    base: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> dict[str, Any] | None:

    if base is None:
        return incoming

    if incoming is None:
        return base

    result = base.copy()

    for key, value in incoming.items():
        result[key] = _fill_if_missing(
            result.get(key),
            value,
        )

    return result


def _merge_list(
    base: list[Any] | None,
    incoming: list[Any] | None,
) -> list[Any]:

    base = base or []
    incoming = incoming or []

    return base + incoming


def _fill_if_missing(
    base_value: Any,
    incoming_value: Any,
) -> Any:

    if base_value is None:
        return incoming_value

    if isinstance(base_value, dict) and isinstance(incoming_value, dict):
        return _merge_dict(base_value, incoming_value)

    return base_value


# ======================================================================
# HELPERS
# ======================================================================

def _guess_mime_type(file_name: str) -> str:

    lower_name = file_name.lower()

    if lower_name.endswith(".jpg") or lower_name.endswith(".jpeg"):
        return "image/jpeg"

    if lower_name.endswith(".png"):
        return "image/png"

    if lower_name.endswith(".pdf"):
        return "application/pdf"

    return "application/octet-stream"


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)