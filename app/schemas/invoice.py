"""Structured extraction schema for invoices/receipts.

Grounded in direct inspection of the dataset's invoice images, which span
at least four distinct template families (Malaysian GST thermal receipts,
two US-style synthetic invoice templates, a European VAT-per-line
template, and a real photographed Indian GST tax invoice). The schema is
therefore a superset of fields, all nullable, rather than a fixed set
tailored to any one template.

Every leaf value is nullable. Line items are a dynamic array because the
observed column sets differ per template (no two of the sampled templates
shared an identical table schema).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import CurrencyInfo, DocumentType, FieldValue


class PartyInfo(BaseModel):
    """Vendor or buyer identification block."""

    name: Optional[FieldValue] = None
    address: Optional[FieldValue] = None
    tax_id_or_gstin: Optional[FieldValue] = None
    contact: Optional[FieldValue] = None


class InvoiceLineItem(BaseModel):
    """One row of the invoice's item table.

    Not every field applies to every template (e.g. `tax_code` is only
    present on the GST thermal-receipt family; `discount_percent` only on
    templates that show a line-level discount). Unused fields stay null.
    """

    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    tax_rate_percent: Optional[float] = None
    tax_code: Optional[str] = None
    discount_percent: Optional[float] = None
    discount_amount: Optional[float] = None
    line_total: Optional[float] = None
    page: Optional[int] = None
    evidence: Optional[str] = None


class TaxBreakdownRow(BaseModel):
    """One row of a tax summary table.

    Covers single-rate GST, split CGST+SGST, and multi-rate VAT summary
    tables observed in the dataset -- each becomes one row here rather
    than assuming a single fixed tax field.
    """

    tax_type: Optional[str] = Field(
        default=None, description="e.g. 'GST', 'VAT', 'CGST', 'SGST', 'Sales Tax'."
    )
    rate_percent: Optional[float] = None
    taxable_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    page: Optional[int] = None
    evidence: Optional[str] = None


class PaymentInfo(BaseModel):
    cash_tendered: Optional[float] = None
    change_returned: Optional[float] = None


class BankDetails(BaseModel):
    account_no: Optional[str] = None
    bank_name: Optional[str] = None
    branch_or_ifsc: Optional[str] = None


class InvoiceExtraction(BaseModel):
    """Top-level structured extraction result for a single invoice/receipt."""

    document_type: DocumentType = DocumentType.INVOICE
    page_count: Optional[int] = None

    vendor: PartyInfo = Field(default_factory=PartyInfo)
    buyer: PartyInfo = Field(default_factory=PartyInfo)

    invoice_number: Optional[FieldValue] = None
    invoice_date: Optional[FieldValue] = None
    invoice_date_raw_format: Optional[str] = Field(
        default=None,
        description="The date exactly as printed, kept verbatim when the format is "
        "ambiguous (e.g. '07/03/2013') so no incorrect ISO normalization is asserted.",
    )
    due_date: Optional[FieldValue] = None

    currency: Optional[CurrencyInfo] = None

    line_items: List[InvoiceLineItem] = Field(default_factory=list)

    subtotal: Optional[FieldValue] = None
    discount_total: Optional[FieldValue] = None
    tax_breakdown: List[TaxBreakdownRow] = Field(default_factory=list)
    shipping_amount: Optional[FieldValue] = None
    rounding_adjustment: Optional[FieldValue] = None
    grand_total: Optional[FieldValue] = None
    amount_paid: Optional[FieldValue] = None
    amount_due: Optional[FieldValue] = None

    payment: Optional[PaymentInfo] = None
    bank_details: Optional[BankDetails] = None
    notes_terms: Optional[FieldValue] = None
