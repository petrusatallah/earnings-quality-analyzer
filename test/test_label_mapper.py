"""Focused tests for Task 87 annual financial label mapping."""

import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.financial_statement_fetcher import FactStatus  # noqa: E402
from Data.label_mapper import LabelMappingStatus, map_annual_label  # noqa: E402


@dataclass(frozen=True)
class Record:
    raw_label: str
    raw_value: object = 100
    status: FactStatus = FactStatus.RETRIEVED


def assert_maps(label: str, metric: str) -> None:
    result = map_annual_label(label)
    assert result.mapping_status is LabelMappingStatus.MAPPED
    assert result.standardized_metric == metric
    assert result.status is FactStatus.RETRIEVED


def test_exact_standard_label_maps() -> None:
    assert_maps("Revenue", "Revenue")


def test_receivable_variations_map() -> None:
    assert_maps("Receivables", "Accounts Receivable")
    assert_maps("Trade Receivables", "Accounts Receivable")


def test_capitalization_and_whitespace_differences_map() -> None:
    assert_maps("  operating CASH flow  ", "Operating Cash Flow")


def test_ampersand_and_and_variations_map() -> None:
    assert_maps("Depreciation and Amortization", "Depreciation & Amortization")
    assert_maps("Depreciation & Amortization", "Depreciation & Amortization")


def test_named_legitimate_variations_map() -> None:
    assert_maps("Share-Based Compensation", "Stock-Based Compensation")
    assert_maps("Cash Flow from Operations", "Operating Cash Flow")
    assert_maps("CapEx", "Capital Expenditures")


def test_broader_or_different_labels_are_not_mapped() -> None:
    for label in (
        "Accounts Payable and Accrued Liabilities",
        "Compensation Expense",
        "Weighted Average Shares Outstanding",
    ):
        result = map_annual_label(label)
        assert result.standardized_metric is None
        assert result.mapping_status is LabelMappingStatus.AMBIGUOUS
        assert result.status is FactStatus.NEEDS_VALIDATION


def test_unknown_label_is_unmapped_and_needs_validation() -> None:
    result = map_annual_label("Unrelated Metric")
    assert result.mapping_status is LabelMappingStatus.UNMAPPED
    assert result.standardized_metric is None
    assert result.status is FactStatus.NEEDS_VALIDATION


def test_original_raw_label_is_preserved() -> None:
    raw = "  TRADE Receivables  "
    result = map_annual_label(raw)
    assert result.raw_label == raw


def test_existing_missing_remains_missing() -> None:
    result = map_annual_label(Record("Revenue", status=FactStatus.MISSING))
    assert result.mapping_status is LabelMappingStatus.MAPPED
    assert result.status is FactStatus.MISSING


def test_existing_needs_validation_is_not_upgraded() -> None:
    record = Record("Revenue", status=FactStatus.NEEDS_VALIDATION)
    result = map_annual_label(record)
    assert result.standardized_metric == "Revenue"
    assert result.status is FactStatus.NEEDS_VALIDATION


def test_mapping_does_not_use_values_or_fuzzy_similarity() -> None:
    result_a = map_annual_label(Record("Revenues Other", raw_value=100))
    result_b = map_annual_label(Record("Revenues Other", raw_value=-999999))
    assert result_a.standardized_metric is None
    assert result_b.standardized_metric is None
    assert result_a.mapping_status is result_b.mapping_status is LabelMappingStatus.UNMAPPED


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Task 87 label mapping tests passed")
