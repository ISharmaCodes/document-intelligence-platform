"""Shared building blocks used by every document-specific schema.

Design notes
------------
- `FieldValue` wraps a single-period value with its page number and
  evidence text, for document types that are not naturally comparative
  (invoices).
- `ComparativeValue` wraps a *current vs. prior period* pair with a single
  shared page/evidence, for the three financial-statement types, which are
  always printed as two-column (current year / prior year) tables in this
  dataset.
- `RowType` lets every line item declare whether it is an atomic component,
  a printed subtotal, or a printed grand total. This is what lets the
  (future) validation layer sum only COMPONENT rows and compare the result
  against a SUBTOTAL/TOTAL row, instead of accidentally summing a subtotal
  together with the rows that produced it.
- `CurrencyInfo` is deliberately conservative: `iso_code` stays `None`
  unless the document gives an unambiguous signal. A bare symbol such as
  "$" is NOT enough evidence to assert "USD" (it could be AUD, CAD, SGD,
  etc.), so the raw symbol and an optional human-readable note are kept
  separately from the ISO code.
- Every "leaf" numeric field is nullable everywhere. Nothing in this
  module invents a value -- absence must always be representable as
  `None`, never as 0 or an empty string.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------------------

class DocumentType(str, Enum):
    INVOICE = "invoice"
    BALANCE_SHEET = "balance_sheet"
    PROFIT_AND_LOSS = "profit_and_loss"
    CASH_FLOW_STATEMENT = "cash_flow_statement"


class RowType(str, Enum):
    """Distinguishes atomic line items from printed subtotal/total rows.

    Used across balance sheet, P&L and cash flow schemas so the validation
    layer never double-counts a subtotal as if it were an independent
    component (correction: subtotal rows must not be summed together with
    their underlying line items).
    """

    COMPONENT = "component"
    SUBTOTAL = "subtotal"
    TOTAL = "total"


class ProcessingStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FileValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------------------
# Value wrappers
# ---------------------------------------------------------------------------------------

class FieldValue(BaseModel):
    """A single extracted value with its provenance.

    Used for document types with one reporting period (invoices).
    """

    value: Optional[Any] = Field(
        default=None, description="The extracted value, or null if not visible/legible."
    )
    page: Optional[int] = Field(
        default=None, description="1-indexed page number the value was read from."
    )
    evidence: Optional[str] = Field(
        default=None,
        description="Short source-text excerpt supporting this value, where practical.",
    )


class ComparativeValue(BaseModel):
    """A current-period vs. prior-period value pair with shared provenance.

    Used throughout the balance sheet, P&L and cash flow schemas, since
    every statement in this dataset is printed as a two-column
    (current year / prior year) table.
    """

    current_value: Optional[float] = Field(default=None)
    prior_value: Optional[float] = Field(default=None)
    page: Optional[int] = Field(default=None)
    evidence: Optional[str] = Field(default=None)


class CurrencyInfo(BaseModel):
    """Conservative currency representation.

    `iso_code` must remain `None` unless the document provides an
    unambiguous signal (e.g. an explicit "USD"/"INR" string, or a symbol
    that is truly unambiguous in context such as "₹" -> INR). A generic
    symbol like "$" alone is NOT sufficient evidence for an ISO code and
    must be left as `raw_symbol` only.
    """

    raw_symbol: Optional[str] = Field(
        default=None, description="Currency symbol or text exactly as printed, e.g. '$', 'RM', '₹'."
    )
    iso_code: Optional[str] = Field(
        default=None,
        description=(
            "ISO 4217 code, populated ONLY when the document makes the currency "
            "unambiguous. Left null for ambiguous symbols (e.g. bare '$')."
        ),
    )
    is_ambiguous: bool = Field(
        default=False,
        description="True when raw_symbol could plausibly map to more than one ISO code.",
    )
    page: Optional[int] = Field(default=None)
    evidence: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------------------

class FileValidationResult(BaseModel):
    status: FileValidationStatus
    issues: List[str] = Field(
        default_factory=list,
        description="Human-readable list of problems found; empty when status is PASSED.",
    )


# ---------------------------------------------------------------------------------------
# Financial validation result (case study §4.4)
# ---------------------------------------------------------------------------------------

class ValidationResult(BaseModel):
    """One deterministic financial-validation check result.

    Produced entirely by Python arithmetic (never by the LLM). `operands`
    holds the named inputs actually used so the evaluator can see exactly
    what was compared.
    """

    name: str = Field(description="Machine-readable check name, e.g. 'grand_total_check'.")
    formula: str = Field(description="Human-readable formula, e.g. 'subtotal + tax == grand_total'.")
    operands: Dict[str, Any] = Field(
        default_factory=dict, description="Named operand values actually used in this check."
    )
    calculated: Optional[float] = None
    reported: Optional[float] = None
    variance: Optional[float] = None
    tolerance: Optional[float] = None
    status: ValidationStatus
    reason: Optional[str] = Field(
        default=None,
        description="Populated when status is NOT_APPLICABLE, explaining which operand was missing.",
    )
    period: Optional[str] = Field(
        default=None,
        description="Which reporting period this check applies to, e.g. 'current' or 'prior', "
        "for document types with comparative columns.",
    )


# ---------------------------------------------------------------------------------------
# Processing metadata + response/error envelopes
# ---------------------------------------------------------------------------------------

class ProcessingMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    processed_at: datetime
    ocr_used: bool = False
    model_used: Optional[str] = None
    page_count: Optional[int] = None
    duration_ms: Optional[int] = None


class DocumentResponse(BaseModel):
    """The single, consistent response envelope for a processed document.

    `extracted_data` is intentionally typed loosely here (as a plain dict)
    to avoid a circular import between this shared module and the four
    document-specific schema modules. The API layer is responsible for
    populating it from the correct typed model (InvoiceExtraction,
    BalanceSheetExtraction, ProfitAndLossExtraction or
    CashFlowExtraction) via `.model_dump()`, so the JSON on the wire is
    still fully structured -- only the Python-side static type is relaxed.
    """

    document_name: str
    document_type: DocumentType
    file_validation: FileValidationResult
    extracted_data: Optional[Dict[str, Any]] = None
    financial_validations: List[ValidationResult] = Field(default_factory=list)
    processing_status: ProcessingStatus
    processing_metadata: ProcessingMetadata
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class DocumentSummary(BaseModel):
    """Lightweight row shape for the dashboard list endpoint."""

    document_name: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    processed_at: datetime


class ErrorResponse(BaseModel):
    """Consistent error body for every failure path in the API."""

    error_code: str
    message: str
    detail: Optional[str] = Field(
        default=None,
        description="Optional additional context. Never includes stack traces or secrets.",
    )
