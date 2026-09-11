"""Pydantic schema package.

Common envelopes/enums live in `common.py`. Each document type has its own
module so schemas never lose information by being forced into one
universal shape:

    invoice.py            -> InvoiceExtraction
    balance_sheet.py       -> BalanceSheetExtraction
    profit_and_loss.py     -> ProfitAndLossExtraction
    cash_flow.py           -> CashFlowExtraction
"""
