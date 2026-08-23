"""Focused tests for Task 99's fixed manual verification benchmark."""

import ast
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Data.manual_verified_answer_sheet import MANUAL_VERIFIED_ANSWER_SHEET  # noqa: E402


REQUIRED_TRACE_FIELDS = {"source", "data", "formula_or_rule", "expected_result"}
EXPECTED_YEARS = [2022, 2023, 2024, 2025]
EXPECTED_RAW_METRICS = {
    "Revenue", "Net Income", "Operating Cash Flow", "Accounts Receivable",
    "Inventory", "Accounts Payable", "Depreciation & Amortization",
    "Capital Expenditures", "Stock-Based Compensation", "Shares Outstanding",
    "Tax Expense", "Deferred Tax Assets", "Deferred Tax Liabilities",
}


def test_answer_sheet_has_required_sections_and_benchmark_identity() -> None:
    sheet = MANUAL_VERIFIED_ANSWER_SHEET

    assert set(sheet) == {
        "benchmark",
        "raw_financial_data",
        "calculated_financial_metrics",
        "red_flag_results",
        "normalized_earnings_results",
    }
    assert sheet["benchmark"]["company"] == "Apple Inc."
    assert sheet["benchmark"]["ticker"] == "AAPL"
    assert sheet["benchmark"]["fiscal_years"] == EXPECTED_YEARS


def test_raw_financial_data_is_complete_and_traceable() -> None:
    raw = MANUAL_VERIFIED_ANSWER_SHEET["raw_financial_data"]

    assert sorted(raw) == EXPECTED_YEARS
    for fiscal_year, record in raw.items():
        assert REQUIRED_TRACE_FIELDS.issubset(record)
        assert record["source"]["name"] == "Apple Form 10-K"
        assert record["source"]["source_date"] == {
            2022: "2022-10-28", 2023: "2023-11-03",
            2024: "2024-11-01", 2025: "2025-10-31",
        }[fiscal_year]
        assert set(record["data"]) == EXPECTED_RAW_METRICS
        assert set(record["expected_result"]) == EXPECTED_RAW_METRICS
        for metric, detail in record["data"].items():
            assert detail["value"] == record["expected_result"][metric]
            assert detail["units"] in {"USD millions", "millions of shares"}
            assert detail["financial_statement"]


def test_calculations_red_flags_and_normalization_have_traceability_fields() -> None:
    sheet = MANUAL_VERIFIED_ANSWER_SHEET

    for record in sheet["calculated_financial_metrics"].values():
        assert REQUIRED_TRACE_FIELDS.issubset(record)
    for record in sheet["red_flag_results"].values():
        assert REQUIRED_TRACE_FIELDS.issubset(record)
    assert REQUIRED_TRACE_FIELDS.issubset(sheet["normalized_earnings_results"])


def test_fixed_expected_answers_match_reviewed_apple_anchors() -> None:
    sheet = MANUAL_VERIFIED_ANSWER_SHEET
    raw = sheet["raw_financial_data"]
    calculations = sheet["calculated_financial_metrics"]
    flags = sheet["red_flag_results"]
    normalized = sheet["normalized_earnings_results"]["expected_result"]

    assert raw[2022]["expected_result"]["Inventory"] == 4946
    assert raw[2025]["expected_result"]["Revenue"] == 416161
    assert calculations["free_cash_flow"]["expected_result"] == {
        2022: 111443, 2023: 99584, 2024: 108807, 2025: 98767
    }
    assert calculations["working_capital"]["expected_result"][2023][
        "net_working_capital_cash_effect"
    ] == -4213
    assert calculations["working_capital"]["expected_result"][2024][
        "net_working_capital_cash_effect"
    ] == 1492
    assert flags["accrual_quality"]["expected_result"][2025] == {
        "ar_flag": True,
        "ni_ocf_flag": True,
        "combined_accrual_flag": True,
        "signal": "Strong accrual warning",
        "severity": "High",
    }
    assert flags["working_capital"]["expected_result"][2024][
        "ap_classification"
    ] == "Normal supplier financing pattern"
    assert flags["deferred_taxes"]["expected_result"][2023][
        "overall_tax_severity"
    ] == "Medium"
    assert flags["overall_severity"]["expected_result"]["benchmark"][
        "severity"
    ] == "Material Concern"
    assert normalized[2024]["normalized_net_income"] == 103936
    assert normalized[2024]["difference"] == 10200
    assert normalized[2024]["large_difference_flag"] is True
    assert normalized[2024]["overall_severity"] == "Medium"


def test_first_year_missing_growth_values_are_explicit_not_invented() -> None:
    calculations = MANUAL_VERIFIED_ANSWER_SHEET["calculated_financial_metrics"]

    assert calculations["capex"]["data"][2022]["previous_capex"] is None
    assert calculations["capex"]["expected_result"][2022]["capex_growth"] is None
    assert calculations["sbc_and_shares"]["data"][2022]["previous_shares"] is None
    assert calculations["sbc_and_shares"]["expected_result"][2022][
        "shares_growth"
    ] is None
    assert calculations["deferred_taxes"]["expected_result"][2022][
        "dta_growth"
    ] is None


def test_answer_sheet_is_literal_and_independent_of_production_modules() -> None:
    source_path = PROJECT_ROOT / "Data" / "manual_verified_answer_sheet.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "Analysis." not in source
    assert "Calculations." not in source
    assert "from Data" not in source
    assert "import Data" not in source
    assert not [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Call))
    ]


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Task 99 manual verified answer sheet tests passed")
