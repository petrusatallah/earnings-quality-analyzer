import contextlib
import io

import pandas as pd

with contextlib.redirect_stdout(io.StringIO()):
    from Data.financial_data import required_fields

required_years = [2022, 2023, 2024, 2025]

metric_details = {
    "Revenue": ("USD millions", "Income Statement"),
    "Net Income": ("USD millions", "Income Statement"),
    "Operating Cash Flow": ("USD millions", "Cash Flow Statement"),
    "Accounts Receivable": ("USD millions", "Balance Sheet"),
    "Inventory": ("USD millions", "Balance Sheet"),
    "Accounts Payable": ("USD millions", "Balance Sheet"),
    "Depreciation & Amortization": ("USD millions", "Cash Flow Statement"),
    "Capital Expenditures": ("USD millions", "Cash Flow Statement"),
    "Stock-Based Compensation": ("USD millions", "Cash Flow Statement"),
    "Shares Outstanding": ("millions of shares", "Equity / Notes"),
    "Tax Expense": ("USD millions", "Income Statement / Tax Note"),
    "Deferred Tax Assets": ("USD millions", "Tax Note"),
    "Deferred Tax Liabilities": ("USD millions", "Tax Note"),
}

source_dates = {
    2022: "2022-10-28",
    2023: "2023-11-03",
    2024: "2024-11-01",
    2025: "2025-10-31",
}

verified_values = {
    2022: {"Revenue": 394328, "Net Income": 99803, "Operating Cash Flow": 122151, "Accounts Receivable": 28184, "Inventory": 4946, "Accounts Payable": 64115, "Depreciation & Amortization": 11104, "Capital Expenditures": 10708, "Stock-Based Compensation": 9038, "Shares Outstanding": 15943.425, "Tax Expense": 19300, "Deferred Tax Assets": 20094, "Deferred Tax Liabilities": 5557},
    2023: {"Revenue": 383285, "Net Income": 96995, "Operating Cash Flow": 110543, "Accounts Receivable": 29508, "Inventory": 6331, "Accounts Payable": 62611, "Depreciation & Amortization": 11519, "Capital Expenditures": 10959, "Stock-Based Compensation": 10833, "Shares Outstanding": 15550.061, "Tax Expense": 16741, "Deferred Tax Assets": 24369, "Deferred Tax Liabilities": 7118},
    2024: {"Revenue": 391035, "Net Income": 93736, "Operating Cash Flow": 118254, "Accounts Receivable": 33410, "Inventory": 7286, "Accounts Payable": 68960, "Depreciation & Amortization": 11445, "Capital Expenditures": 9447, "Stock-Based Compensation": 11688, "Shares Outstanding": 15116.786, "Tax Expense": 29749, "Deferred Tax Assets": 26007, "Deferred Tax Liabilities": 6805},
    2025: {"Revenue": 416161, "Net Income": 112010, "Operating Cash Flow": 111482, "Accounts Receivable": 39777, "Inventory": 5718, "Accounts Payable": 69860, "Depreciation & Amortization": 11698, "Capital Expenditures": 12715, "Stock-Based Compensation": 12863, "Shares Outstanding": 14773.260, "Tax Expense": 20719, "Deferred Tax Assets": 27451, "Deferred Tax Liabilities": 7471},
}

apple_financial_data = []

for fiscal_year in required_years:
    for metric, (units, financial_statement) in metric_details.items():
        apple_financial_data.append(
            {
                "Company": "Apple Inc.",
                "Ticker": "AAPL",
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": verified_values[fiscal_year][metric],
                "Units": units,
                "Financial Statement": financial_statement,
                "Source": "Apple Form 10-K",
                "Source Date": source_dates[fiscal_year],
            }
        )

apple_financial_data_df = pd.DataFrame(
    apple_financial_data, columns=required_fields
)
