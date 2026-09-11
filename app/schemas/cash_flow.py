"""Structured extraction schema for Cash Flow Statements.

Grounded in direct inspection of the 10 sample Cash Flow PDFs
(FY2017-FY2026; 9 image-based, 1 -- FY2022 -- with a native text layer
confirmed by direct extraction). Structure observed: Operating, Investing
and Financing activity sections, each containing an internal subtotal
(e.g. the "70,780.55" line after the depreciation/provision add-backs,
before the working-capital adjustments block) as well as a final printed
net-cash-flow line for the section. A separate "Effect of exchange
fluctuation on translation reserve" line sits between the financing
section and the opening/closing cash reconciliation.

`row_type` is critical here: each activities section contains BOTH
component rows and one or more internal SUBTOTAL rows before its final
TOTAL (net cash flow) line. The validation layer must sum only COMPONENT
rows -- never a SUBTOTAL together with the rows that produced it -- when
checking a section's total, to avoid double-counting.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ComparativeValue, CurrencyInfo, DocumentType, FieldValue, RowType


class CashFlowLineItem(BaseModel):
    label: Optional[str] = None
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    row_type: RowType = Field(
        default=RowType.COMPONENT,
        description="COMPONENT for an individual adjustment/activity line, SUBTOTAL for an "
        "internal running subtotal (e.g. before working-capital adjustments), TOTAL for the "
        "section's final net-cash-flow line.",
    )
    page: Optional[int] = None
    evidence: Optional[str] = None


class CashFlowActivitySection(BaseModel):
    """One of Operating / Investing / Financing activities.

    `net_cash_flow` is the section's own explicit printed total (e.g. "Net
    cash flow (used in)/from operating activities"), kept separate from
    `line_items` so the validation layer has one unambiguous target to
    check the sum of COMPONENT rows against.
    """

    line_items: List[CashFlowLineItem] = Field(default_factory=list)
    net_cash_flow: Optional[ComparativeValue] = None


class CashReconciliation(BaseModel):
    opening_cash: Optional[ComparativeValue] = None
    net_change_in_cash: Optional[ComparativeValue] = None
    closing_cash: Optional[ComparativeValue] = None


class CashFlowExtraction(BaseModel):
    """Top-level structured extraction result for a single cash flow statement."""

    document_type: DocumentType = DocumentType.CASH_FLOW_STATEMENT
    page_count: Optional[int] = None

    entity_name: Optional[FieldValue] = None
    period_ended: Optional[FieldValue] = None
    comparative_period_ended: Optional[FieldValue] = None

    currency: Optional[CurrencyInfo] = None
    unit_multiplier_raw_label: Optional[str] = None

    operating_activities: CashFlowActivitySection = Field(default_factory=CashFlowActivitySection)
    investing_activities: CashFlowActivitySection = Field(default_factory=CashFlowActivitySection)
    financing_activities: CashFlowActivitySection = Field(default_factory=CashFlowActivitySection)

    fx_translation_effect: Optional[ComparativeValue] = Field(
        default=None,
        description="'Effect of exchange fluctuation on translation reserve' -- a distinct "
        "line sitting between financing activities and the cash reconciliation; must not be "
        "folded into financing_activities.",
    )

    cash_reconciliation: CashReconciliation = Field(default_factory=CashReconciliation)
