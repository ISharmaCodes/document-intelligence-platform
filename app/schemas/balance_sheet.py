"""Structured extraction schema for balance sheets.

Grounded in direct inspection of the 10 sample Balance Sheet PDFs
(FY2017-FY2026): all are scanned/image-based, printed as a two-column
(current year / prior year) table split into "Capital and Liabilities"
and "Assets" sections, each ending in a printed Total row. Line items are
NOT identical across years (e.g. "Employees stock options/units
outstanding" and "Policyholders' funds" only appear in later years;
"Goodwill on Consolidation" is absent in some years) -- so line items are
modeled as a dynamic, row-tagged array rather than fixed named fields.

`row_type` on each line item lets the (future) validation layer sum only
COMPONENT rows and compare against the section's reported TOTAL, without
ever double-counting a printed subtotal.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ComparativeValue, CurrencyInfo, DocumentType, FieldValue, RowType


class BalanceSheetLineItem(BaseModel):
    label: Optional[str] = None
    schedule_ref: Optional[str] = Field(
        default=None, description="Schedule number printed alongside the line item, if any."
    )
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    row_type: RowType = RowType.COMPONENT
    page: Optional[int] = None
    evidence: Optional[str] = None


class BalanceSheetSection(BaseModel):
    """One side of the balance sheet (liabilities or assets).

    `line_items` holds every row observed for this section, including any
    row explicitly tagged TOTAL for traceability, but the validation layer
    must sum only rows tagged COMPONENT and compare that sum against
    `reported_total`, not against a TOTAL row found inside `line_items`.
    """

    line_items: List[BalanceSheetLineItem] = Field(default_factory=list)
    reported_total: Optional[ComparativeValue] = None


class BalanceSheetMemoItem(BaseModel):
    """Off-balance-sheet memo rows (e.g. Contingent liabilities, Bills for
    collection) that are printed below the Total but are not part of it."""

    label: Optional[str] = None
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    page: Optional[int] = None
    evidence: Optional[str] = None


class BalanceSheetExtraction(BaseModel):
    """Top-level structured extraction result for a single balance sheet."""

    document_type: DocumentType = DocumentType.BALANCE_SHEET
    page_count: Optional[int] = None

    entity_name: Optional[FieldValue] = None
    reporting_date: Optional[FieldValue] = Field(
        default=None, description="e.g. 'As at March 31, 2023' -- the current-period date."
    )
    comparative_reporting_date: Optional[FieldValue] = None

    currency: Optional[CurrencyInfo] = None
    unit_multiplier_raw_label: Optional[str] = Field(
        default=None,
        description="Unit exactly as printed, e.g. \"₹ in crore\" or \"₹ in '000\". "
        "Kept verbatim rather than pre-converted, since this dataset uses both across years.",
    )

    capital_and_liabilities: BalanceSheetSection = Field(default_factory=BalanceSheetSection)
    assets: BalanceSheetSection = Field(default_factory=BalanceSheetSection)

    memo_items: List[BalanceSheetMemoItem] = Field(default_factory=list)
