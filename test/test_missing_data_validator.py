"""Focused tests for Task 83 annual missing-data validation."""

import sys
from dataclasses import dataclass, replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.financial_statement_fetcher import FactStatus  # noqa: E402
from Data.missing_data_validator import (  # noqa: E402
    REQUIRED_ANNUAL_CORE_METRICS,
    ValidationStatus,
    validate_annual_missing_data,
)


@dataclass(frozen=True)
class Record:
    metric_name: str
    fiscal_year: int
    raw_sec_value: object
    status: FactStatus


def complete_records(*years: int) -> tuple[Record, ...]:
    return tuple(
        Record(metric, year, 100, FactStatus.RETRIEVED)
        for year in years
        for metric in REQUIRED_ANNUAL_CORE_METRICS
    )


def test_complete_dataset() -> None:
    result = validate_annual_missing_data(complete_records(2023, 2024), [2023, 2024])
    assert result.overall_complete
    assert result.counts == {"PRESENT": 26, "MISSING": 0, "NEEDS VALIDATION": 0}


def test_one_missing_metric() -> None:
    records = tuple(r for r in complete_records(2024) if r.metric_name != "Revenue")
    result = validate_annual_missing_data(records, [2024])
    assert result.status_for("Revenue", 2024) is ValidationStatus.MISSING
    assert len(result.missing_items) == 1


def test_multiple_missing_metrics_across_different_years() -> None:
    records = tuple(
        r for r in complete_records(2023, 2024)
        if (r.metric_name, r.fiscal_year) not in {("AR", 2023), ("DTA", 2024)}
    )
    result = validate_annual_missing_data(records, [2023, 2024])
    assert {(item.metric, item.fiscal_year) for item in result.missing_items} == {
        ("AR", 2023), ("DTA", 2024)
    }


def test_needs_validation_is_not_present() -> None:
    records = list(complete_records(2024))
    records[0] = replace(records[0], status=FactStatus.NEEDS_VALIDATION)
    result = validate_annual_missing_data(records, [2024])
    assert result.status_for("Revenue", 2024) is ValidationStatus.NEEDS_VALIDATION
    assert not result.overall_complete


def test_missing_record_entirely() -> None:
    result = validate_annual_missing_data([], [2025])
    assert len(result.missing_items) == 13
    assert result.total_items == 13


def test_zero_numeric_value_is_present() -> None:
    records = list(complete_records(2024))
    records[0] = replace(records[0], raw_sec_value=0)
    result = validate_annual_missing_data(records, [2024])
    assert result.status_for("Revenue", 2024) is ValidationStatus.PRESENT


def test_no_silent_filling_or_substitution() -> None:
    records = list(complete_records(2023, 2024))
    records = [
        r for r in records if not (r.metric_name == "Inventory" and r.fiscal_year == 2024)
    ]
    before = tuple(records)
    result = validate_annual_missing_data(records, [2023, 2024])
    assert result.status_for("Inventory", 2023) is ValidationStatus.PRESENT
    assert result.status_for("Inventory", 2024) is ValidationStatus.MISSING
    assert tuple(records) == before


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Task 83 missing-data validation tests passed")
