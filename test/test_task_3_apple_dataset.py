"""Focused tests for the Task 3 manual Apple financial dataset."""

import contextlib
import io
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Data.financial_data import required_fields as task_2_required_fields
    from Data.apple_test_dataset import (
        apple_financial_data_df,
        required_fields,
    )


EXPECTED_VALUES = {
    2022: {
        "Revenue": 394328, "Net Income": 99803,
        "Operating Cash Flow": 122151, "Accounts Receivable": 28184,
        "Inventory": 4946, "Accounts Payable": 64115,
        "Depreciation & Amortization": 11104, "Capital Expenditures": 10708,
        "Stock-Based Compensation": 9038, "Shares Outstanding": 15943.425,
        "Tax Expense": 19300, "Deferred Tax Assets": 20094,
        "Deferred Tax Liabilities": 5557,
    },
    2023: {
        "Revenue": 383285, "Net Income": 96995,
        "Operating Cash Flow": 110543, "Accounts Receivable": 29508,
        "Inventory": 6331, "Accounts Payable": 62611,
        "Depreciation & Amortization": 11519, "Capital Expenditures": 10959,
        "Stock-Based Compensation": 10833, "Shares Outstanding": 15550.061,
        "Tax Expense": 16741, "Deferred Tax Assets": 24369,
        "Deferred Tax Liabilities": 7118,
    },
    2024: {
        "Revenue": 391035, "Net Income": 93736,
        "Operating Cash Flow": 118254, "Accounts Receivable": 33410,
        "Inventory": 7286, "Accounts Payable": 68960,
        "Depreciation & Amortization": 11445, "Capital Expenditures": 9447,
        "Stock-Based Compensation": 11688, "Shares Outstanding": 15116.786,
        "Tax Expense": 29749, "Deferred Tax Assets": 26007,
        "Deferred Tax Liabilities": 6805,
    },
    2025: {
        "Revenue": 416161, "Net Income": 112010,
        "Operating Cash Flow": 111482, "Accounts Receivable": 39777,
        "Inventory": 5718, "Accounts Payable": 69860,
        "Depreciation & Amortization": 11698, "Capital Expenditures": 12715,
        "Stock-Based Compensation": 12863, "Shares Outstanding": 14773.260,
        "Tax Expense": 20719, "Deferred Tax Assets": 27451,
        "Deferred Tax Liabilities": 7471,
    },
}

EXPECTED_DETAILS = {
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

EXPECTED_SOURCE_DATES = {
    2022: "2022-10-28",
    2023: "2023-11-03",
    2024: "2024-11-01",
    2025: "2025-10-31",
}


def test_task_3_reuses_the_exact_task_2_financial_structure() -> None:
    assert required_fields == task_2_required_fields
    assert apple_financial_data_df.columns.tolist() == task_2_required_fields


def test_task_3_contains_each_required_apple_metric_and_verified_value() -> None:
    assert set(apple_financial_data_df["Company"]) == {"Apple Inc."}
    assert set(apple_financial_data_df["Ticker"]) == {"AAPL"}
    assert set(apple_financial_data_df["Fiscal Year"]) == set(EXPECTED_VALUES)
    assert len(apple_financial_data_df) == 52
    assert not apple_financial_data_df.duplicated(
        subset=["Fiscal Year", "Metric"]
    ).any()
    assert not apple_financial_data_df["Value"].isna().any()

    actual = apple_financial_data_df.set_index(["Fiscal Year", "Metric"])
    for fiscal_year, metrics in EXPECTED_VALUES.items():
        assert set(actual.loc[fiscal_year].index) == set(EXPECTED_DETAILS)
        for metric, expected_value in metrics.items():
            assert actual.loc[(fiscal_year, metric), "Value"] == expected_value


def test_task_3_preserves_units_statements_and_filing_provenance() -> None:
    for row in apple_financial_data_df.to_dict("records"):
        expected_units, expected_statement = EXPECTED_DETAILS[row["Metric"]]
        assert row["Units"] == expected_units
        assert row["Financial Statement"] == expected_statement
        assert row["Source"] == "Apple Form 10-K"
        assert row["Source Date"] == EXPECTED_SOURCE_DATES[row["Fiscal Year"]]
