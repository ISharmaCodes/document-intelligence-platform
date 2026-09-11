from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.common import DocumentType, RowType


# Financial documents are usually printed with rounding differences.
# 0.5% gives us a practical tolerance while still catching real errors.
DEFAULT_RELATIVE_TOLERANCE = Decimal("0.005")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("0.01")


def _decimal(value: Any) -> Decimal | None:
    """Safely convert a numeric value to Decimal."""
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _tolerance(reported: Decimal | None) -> Decimal:
    """Return an absolute tolerance based on the reported amount."""
    if reported is None:
        return DEFAULT_ABSOLUTE_TOLERANCE

    return max(
        DEFAULT_ABSOLUTE_TOLERANCE,
        abs(reported) * DEFAULT_RELATIVE_TOLERANCE,
    )


def _compare(
    *,
    name: str,
    formula: str,
    operands: dict[str, Any],
    calculated: Decimal | None,
    reported: Decimal | None,
    period: str | None = None,
) -> dict[str, Any]:
    """
    Compare a calculated financial value with the printed/reported value.
    """
    if calculated is None or reported is None:
        return {
            "name": name,
            "formula": formula,
            "operands": operands,
            "calculated": float(calculated) if calculated is not None else None,
            "reported": float(reported) if reported is not None else None,
            "variance": None,
            "tolerance": None,
            "status": "NOT_APPLICABLE",
            "reason": "Required values were not available for validation.",
            "period": period,
        }

    variance = calculated - reported
    tolerance = _tolerance(reported)

    passed = abs(variance) <= tolerance

    return {
        "name": name,
        "formula": formula,
        "operands": operands,
        "calculated": float(calculated),
        "reported": float(reported),
        "variance": float(variance),
        "tolerance": float(tolerance),
        "status": "PASS" if passed else "FAIL",
        "reason": (
            "Calculated value agrees with the reported value within tolerance."
            if passed
            else "Calculated value differs from the reported value beyond tolerance."
        ),
        "period": period,
    }


def _field_value(field: Any) -> Any:
    """Extract .value from a FieldValue-like object or dictionary."""
    if field is None:
        return None

    if hasattr(field, "value"):
        return field.value

    if isinstance(field, dict):
        return field.get("value")

    return field


def _comparative_value(field: Any, period: str) -> Any:
    """Extract current/prior from a ComparativeValue-like object."""
    if field is None:
        return None

    field_name = (
        "current_value"
        if period in ("current", "current_value")
        else "prior_value"
        if period in ("prior", "prior_value")
        else period
    )

    if hasattr(field, field_name):
        return getattr(field, field_name)

    if isinstance(field, dict):
        return field.get(field_name)

    return None


def _row_value(row: Any, period: str) -> Decimal | None:
    if hasattr(row, period):
        return _decimal(getattr(row, period))

    if isinstance(row, dict):
        return _decimal(row.get(period))

    return None


def _row_type(row: Any) -> str:
    value = row.row_type if hasattr(row, "row_type") else row.get("row_type")

    if hasattr(value, "value"):
        return value.value

    return str(value).lower()


# ---------------------------------------------------------------------------
# INVOICE
# ---------------------------------------------------------------------------

def validate_invoice(invoice: Any) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []

    # 1. Validate every line item where quantity, unit price and line total
    # are available.
    for index, item in enumerate(invoice.line_items, start=1):
        quantity = _decimal(item.quantity)
        unit_price = _decimal(item.unit_price)
        line_total = _decimal(item.line_total)

        calculated = (
            quantity * unit_price
            if quantity is not None and unit_price is not None
            else None
        )

        validations.append(
            _compare(
                name=f"Invoice line item {index} calculation",
                formula="quantity × unit_price ≈ line_total",
                operands={
                    "quantity": float(quantity) if quantity is not None else None,
                    "unit_price": float(unit_price) if unit_price is not None else None,
                },
                calculated=calculated,
                reported=line_total,
                period=None,
            )
        )

    # 2. Validate subtotal against line-item totals when possible.
    line_totals = [
        _decimal(item.line_total)
        for item in invoice.line_items
        if _decimal(item.line_total) is not None
    ]

    subtotal = _decimal(_field_value(invoice.subtotal))

    if line_totals and subtotal is not None:
        calculated_subtotal = sum(line_totals, Decimal("0"))

        validations.append(
            _compare(
                name="Invoice line items to subtotal",
                formula="sum(line_item.line_total) ≈ subtotal",
                operands={
                    "line_item_totals": [float(x) for x in line_totals],
                },
                calculated=calculated_subtotal,
                reported=subtotal,
            )
        )

    # 3. Validate grand total.
    #
    # We intentionally do NOT assume every invoice uses exactly:
    # subtotal + tax - discount.
    #
    # Shipping and rounding may exist, and some invoices have tax-inclusive
    # prices. Therefore this check is only performed when the available
    # fields support a reasonable reconstruction.
    grand_total = _decimal(_field_value(invoice.grand_total))
    discount = _decimal(_field_value(invoice.discount_total))
    shipping = _decimal(_field_value(invoice.shipping_amount))
    rounding = _decimal(_field_value(invoice.rounding_adjustment))

    tax_amounts = [
        _decimal(row.tax_amount)
        for row in invoice.tax_breakdown
        if _decimal(row.tax_amount) is not None
    ]

    tax_total = sum(tax_amounts, Decimal("0")) if tax_amounts else None

    if subtotal is not None and grand_total is not None:
        calculated = subtotal

        if discount is not None:
            calculated -= discount

        if tax_total is not None:
            calculated += tax_total

        if shipping is not None:
            calculated += shipping

        if rounding is not None:
            calculated += rounding

        validations.append(
            _compare(
                name="Invoice total reconciliation",
                formula=(
                    "subtotal - discount + tax + shipping + rounding "
                    "≈ grand_total"
                ),
                operands={
                    "subtotal": float(subtotal),
                    "discount": float(discount) if discount is not None else None,
                    "tax": float(tax_total) if tax_total is not None else None,
                    "shipping": float(shipping) if shipping is not None else None,
                    "rounding": float(rounding) if rounding is not None else None,
                },
                calculated=calculated,
                reported=grand_total,
            )
        )

    # 4. Cash tendered - change ≈ total.
    payment = invoice.payment

    if payment is not None:
        cash_tendered = _decimal(payment.cash_tendered)
        change_returned = _decimal(payment.change_returned)

        if cash_tendered is not None and change_returned is not None:
            validations.append(
                _compare(
                    name="Invoice cash payment reconciliation",
                    formula="cash_tendered - change_returned ≈ grand_total",
                    operands={
                        "cash_tendered": float(cash_tendered),
                        "change_returned": float(change_returned),
                    },
                    calculated=cash_tendered - change_returned,
                    reported=grand_total,
                )
            )

    return validations


# ---------------------------------------------------------------------------
# BALANCE SHEET
# ---------------------------------------------------------------------------

def _validate_balance_section(
    section: Any,
    section_name: str,
) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []

    for period in ("current_value", "prior_value"):
        component_values = [
            _row_value(row, period)
            for row in section.line_items
            if _row_type(row) == RowType.COMPONENT.value
            and _row_value(row, period) is not None
        ]

        reported = _comparative_value(
            section.reported_total,
            "current_value" if period == "current_value" else "prior_value",
        )
        reported_decimal = _decimal(reported)

        calculated = (
            sum(component_values, Decimal("0"))
            if component_values
            else None
        )

        period_name = "current" if period == "current_value" else "prior"

        validations.append(
            _compare(
                name=f"{section_name} components to printed total ({period_name})",
                formula=f"sum({section_name} COMPONENT rows) ≈ reported total",
                operands={
                    "component_values": [float(x) for x in component_values],
                },
                calculated=calculated,
                reported=reported_decimal,
                period=period_name,
            )
        )

    return validations


def validate_balance_sheet(balance_sheet: Any) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []

    validations.extend(
        _validate_balance_section(
            balance_sheet.capital_and_liabilities,
            "capital_and_liabilities",
        )
    )

    validations.extend(
        _validate_balance_section(
            balance_sheet.assets,
            "assets",
        )
    )

    # Assets ≈ Capital + Liabilities, independently for current/prior period.
    for period in ("current", "prior"):
        assets_total = _decimal(
            _comparative_value(
                balance_sheet.assets.reported_total,
                period,
            )
        )

        liabilities_total = _decimal(
            _comparative_value(
                balance_sheet.capital_and_liabilities.reported_total,
                period,
            )
        )

        validations.append(
            _compare(
                name=f"Balance sheet equation ({period})",
                formula="capital_and_liabilities ≈ assets",
                operands={
                    "capital_and_liabilities": (
                        float(liabilities_total)
                        if liabilities_total is not None
                        else None
                    ),
                },
                calculated=liabilities_total,
                reported=assets_total,
                period=period,
            )
        )

    return validations


# ---------------------------------------------------------------------------
# PROFIT & LOSS
# ---------------------------------------------------------------------------

def _pnl_value(field: Any, period: str) -> Decimal | None:
    return _decimal(_comparative_value(field, period))


def validate_profit_and_loss(pnl: Any) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []

    for period in ("current", "prior"):
        interest_earned = _pnl_value(
            pnl.income.interest_earned,
            period,
        )
        other_income = _pnl_value(
            pnl.income.other_income,
            period,
        )
        total_income = _pnl_value(
            pnl.income.reported_total,
            period,
        )

        if interest_earned is not None and other_income is not None:
            income_calculated = interest_earned + other_income
        else:
            income_calculated = None

        validations.append(
            _compare(
                name=f"Total income reconciliation ({period})",
                formula="Interest Earned + Other Income ≈ Total Income",
                operands={
                    "interest_earned": (
                        float(interest_earned)
                        if interest_earned is not None
                        else None
                    ),
                    "other_income": (
                        float(other_income)
                        if other_income is not None
                        else None
                    ),
                },
                calculated=income_calculated,
                reported=total_income,
                period=period,
            )
        )

        interest_expended = _pnl_value(
            pnl.expenditure.interest_expended,
            period,
        )
        operating_expenses = _pnl_value(
            pnl.expenditure.operating_expenses,
            period,
        )
        provisions = _pnl_value(
            pnl.expenditure.provisions_and_contingencies,
            period,
        )
        total_expenditure = _pnl_value(
            pnl.expenditure.reported_total,
            period,
        )

        if (
            interest_expended is not None
            and operating_expenses is not None
            and provisions is not None
        ):
            expenditure_calculated = (
                interest_expended
                + operating_expenses
                + provisions
            )
        else:
            expenditure_calculated = None

        validations.append(
            _compare(
                name=f"Total expenditure reconciliation ({period})",
                formula=(
                    "Interest Expended + Operating Expenses "
                    "+ Provisions & Contingencies ≈ Total Expenditure"
                ),
                operands={
                    "interest_expended": (
                        float(interest_expended)
                        if interest_expended is not None
                        else None
                    ),
                    "operating_expenses": (
                        float(operating_expenses)
                        if operating_expenses is not None
                        else None
                    ),
                    "provisions_and_contingencies": (
                        float(provisions)
                        if provisions is not None
                        else None
                    ),
                },
                calculated=expenditure_calculated,
                reported=total_expenditure,
                period=period,
            )
        )

        net_profit_before_minority = _pnl_value(
            pnl.profit.net_profit_before_minority_interest,
            period,
        )

        if total_income is not None and total_expenditure is not None:
            profit_calculated = total_income - total_expenditure
        else:
            profit_calculated = None

        validations.append(
            _compare(
                name=f"Profit before minority interest ({period})",
                formula="Total Income - Total Expenditure ≈ Net Profit before Minority Interest",
                operands={
                    "total_income": (
                        float(total_income)
                        if total_income is not None
                        else None
                    ),
                    "total_expenditure": (
                        float(total_expenditure)
                        if total_expenditure is not None
                        else None
                    ),
                },
                calculated=profit_calculated,
                reported=net_profit_before_minority,
                period=period,
            )
        )

        minority_interest = _pnl_value(
            pnl.profit.minority_interest,
            period,
        )

        attributable_profit = _pnl_value(
            pnl.profit.net_profit_attributable_to_group,
            period,
        )

        if (
            net_profit_before_minority is not None
            and minority_interest is not None
        ):
            attributable_calculated = (
                net_profit_before_minority - minority_interest
            )
        else:
            attributable_calculated = None

        validations.append(
            _compare(
                name=f"Attributable profit reconciliation ({period})",
                formula=(
                    "Net Profit before Minority Interest "
                    "- Minority Interest ≈ Net Profit attributable to Group"
                ),
                operands={
                    "net_profit_before_minority_interest": (
                        float(net_profit_before_minority)
                        if net_profit_before_minority is not None
                        else None
                    ),
                    "minority_interest": (
                        float(minority_interest)
                        if minority_interest is not None
                        else None
                    ),
                },
                calculated=attributable_calculated,
                reported=attributable_profit,
                period=period,
            )
        )

    return validations


# ---------------------------------------------------------------------------
# CASH FLOW
# ---------------------------------------------------------------------------

def _validate_cash_flow_section(
    section: Any,
    section_name: str,
) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []

    for period in ("current", "prior"):
        # CRITICAL:
        # Only COMPONENT rows are summed.
        # SUBTOTAL and TOTAL rows are deliberately excluded.
        components = [
           _row_value(row, "current_value" if period == "current" else "prior_value")
            for row in section.line_items
            if _row_type(row) == RowType.COMPONENT.value
            and _row_value(
                row,
                "current_value" if period == "current" else "prior_value",
            ) is not None
        ]

        calculated = (
            sum(components, Decimal("0"))
            if components
            else None
        )

        reported = _decimal(
            _comparative_value(
                section.net_cash_flow,
                period,
            )
        )

        validations.append(
            _compare(
                name=f"{section_name} net cash flow ({period})",
                formula=f"sum({section_name} COMPONENT rows) ≈ net cash flow",
                operands={
                    "component_values": [float(x) for x in components],
                },
                calculated=calculated,
                reported=reported,
                period=period,
            )
        )

    return validations


def validate_cash_flow(cash_flow: Any) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []

    validations.extend(
        _validate_cash_flow_section(
            cash_flow.operating_activities,
            "operating_activities",
        )
    )

    validations.extend(
        _validate_cash_flow_section(
            cash_flow.investing_activities,
            "investing_activities",
        )
    )

    validations.extend(
        _validate_cash_flow_section(
            cash_flow.financing_activities,
            "financing_activities",
        )
    )

    # Net change = operating + investing + financing + FX effect.
    for period in ("current", "prior"):
        operating = _comparative_value(
            cash_flow.operating_activities.net_cash_flow,
            period,
        )
        investing = _comparative_value(
            cash_flow.investing_activities.net_cash_flow,
            period,
        )
        financing = _comparative_value(
            cash_flow.financing_activities.net_cash_flow,
            period,
        )

        operating_d = _decimal(operating)
        investing_d = _decimal(investing)
        financing_d = _decimal(financing)

        fx_d = _decimal(
            _comparative_value(
                cash_flow.fx_translation_effect,
                period,
            )
        )

        reported_change = _decimal(
            _comparative_value(
                cash_flow.cash_reconciliation.net_change_in_cash,
                period,
            )
        )

        values = [
            operating_d,
            investing_d,
            financing_d,
        ]

        if all(value is not None for value in values):
            calculated_change = (
                operating_d
                + investing_d
                + financing_d
            )

            if fx_d is not None:
                calculated_change += fx_d
        else:
            calculated_change = None

        validations.append(
            _compare(
                name=f"Cash flow net change reconciliation ({period})",
                formula=(
                    "Operating + Investing + Financing + FX adjustment "
                    "≈ Net Change in Cash"
                ),
                operands={
                    "operating": (
                        float(operating_d)
                        if operating_d is not None
                        else None
                    ),
                    "investing": (
                        float(investing_d)
                        if investing_d is not None
                        else None
                    ),
                    "financing": (
                        float(financing_d)
                        if financing_d is not None
                        else None
                    ),
                    "fx_adjustment": (
                        float(fx_d)
                        if fx_d is not None
                        else None
                    ),
                },
                calculated=calculated_change,
                reported=reported_change,
                period=period,
            )
        )

        opening = _decimal(
            _comparative_value(
                cash_flow.cash_reconciliation.opening_cash,
                period,
            )
        )

        closing = _decimal(
            _comparative_value(
                cash_flow.cash_reconciliation.closing_cash,
                period,
            )
        )

        if opening is not None and calculated_change is not None:
            calculated_closing = opening + calculated_change
        else:
            calculated_closing = None

        validations.append(
            _compare(
                name=f"Opening to closing cash reconciliation ({period})",
                formula="Opening Cash + Net Change in Cash ≈ Closing Cash",
                operands={
                    "opening_cash": (
                        float(opening)
                        if opening is not None
                        else None
                    ),
                    "net_change_in_cash": (
                        float(calculated_change)
                        if calculated_change is not None
                        else None
                    ),
                },
                calculated=calculated_closing,
                reported=closing,
                period=period,
            )
        )

    return validations


# ---------------------------------------------------------------------------
# DISPATCHER
# ---------------------------------------------------------------------------

def validate_financial_document(
    document_type: DocumentType | str,
    extracted_data: Any,
) -> list[dict[str, Any]]:
    """Dispatch deterministic financial validation by document type."""

    if hasattr(document_type, "value"):
        document_type = document_type.value

    if document_type == DocumentType.INVOICE.value:
        return validate_invoice(extracted_data)

    if document_type == DocumentType.BALANCE_SHEET.value:
        return validate_balance_sheet(extracted_data)

    if document_type == DocumentType.PROFIT_AND_LOSS.value:
        return validate_profit_and_loss(extracted_data)

    if document_type == DocumentType.CASH_FLOW_STATEMENT.value:
        return validate_cash_flow(extracted_data)

    return []