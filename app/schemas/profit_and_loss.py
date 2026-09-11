"""Structured extraction schema for Profit & Loss statements.

Grounded in direct inspection of the 10 sample P&L PDFs (FY2017-FY2026),
consistently structured as: I INCOME, II EXPENDITURE, III PROFIT,
IV APPROPRIATIONS, V EARNINGS PER SHARE, each comparative (current/prior
year) and each ending in a printed Total row. Exact row wording shifts by
year (e.g. "Net profit for the year" vs. "Consolidated Net Profit for the
year before minorities' interest"), so in addition to the generic,
dynamic `line_items` array (for full display/evidence coverage), this
schema exposes explicit, named fields for the specific figures the case
study's required formulas operate on:

    Interest Earned + Other Income                      ~= Total Income
    Interest Expended + Operating Expenses
        + Provisions & Contingencies                    ~= Total Expenditure
    Total Income - Total Expenditure                     ~= Net Profit before Minority Interest
    Net Profit before Minority Interest - Minority Interest ~= Net Profit attributable to Group

Keeping these as explicit fields (rather than requiring the validation
layer to fuzzy-match line-item labels, which vary by year) is what makes
the exact formulas in the case study directly and reliably computable.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ComparativeValue, CurrencyInfo, DocumentType, FieldValue, RowType


class PnlLineItem(BaseModel):
    """Generic row for full-completeness extraction/display purposes.

    This captures every visible row (including ones not directly needed by
    the mandated formulas, e.g. individual appropriation transfers) with
    evidence/page, independent of the explicit named fields below.
    """

    label: Optional[str] = None
    schedule_ref: Optional[str] = None
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    row_type: RowType = RowType.COMPONENT
    page: Optional[int] = None
    evidence: Optional[str] = None


class IncomeSection(BaseModel):
    """Section I - INCOME.

    Explicit fields back the mandated
    `Interest Earned + Other Income ~= Total Income` check.
    """

    interest_earned: Optional[ComparativeValue] = None
    other_income: Optional[ComparativeValue] = None
    reported_total: Optional[ComparativeValue] = None
    line_items: List[PnlLineItem] = Field(default_factory=list)


class ExpenditureSection(BaseModel):
    """Section II - EXPENDITURE.

    Explicit fields back the mandated
    `Interest Expended + Operating Expenses + Provisions & Contingencies
    ~= Total Expenditure` check.
    """

    interest_expended: Optional[ComparativeValue] = None
    operating_expenses: Optional[ComparativeValue] = None
    provisions_and_contingencies: Optional[ComparativeValue] = None
    reported_total: Optional[ComparativeValue] = None
    line_items: List[PnlLineItem] = Field(default_factory=list)


class ProfitSection(BaseModel):
    """Section III - PROFIT.

    Explicit fields back the two mandated checks that connect Income,
    Expenditure and Minority Interest:
        Total Income - Total Expenditure ~= net_profit_before_minority_interest
        net_profit_before_minority_interest - minority_interest
            ~= net_profit_attributable_to_group
    """

    net_profit_before_minority_interest: Optional[ComparativeValue] = Field(
        default=None,
        description="e.g. 'Net profit for the year' / 'Consolidated Net Profit for the "
        "year before minorities' interest' -- wording varies by year, concept does not.",
    )
    minority_interest: Optional[ComparativeValue] = None
    net_profit_attributable_to_group: Optional[ComparativeValue] = None
    brought_forward_profit: Optional[ComparativeValue] = None
    reported_total: Optional[ComparativeValue] = None
    line_items: List[PnlLineItem] = Field(default_factory=list)


class AppropriationsSection(BaseModel):
    """Section IV - APPROPRIATIONS (transfers to reserves, dividends, etc.)."""

    reported_total: Optional[ComparativeValue] = None
    line_items: List[PnlLineItem] = Field(default_factory=list)


class EarningsPerShare(BaseModel):
    face_value: Optional[float] = None
    basic_current: Optional[float] = None
    basic_prior: Optional[float] = None
    diluted_current: Optional[float] = None
    diluted_prior: Optional[float] = None
    page: Optional[int] = None
    evidence: Optional[str] = None


class ProfitAndLossExtraction(BaseModel):
    """Top-level structured extraction result for a single P&L statement."""

    document_type: DocumentType = DocumentType.PROFIT_AND_LOSS
    page_count: Optional[int] = None

    entity_name: Optional[FieldValue] = None
    period_ended: Optional[FieldValue] = None
    comparative_period_ended: Optional[FieldValue] = None

    currency: Optional[CurrencyInfo] = None
    unit_multiplier_raw_label: Optional[str] = None

    income: IncomeSection = Field(default_factory=IncomeSection)
    expenditure: ExpenditureSection = Field(default_factory=ExpenditureSection)
    profit: ProfitSection = Field(default_factory=ProfitSection)
    appropriations: AppropriationsSection = Field(default_factory=AppropriationsSection)
    earnings_per_share: Optional[EarningsPerShare] = None
