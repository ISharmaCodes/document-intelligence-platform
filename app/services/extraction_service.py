from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Type

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ValidationError

from app.schemas.invoice import InvoiceExtraction
from app.schemas.balance_sheet import BalanceSheetExtraction
from app.schemas.profit_and_loss import ProfitAndLossExtraction
from app.schemas.cash_flow import CashFlowExtraction

load_dotenv()

MODEL_NAME = "qwen/qwen3.6-27b"
logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when document extraction fails."""


SCHEMA_MODELS: dict[str, Type[BaseModel]] = {
    "invoice": InvoiceExtraction,
    "balance_sheet": BalanceSheetExtraction,
    "profit_and_loss": ProfitAndLossExtraction,
    "cash_flow_statement": CashFlowExtraction,
}


def _get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ExtractionError("GROQ_API_KEY is not configured.")

    return Groq(api_key=api_key)


def _image_to_data_url(
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _build_prompt(document_type: str) -> str:
    prompts = {
      "invoice": """
You are an expert document extraction system.

Read the ENTIRE invoice image carefully before producing the JSON.

Extract ALL meaningful information that is visibly present.

IMPORTANT RULES:

1. NEVER invent information.
   If a value is genuinely not visible, return null.

2. Extract PRINTED values even if they could also be calculated.

3. For extracted values, preserve:
   - page = 1
   - evidence = short text from the image proving the value

4. VENDOR:
   Look for Seller, Vendor, Supplier, From, Sold By, Company.
   Extract name, address, tax ID and contact when visible.

5. BUYER:
   Look for Client, Customer, Buyer, Bill To, Billed To.
   Extract name, address, tax ID and contact when visible.

6. INVOICE NUMBER:
   Look for Invoice No, Invoice Number, Invoice #, Reference or Bill No.

7. DATES:
   Extract the printed date.
   invoice_date_raw_format MUST be a plain string containing the original
   printed date, such as "07/03/2013".

8. CURRENCY:
   Preserve the printed currency symbol/text.
   Do NOT automatically assume "$" means USD.
   Only set iso_code when the document provides enough evidence.
   Otherwise use:
       iso_code = null
       is_ambiguous = true

9. LINE ITEMS:
   Extract EVERY visible line item separately.

   Read the COMPLETE row from left to right.

   Extract:
   - description
   - quantity
   - unit
   - unit_price
   - tax_rate_percent
   - tax_code
   - discount_percent
   - discount_amount
   - line_total

   Example:

   "1. B0028NAO6C Shoeless Joe 5,00 each 3,49 17,45 10% 19,20"

   This may represent:

   quantity = 5
   unit = "each"
   unit_price = 3.49
   tax_rate_percent = 10
   line_total = 19.20

   The COMPLETE row should be included in evidence.

   Do NOT leave quantity, tax rate or line_total null when clearly
   visible in the row.

10. NUMBER FORMATTING:
    A comma may be a decimal separator.

    5,00 = 5
    3,49 = 3.49
    17,45 = 17.45
    10% = 10
    19,20 = 19.20

    Parentheses or brackets indicate negative values.

11. TOTALS:
    Carefully inspect the entire bottom portion of the invoice.

    Look for:

    Subtotal
    Sub-total
    Net Amount
    Discount
    Tax
    VAT
    GST
    Sales Tax
    Shipping
    Freight
    Rounding
    Total
    Grand Total
    Amount Paid
    Amount Due
    Balance Due

    If a printed amount exists, extract the PRINTED amount.

    Do NOT leave subtotal, tax or grand_total null merely because those
    values can be calculated from line items.

12. TAX:
    If a tax rate or tax amount is visibly printed, extract it.
    If a tax breakdown is visible, create a tax_breakdown entry.

13. PAYMENT:
    Extract cash tendered, change returned, amount paid and amount due
    when visible.

14. BANK DETAILS:
    Extract account number, bank name, branch or IFSC when visible.

15. NOTES:
    Extract visible invoice notes, payment terms or other meaningful
    text into notes_terms.

16. FINAL CHECK:
    Before returning JSON, verify that you inspected:

    - vendor
    - buyer
    - invoice number
    - date
    - currency
    - EVERY line item
    - quantity
    - unit price
    - tax rate
    - line total
    - subtotal
    - tax
    - discount
    - shipping
    - grand total
    - amount paid/due
    - payment information
    - bank information
    - notes/terms

Return ONLY valid JSON matching the requested structure.
""",
        "balance_sheet": """
You are an expert financial-document extraction system.

IMPORTANT: Read and inspect the ENTIRE balance sheet image BEFORE producing JSON.
Do NOT stop after extracting the first section you see.

This balance sheet normally contains TWO major sides/sections:
1. CAPITAL AND LIABILITIES
2. ASSETS

You MUST inspect BOTH sections independently and extract ALL visible rows from BOTH.
A response containing Capital and Liabilities but an empty Assets section is INCOMPLETE.

Extract ALL meaningful visible information, including:
- entity name
- reporting date
- comparative reporting date
- currency
- printed unit/multiplier
- every visible Capital and Liabilities line
- every visible Assets line
- every subtotal
- every printed total
- memo/off-balance-sheet items
- schedule references
- current-period values
- comparative/prior-period values

CRITICAL TABLE-READING RULES:

1. Read the image from TOP TO BOTTOM and LEFT TO RIGHT.
2. Identify the complete table structure before extracting values.
3. Do NOT stop when the Capital and Liabilities section is complete.
4. After Capital and Liabilities, explicitly inspect the ENTIRE Assets section.
5. Extract every visible row, even if the label is unfamiliar.
6. Preserve the printed values exactly in numeric meaning.
7. Parentheses/brackets indicate negative values.
8. Keep current and prior/comparative values separate.
9. Distinguish:
   - COMPONENT = individual financial component
   - SUBTOTAL = subtotal of a group
   - TOTAL = printed total
10. A printed subtotal or total MUST be extracted when visible. Do not calculate it yourself.
11. Do not omit a row because another row appears to contain a similar amount.
12. Do not infer missing rows from accounting logic.
13. If something is genuinely not visible, use null.
14. Never invent information.
15. Include page = 1 and short evidence/source text for every extracted line where possible.

BALANCE-SHEET COMPLETENESS CHECK:

Before returning JSON, mentally verify that you inspected:
- header/entity
- reporting date
- comparative date
- currency and unit
- ALL Capital and Liabilities rows
- Capital and Liabilities subtotal/total
- ALL Assets rows
- Assets subtotal/total
- memo/off-balance-sheet items

If the Assets section is visible in the image, "assets.line_items" MUST NOT be empty.

Return ONLY valid JSON matching the requested schema exactly.
""",

        "profit_and_loss": """
You are extracting structured information from a profit and loss statement.

Extract ALL meaningful visible information, including:
- entity name
- reporting periods and comparative periods
- currency
- printed unit/multiplier
- every visible income line
- every visible expenditure line
- every visible profit line
- appropriations
- earnings per share
- subtotals and totals
- schedule references
- comparative values

IMPORTANT:
- Do not invent information.
- Missing values must be null.
- Preserve every visible line item.
- Parentheses/brackets mean negative values.
- Distinguish COMPONENT, SUBTOTAL and TOTAL rows.
- Pay particular attention to:
  Interest Earned
  Other Income
  Total Income
  Interest Expended
  Operating Expenses
  Provisions & Contingencies
  Total Expenditure
  Net Profit before Minority Interest
  Minority Interest
  Net Profit attributable to Group
  Brought Forward Profit
- Include page and evidence/source text where supported.

Return JSON matching the provided schema exactly.
""",

        "cash_flow_statement": """
You are extracting structured information from a cash flow statement.

Extract ALL meaningful visible information, including:
- entity name
- reporting periods and comparative periods
- currency
- printed unit/multiplier
- every operating activity line
- every investing activity line
- every financing activity line
- internal subtotals
- section net cash-flow totals
- FX/translation adjustment
- opening cash
- net change in cash
- closing cash
- comparative values

IMPORTANT:
- Do not invent information.
- Missing values must be null.
- Preserve every visible line item.
- Parentheses/brackets mean negative values.
- Distinguish COMPONENT, SUBTOTAL and TOTAL rows.
- Keep FX/translation adjustment separate from financing activities.
- Do not combine a subtotal with the component rows that produced it.
- Include page and evidence/source text where supported.

Return JSON matching the provided schema exactly.
""",
    }

    if document_type not in prompts:
        raise ExtractionError(
            f"Unsupported document type: {document_type}"
        )

    return prompts[document_type]

def _schema_instructions(document_type: str) -> str:
    templates = {
        "invoice": """
You are extracting structured information from an invoice or receipt.

Read the ENTIRE document carefully before producing the JSON.

Extract ALL meaningful visible information, including:
- seller/vendor information
- buyer/customer information
- invoice number
- invoice date
- due date
- currency
- EVERY line item
- subtotal
- discount
- tax
- shipping
- rounding adjustment
- grand total
- amount paid
- amount due
- payment information
- bank details
- notes and terms

CRITICAL ACCURACY RULES:

1. Do NOT invent or calculate values during extraction.
   Extract values exactly as printed whenever possible.

2. If a field is not visibly present, return null.

3. Currency:
   - Preserve the printed symbol/text in raw_symbol.
   - Only set iso_code when the document explicitly identifies the currency
     or the currency can be determined unambiguously from the document.
   - Do NOT automatically convert "$" into USD.
   - If "$" is present without enough evidence to identify the country/currency,
     use iso_code = null and is_ambiguous = true.

4. Numbers:
   - Preserve the numeric meaning of the printed value.
   - Commas may be decimal separators.
   - Parentheses/brackets indicate negative values.
   - Do not confuse line totals with subtotal or grand total.

5. Invoice totals:
   Look specifically for labels such as:
   Subtotal
   Sub-total
   Tax
   VAT
   GST
   Sales Tax
   Discount
   Shipping
   Freight
   Rounding
   Total
   Grand Total
   Amount Paid
   Amount Due
   Balance Due

   If these values are visible, extract them.
   Do not leave them null merely because they can be calculated from line items.

6. Line items:
   Extract EVERY visible line item separately.
   Preserve description, quantity, unit, unit price, tax rate/code,
   discount information and line total.

7. Evidence:
   For every extracted value, include short evidence copied from the
   relevant visible text.
   Include page number = 1 for this single-page extraction.

8. Dates:
   Preserve the original printed date in invoice_date_raw_format.
   Do not silently reinterpret an ambiguous date.

Return ONLY valid JSON matching the requested structure.
""",
        "balance_sheet": """
Return exactly one JSON object using this structure:

{
  "document_type": "balance_sheet",
  "page_count": 1,
  "entity_name": {"value": null, "page": 1, "evidence": null},
  "reporting_date": {"value": null, "page": 1, "evidence": null},
  "comparative_reporting_date": {"value": null, "page": 1, "evidence": null},
  "currency": {
    "raw_symbol": null,
    "iso_code": null,
    "is_ambiguous": false,
    "page": 1,
    "evidence": null
  },
  "unit_multiplier_raw_label": null,
  "capital_and_liabilities": {
    "line_items": [],
    "reported_total": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    }
  },
  "assets": {
    "line_items": [],
    "reported_total": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    }
  },
  "memo_items": []
}

Each line item:
{
  "label": null,
  "schedule_ref": null,
  "current_value": null,
  "prior_value": null,
  "row_type": "COMPONENT",
  "page": 1,
  "evidence": null
}

row_type must be COMPONENT, SUBTOTAL, or TOTAL.
""",

        "profit_and_loss": """
Return exactly one JSON object using this structure:

{
  "document_type": "profit_and_loss",
  "page_count": 1,
  "entity_name": {"value": null, "page": 1, "evidence": null},
  "period_ended": {"value": null, "page": 1, "evidence": null},
  "comparative_period_ended": {"value": null, "page": 1, "evidence": null},
  "currency": {
    "raw_symbol": null,
    "iso_code": null,
    "is_ambiguous": false,
    "page": 1,
    "evidence": null
  },
  "unit_multiplier_raw_label": null,
  "income": {
    "interest_earned": null,
    "other_income": null,
    "reported_total": null,
    "line_items": []
  },
  "expenditure": {
    "interest_expended": null,
    "operating_expenses": null,
    "provisions_and_contingencies": null,
    "reported_total": null,
    "line_items": []
  },
  "profit": {
    "net_profit_before_minority_interest": null,
    "minority_interest": null,
    "net_profit_attributable_to_group": null,
    "brought_forward_profit": null,
    "reported_total": null,
    "line_items": []
  },
  "appropriations": {
    "reported_total": null,
    "line_items": []
  },
  "earnings_per_share": null
}

All ComparativeValue fields use:
{
  "current_value": null,
  "prior_value": null,
  "page": 1,
  "evidence": null
}

Each line item:
{
  "label": null,
  "schedule_ref": null,
  "current_value": null,
  "prior_value": null,
  "row_type": "COMPONENT",
  "page": 1,
  "evidence": null
}

row_type must be COMPONENT, SUBTOTAL, or TOTAL.
""",

        "cash_flow_statement": """
Return exactly one JSON object using this structure:

{
  "document_type": "cash_flow_statement",
  "page_count": 1,
  "entity_name": {"value": null, "page": 1, "evidence": null},
  "period_ended": {"value": null, "page": 1, "evidence": null},
  "comparative_period_ended": {"value": null, "page": 1, "evidence": null},
  "currency": {
    "raw_symbol": null,
    "iso_code": null,
    "is_ambiguous": false,
    "page": 1,
    "evidence": null
  },
  "unit_multiplier_raw_label": null,
  "operating_activities": {
    "line_items": [],
    "net_cash_flow": null
  },
  "investing_activities": {
    "line_items": [],
    "net_cash_flow": null
  },
  "financing_activities": {
    "line_items": [],
    "net_cash_flow": null
  },
  "fx_translation_effect": null,
  "cash_reconciliation": {
    "opening_cash": null,
    "net_change_in_cash": null,
    "closing_cash": null
  }
}

All ComparativeValue fields use:
{
  "current_value": null,
  "prior_value": null,
  "page": 1,
  "evidence": null
}

Each line item:
{
  "label": null,
  "current_value": null,
  "prior_value": null,
  "row_type": "COMPONENT",
  "page": 1,
  "evidence": null
}

row_type must be COMPONENT, SUBTOTAL, or TOTAL.
"""
    }

    if document_type not in templates:
        raise ExtractionError(
            f"Unsupported document type: {document_type}"
        )

    return templates[document_type]

def _build_invoice_header_prompt() -> str:
    return """
You are extracting the HEADER and LINE ITEMS from an invoice.

Read the ENTIRE invoice image carefully.

Extract ONLY these groups:

1. Vendor/seller
2. Buyer/customer
3. Invoice number
4. Invoice date
5. Due date
6. Currency
7. EVERY visible line item

For every extracted value, do not invent information.
Use null when genuinely not visible.

For line items, extract:
- description
- quantity
- unit
- unit_price
- tax_rate_percent
- tax_code
- discount_percent
- discount_amount
- line_total
- page
- evidence

Read the COMPLETE row from left to right.

For example:
"5,00 each 3,49 17,45 10% 19,20"

means, when supported by the column layout:
quantity = 5
unit = "each"
unit_price = 3.49
tax_rate_percent = 10
line_total = 19.20

Include the complete useful row in evidence.

For currency, do not automatically assume "$" means USD.
If the currency cannot be determined unambiguously:
iso_code = null
is_ambiguous = true

Return ONLY valid JSON.
"""

def _build_invoice_totals_prompt() -> str:
    return """
You are extracting the TOTALS and PAYMENT information from an invoice.

Read the ENTIRE invoice image, especially the lower portion.

Extract ONLY these groups:

1. Subtotal
2. Discount total
3. Tax breakdown
4. Shipping amount
5. Rounding adjustment
6. Grand total
7. Amount paid
8. Amount due
9. Payment information
10. Bank details
11. Notes and terms

Look specifically for printed labels such as:

Subtotal
Sub-total
Net Amount
Discount
Tax
VAT
GST
Sales Tax
Shipping
Freight
Rounding
Total
Grand Total
Amount Paid
Amount Due
Balance Due

IMPORTANT:

- Extract PRINTED values.
- Do not calculate a value when a printed value exists.
- Do not invent missing information.
- If a field is genuinely not visible, return null.
- Include page = 1 and useful evidence whenever possible.
- For tax breakdowns, extract the printed tax type, rate, taxable amount
  and tax amount when visible.

Return ONLY valid JSON.
"""

def _call_vision_model(
    image_bytes: bytes,
    prompt: str,
    mime_type: str,
    max_completion_tokens: int = 950,
) -> dict[str, Any]:
    client = _get_client()

    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": _image_to_data_url(
                                        image_bytes,
                                        mime_type,
                                    )
                                },
                            },
                        ],
                    }
                ],
                temperature=0,
                max_completion_tokens=max_completion_tokens,
                reasoning_effort="none",
                reasoning_format="hidden",
                response_format={"type": "json_object"},
            )

            print("COMPLETION TOKENS:", response.usage.completion_tokens)


            content = response.choices[0].message.content

            if not content:
                raise ExtractionError(
                    "The model returned an empty response."
                )

            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise ExtractionError(
                    "The model returned invalid JSON."
                ) from exc

        except Exception as exc:
            status_code = getattr(exc, "status_code", None)

            # Retry rate-limit and temporary server errors.
            if status_code == 429 or (
                isinstance(status_code, int) and 500 <= status_code < 600
            ):
                if attempt < max_attempts - 1:
                    import time

                    # Short exponential backoff:
                    # attempt 1 -> 2 seconds
                    # attempt 2 -> 4 seconds
                    wait_seconds = 2 ** (attempt + 1)

                    # Respect Retry-After when Groq provides it.
                    retry_after = getattr(exc, "response", None)
                    retry_after = getattr(
                        retry_after,
                        "headers",
                        {},
                    ).get("retry-after")

                    if retry_after:
                        try:
                            wait_seconds = min(
                                max(float(retry_after), 0),
                                10,
                            )
                        except (TypeError, ValueError):
                            pass

                    logger.warning(
                        "LLM request temporarily failed "
                        "(status=%s). Retrying in %.1f seconds "
                        "(attempt %d/%d).",
                        status_code,
                        wait_seconds,
                        attempt + 1,
                        max_attempts,
                    )

                    time.sleep(wait_seconds)
                    continue

            raise ExtractionError(
                f"LLM extraction request failed: {exc}"
            ) from exc

    raise ExtractionError(
        "LLM extraction failed after maximum retry attempts."
    )

def _normalize_invoice_payload(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize common LLM output variations into InvoiceExtraction schema.

    The LLM may return some simple fields as either:
      "invoice_number": "123"
    or:
      "invoice_number": {
          "value": "123",
          "page": 1,
          "evidence": "Invoice No: 123"
      }

    The Pydantic schema expects the second representation for FieldValue
    fields, so scalar values are wrapped here.

    Line-item fields are different: their schema expects primitive values,
    so FieldValue-style objects are unwrapped there.
    """

    # ---------------------------------------------------------
    # Top-level FieldValue fields
    # ---------------------------------------------------------

    field_value_fields = [
        "invoice_number",
        "invoice_date",
        "due_date",
        "subtotal",
        "discount_total",
        "shipping_amount",
        "rounding_adjustment",
        "grand_total",
        "amount_paid",
        "amount_due",
        "notes_terms",
    ]

    for field_name in field_value_fields:
        value = data.get(field_name)

        if value is not None and not isinstance(value, dict):
            data[field_name] = {
                "value": value,
                "page": 1,
                "evidence": None,
            }

    # invoice_date_raw_format is a plain string in the schema.
    raw_date = data.get("invoice_date_raw_format")

    if isinstance(raw_date, dict):
        data["invoice_date_raw_format"] = raw_date.get("value")

    # ---------------------------------------------------------
    # Vendor / buyer FieldValue fields
    # ---------------------------------------------------------

    for party_name in ("vendor", "buyer"):
        party = data.get(party_name)

        if not isinstance(party, dict):
            continue

        for field_name in (
            "name",
            "address",
            "tax_id_or_gstin",
            "contact",
        ):
            value = party.get(field_name)

            if value is not None and not isinstance(value, dict):
                party[field_name] = {
                    "value": value,
                    "page": 1,
                    "evidence": None,
                }

    # ---------------------------------------------------------
    # Line items
    # ---------------------------------------------------------

    line_items = data.get("line_items")

    if isinstance(line_items, list):
        for item in line_items:

            if not isinstance(item, dict):
                continue

            primitive_fields = [
                "description",
                "quantity",
                "unit",
                "unit_price",
                "tax_rate_percent",
                "tax_code",
                "discount_percent",
                "discount_amount",
                "line_total",
            ]

            extracted_page = item.get("page")
            extracted_evidence = item.get("evidence")

            for field_name in primitive_fields:
                value = item.get(field_name)

                if isinstance(value, dict):
                    if extracted_page is None:
                        extracted_page = value.get("page")

                    if extracted_evidence is None:
                        extracted_evidence = value.get("evidence")

                    item[field_name] = value.get("value")

            item["page"] = extracted_page
            item["evidence"] = extracted_evidence
            # Page/evidence belong directly to the line item.
            # If the model put them inside one of the FieldValue
            # objects, recover them where possible.

            if item.get("page") is None:
                for field_name in primitive_fields:
                    original = item.get(field_name)

                    if isinstance(original, dict):
                        if original.get("page") is not None:
                            item["page"] = original["page"]
                            break

            if item.get("evidence") is None:
                for field_name in primitive_fields:
                    original = item.get(field_name)

                    if isinstance(original, dict):
                        if original.get("evidence"):
                            item["evidence"] = original["evidence"]
                            break

    return data


def _call_llm(
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    mime_type: str = "image/png",
    max_completion_tokens: int = 2200,
) -> dict[str, Any]:
    """Run a focused Groq JSON extraction pass for cash-flow extraction."""
    client = _get_client()

    content: Any = prompt
    if image_bytes is not None:
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": _image_to_data_url(image_bytes, mime_type)
                },
            },
        ]

    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": content}],
                temperature=0,
                max_completion_tokens=max_completion_tokens,
                reasoning_effort="none",
                reasoning_format="hidden",
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)

            if status_code == 429 or (
                isinstance(status_code, int) and 500 <= status_code < 600
            ):
                if attempt < max_attempts - 1:
                    import time

                    wait_seconds = 2 ** (attempt + 1)
                    retry_after = getattr(exc, "response", None)
                    retry_after = getattr(
                        retry_after,
                        "headers",
                        {},
                    ).get("retry-after")

                    if retry_after:
                        try:
                            wait_seconds = min(
                                max(float(retry_after), 0),
                                10,
                            )
                        except (TypeError, ValueError):
                            pass

                    logger.warning(
                        "LLM request temporarily failed "
                        "(status=%s). Retrying in %.1f seconds "
                        "(attempt %d/%d).",
                        status_code,
                        wait_seconds,
                        attempt + 1,
                        max_attempts,
                    )
                    time.sleep(wait_seconds)
                    continue

            raise ExtractionError(
                f"LLM extraction request failed: {exc}"
            ) from exc

        print("===== CASH FLOW PASS DEBUG =====")
        print("COMPLETION TOKENS:", response.usage.completion_tokens)
        print("FINISH REASON:", response.choices[0].finish_reason)
        print("=================================")

        content_text = response.choices[0].message.content
        if not content_text:
            raise ExtractionError("The model returned an empty response.")

        try:
            return json.loads(content_text)
        except json.JSONDecodeError as exc:
            raise ExtractionError("The model returned invalid JSON.") from exc

    raise ExtractionError("LLM extraction failed after maximum retry attempts.")


def _build_cash_flow_operating_prompt(text_context: str | None) -> str:
    base = """
You are extracting the HEADER and OPERATING ACTIVITIES section of a cash flow statement.

Extract:
- entity name, reporting period, comparative period, currency, unit/multiplier
- EVERY operating-activities line item, including COMPONENT and SUBTOTAL rows
- the section's final Net cash flow from/(used in) operating activities line

Do NOT extract investing activities, financing activities, the FX/translation
adjustment, or the cash reconciliation. A separate pass handles those.

IMPORTANT:
- Read the relevant section completely before returning JSON.
- Do not invent information.
- Missing values must be null.
- Parentheses/brackets mean negative values.
- Preserve printed values.
- Distinguish COMPONENT, SUBTOTAL and TOTAL rows.
- Do not combine a subtotal with the component rows that produced it.
- Include page number and short evidence where supported.

Return exactly one JSON object with ONLY these fields:

{
  "entity_name": {"value": null, "page": 1, "evidence": null},
  "period_ended": {"value": null, "page": 1, "evidence": null},
  "comparative_period_ended": {"value": null, "page": 1, "evidence": null},
  "currency": {
    "raw_symbol": null,
    "iso_code": null,
    "is_ambiguous": false,
    "page": 1,
    "evidence": null
  },
  "unit_multiplier_raw_label": null,
  "operating_activities": {
    "line_items": [
      {
        "label": null,
        "current_value": null,
        "prior_value": null,
        "row_type": "COMPONENT",
        "page": 1,
        "evidence": null
      }
    ],
    "net_cash_flow": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    }
  }
}

row_type must be COMPONENT, SUBTOTAL, or TOTAL.
"""
    if text_context:
        base += f"\n\nSTATEMENT TEXT (page 1):\n{text_context}\n"
    return base


def _build_cash_flow_remaining_prompt(text_context: str | None) -> str:
    base = """
Operating activities were ALREADY extracted in a separate pass. Do not repeat them.

Read the SAME cash flow statement carefully, especially the LOWER portion.

Extract ONLY:
- EVERY investing-activities line item and the section's net cash flow line
- EVERY financing-activities line item and the section's net cash flow line
- the FX/exchange/translation adjustment line, kept separate from financing
- opening cash
- net change in cash
- closing cash
- comparative values for all applicable fields

IMPORTANT:
- Do not invent information.
- Missing values must be null.
- Parentheses/brackets mean negative values.
- Preserve every visible line item.
- Distinguish COMPONENT, SUBTOTAL and TOTAL rows.
- Do not combine a subtotal with the component rows that produced it.
- Inspect the entire lower portion before returning JSON.
- Include page number and short evidence where supported.

Return exactly one JSON object with ONLY these fields:

{
  "investing_activities": {
    "line_items": [
      {
        "label": null,
        "current_value": null,
        "prior_value": null,
        "row_type": "COMPONENT",
        "page": 1,
        "evidence": null
      }
    ],
    "net_cash_flow": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    }
  },
  "financing_activities": {
    "line_items": [
      {
        "label": null,
        "current_value": null,
        "prior_value": null,
        "row_type": "COMPONENT",
        "page": 1,
        "evidence": null
      }
    ],
    "net_cash_flow": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    }
  },
  "fx_translation_effect": {
    "current_value": null,
    "prior_value": null,
    "page": 1,
    "evidence": null
  },
  "cash_reconciliation": {
    "opening_cash": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    },
    "net_change_in_cash": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    },
    "closing_cash": {
      "current_value": null,
      "prior_value": null,
      "page": 1,
      "evidence": null
    }
  }
}

row_type must be COMPONENT, SUBTOTAL, or TOTAL.
"""
    if text_context:
        base += f"\n\nSTATEMENT TEXT (page 1):\n{text_context}\n"
    return base


def _merge_cash_flow_passes(
    operating_data: dict[str, Any],
    remaining_data: dict[str, Any],
) -> dict[str, Any]:
    """Merge the two focused cash-flow extraction passes safely."""
    merged = dict(operating_data)

    for key in (
        "investing_activities",
        "financing_activities",
        "fx_translation_effect",
        "cash_reconciliation",
    ):
        if remaining_data.get(key) is not None:
            merged[key] = remaining_data[key]

    return merged


def _finalize_cash_flow(data: dict[str, Any]) -> dict[str, Any]:
    data = _normalize_row_types(data)

    try:
        validated = CashFlowExtraction.model_validate(data)
    except ValidationError as exc:
        raise ExtractionError(
            f"Cash flow extraction failed schema validation: {exc}"
        ) from exc

    return validated.model_dump(mode="json")


def extract_cash_flow_from_image(
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> dict[str, Any]:
    """Extract Cash Flow using two focused vision passes."""
    operating_data = _call_llm(
        _build_cash_flow_operating_prompt(None),
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    try:
        remaining_data = _call_llm(
            _build_cash_flow_remaining_prompt(None),
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
    except ExtractionError:
        remaining_data = {}

    return _finalize_cash_flow(
        _merge_cash_flow_passes(operating_data, remaining_data)
    )


def extract_cash_flow_from_text(
    text: str,
    page_number: int = 1,
    page_count: int = 1,
) -> dict[str, Any]:
    """Extract Cash Flow using two focused text passes."""
    if not text or not text.strip():
        raise ExtractionError("No usable text was provided for extraction.")

    operating_data = _call_llm(
        _build_cash_flow_operating_prompt(text)
    )

    try:
        remaining_data = _call_llm(
            _build_cash_flow_remaining_prompt(text)
        )
    except ExtractionError:
        remaining_data = {}

    merged = _merge_cash_flow_passes(
        operating_data,
        remaining_data,
    )
    merged["page_count"] = page_count

    return _finalize_cash_flow(merged)


def extract_from_image(
    image_bytes: bytes,
    document_type: str,
    mime_type: str = "image/png",
) -> dict[str, Any]:
    """
    Extract a document image.

    Invoices use a single focused vision pass to stay within
    the Groq output-token limit.

    Other document types continue to use the existing single-pass flow.
    """

    if document_type not in SCHEMA_MODELS:
        raise ExtractionError(
            f"Unsupported document type: {document_type}"
        )

    # ---------------------------------------------------------
    # # INVOICE: SINGLE-PASS EXTRACTION
    # ---------------------------------------------------------

    if document_type == "invoice":

        # Single-pass extraction:
        # header + vendor/buyer + all line items + totals/payment
        # This keeps the request below the Groq output-token limit.
        invoice_prompt = (
            _build_prompt("invoice")
            + "\n"
            + _schema_instructions("invoice")
        )

        try:
            raw_data = _call_vision_model(
            image_bytes=image_bytes,
            prompt=invoice_prompt,
            mime_type=mime_type,
            max_completion_tokens=950,
        )
        except ExtractionError as exc:
          raise ExtractionError(
            f"Invoice extraction failed: {exc}"
        ) from exc

      # The model may return scalar values or FieldValue-style objects.
      # Normalize them before Pydantic validation.
        raw_data = _normalize_invoice_payload(raw_data)

    # These are known from the processing pipeline, so don't waste
    # precious LLM output tokens asking the model to repeat them.
        raw_data["document_type"] = "invoice"
        raw_data["page_count"] = 1

        try:
          validated = InvoiceExtraction.model_validate(raw_data)
        except ValidationError as exc:
         raise ExtractionError(
            f"Invoice extraction failed schema validation: {exc}"
        ) from exc

        return validated.model_dump(mode="json")
    
    if document_type == "cash_flow_statement":
        return extract_cash_flow_from_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

    # ---------------------------------------------------------
    # OTHER DOCUMENT TYPES: EXISTING SINGLE-PASS EXTRACTION
    # ---------------------------------------------------------

    client = _get_client()

    prompt = (
        _build_prompt(document_type)
        + _schema_instructions(document_type)
    )


    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _image_to_data_url(
                                    image_bytes,
                                    mime_type,
                                )
                            },
                        },
                    ],
                }
            ],
            temperature=0,
            max_completion_tokens=4000,
            reasoning_effort="none",
            reasoning_format="hidden",
            response_format={"type": "json_object"},
        )

    except Exception as exc:
        raise ExtractionError(
            f"LLM extraction request failed: {exc}"
        ) from exc

    print("========== GROQ DEBUG ==========")
    print("COMPLETION TOKENS:", response.usage.completion_tokens)
    print("FINISH REASON:", response.choices[0].finish_reason)
    print("================================")

    content = response.choices[0].message.content

    if not content:
        raise ExtractionError(
            "The model returned an empty response."
        )

    try:
            raw_data = json.loads(content)
    except json.JSONDecodeError as exc:
            raise ExtractionError(
                "The model returned invalid JSON."
            ) from exc

        # Normalize LLM enum casing before Pydantic validation.
    raw_data = _normalize_row_types(raw_data)

    schema_model = SCHEMA_MODELS[document_type]
    try:
        validated = schema_model.model_validate(raw_data)
    except ValidationError as exc:
        raise ExtractionError(
            f"LLM response failed schema validation: {exc}"
        ) from exc

    return validated.model_dump(mode="json")


def _normalize_row_types(payload: Any) -> Any:
    """Normalize row_type enum values returned by the LLM."""
    if isinstance(payload, dict):
        normalized = {}
        for key, value in payload.items():
            if key == "row_type" and isinstance(value, str):
                normalized[key] = value.strip().lower()
            else:
                normalized[key] = _normalize_row_types(value)
        return normalized

    if isinstance(payload, list):
        return [_normalize_row_types(item) for item in payload]

    return payload


def extract_from_text(
    text: str,
    document_type: str,
    page_number: int = 1,
    page_count: int = 1,
) -> dict[str, Any]:
    """
    Extract structured document data from already-extracted PDF text.

    Used for native-text PDF pages so we do not unnecessarily send
    readable PDFs through vision.
    """

    if document_type not in SCHEMA_MODELS:
        raise ExtractionError(
            f"Unsupported document type: {document_type}"
        )

    if not text or not text.strip():
        raise ExtractionError(
            "No usable text was provided for extraction."
        )

    if document_type == "cash_flow_statement":
        return extract_cash_flow_from_text(
            text=text,
            page_number=page_number,
            page_count=page_count,
        )

    client = _get_client()

    prompt = (
        _build_prompt(document_type)
        + "\n"
        + _schema_instructions(document_type)
        + f"""

ADDITIONAL TEXT EXTRACTION RULES:

The following text was extracted from PDF page {page_number}.

- Extract ONLY information actually present in the text.
- Do NOT invent missing values.
- Preserve printed numbers and labels.
- Parentheses/brackets indicate negative values.
- Preserve comparative current/prior values separately.
- Include page number {page_number} where appropriate.
- Evidence should contain a short excerpt from the supplied text.
- The PDF may contain formatting artifacts from text extraction.
- Use the surrounding labels and table structure to interpret values.

PAGE {page_number} TEXT:
{text}

Return ONLY valid JSON.
"""
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            max_completion_tokens=1800,
            reasoning_effort="none",
            reasoning_format="hidden",
            response_format={"type": "json_object"},
        )

    except Exception as exc:
        raise ExtractionError(
            f"LLM text extraction request failed: {exc}"
        ) from exc

    content = response.choices[0].message.content

    if not content:
        raise ExtractionError(
            "The model returned an empty response."
        )

    try:
           raw_data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            "The model returned invalid JSON."
        ) from exc

    # Normalize LLM enum casing before Pydantic validation.
    raw_data = _normalize_row_types(raw_data)

    # Make sure page_count reflects the actual document rather than
    # whatever value the model guessed.
    raw_data["page_count"] = page_count

    schema_model = SCHEMA_MODELS[document_type]

    try:
        validated = schema_model.model_validate(raw_data)
    except ValidationError as exc:
        raise ExtractionError(
            f"LLM text response failed schema validation: {exc}"
        ) from exc

    
    # Make sure page_count reflects the actual document rather than
    # whatever value the model guessed.
    raw_data["page_count"] = page_count
    schema_model = SCHEMA_MODELS[document_type]

    try:
        validated = schema_model.model_validate(raw_data)
    except ValidationError as exc:
        raise ExtractionError(
            f"LLM text response failed schema validation: {exc}"
        ) from exc

    return validated.model_dump(mode="json")

def _normalize_row_types(payload: Any) -> Any:
    """Normalize row_type enum values returned by the LLM."""
    if isinstance(payload, dict):
        normalized = {}
        for key, value in payload.items():
            if key == "row_type" and isinstance(value, str):
                normalized[key] = value.strip().lower()
            else:
                normalized[key] = _normalize_row_types(value)
        return normalized

    if isinstance(payload, list):
        return [_normalize_row_types(item) for item in payload]

    return payload