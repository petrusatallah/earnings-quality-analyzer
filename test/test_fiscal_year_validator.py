"""Focused tests for Task 86 annual fiscal-year validation."""

import sys
from dataclasses import dataclass, replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.financial_statement_fetcher import FactStatus  # noqa: E402
from Data.fiscal_year_validator import (  # noqa: E402
    FiscalMetricType,
    validate_annual_fiscal_year,
)


@dataclass(frozen=True)
class Record:
    metric_name: str
    fiscal_year: object
    period_start: object = None
    period_end: object = None
    balance_sheet_date: object = None
    status: FactStatus = FactStatus.RETRIEVED
    filing_form: str = "10-K"
    accession_number: str = "0001"
    source_url: str = "https://www.sec.gov/example"


def duration(**changes: object) -> Record:
    base = Record("Revenue", 2024, "2023-10-01", "2024-09-28")
    return replace(base, **changes)


def point(**changes: object) -> Record:
    base = Record("Inventory", 2024, balance_sheet_date="2024-09-28")
    return replace(base, **changes)


def test_valid_annual_duration_passes() -> None:
    result = validate_annual_fiscal_year(duration(), 2024)
    assert result.status is FactStatus.RETRIEVED
    assert result.metric_type is FiscalMetricType.ANNUAL_DURATION


def test_duration_wrong_fiscal_year_needs_validation() -> None:
    assert validate_annual_fiscal_year(duration(fiscal_year=2023), 2024).status is FactStatus.NEEDS_VALIDATION


def test_quarterly_duration_needs_validation() -> None:
    record = duration(period_start="2024-07-01", period_end="2024-09-28")
    assert validate_annual_fiscal_year(record, 2024).status is FactStatus.NEEDS_VALIDATION


def test_ytd_duration_needs_validation() -> None:
    record = duration(period_start="2024-01-01", period_end="2024-09-28")
    assert validate_annual_fiscal_year(record, 2024).status is FactStatus.NEEDS_VALIDATION


def test_valid_point_in_time_at_fiscal_year_end_passes() -> None:
    result = validate_annual_fiscal_year(point(), 2024, fiscal_year_end_date="2024-09-28")
    assert result.status is FactStatus.RETRIEVED
    assert result.metric_type is FiscalMetricType.POINT_IN_TIME


def test_point_in_time_wrong_fiscal_year_needs_validation() -> None:
    result = validate_annual_fiscal_year(point(fiscal_year=2023), 2024, fiscal_year_end_date="2024-09-28")
    assert result.status is FactStatus.NEEDS_VALIDATION


def test_point_date_not_fiscal_year_end_needs_validation() -> None:
    result = validate_annual_fiscal_year(point(balance_sheet_date="2024-06-29"), 2024, fiscal_year_end_date="2024-09-28")
    assert result.status is FactStatus.NEEDS_VALIDATION


def test_missing_fiscal_year_metadata_needs_validation() -> None:
    assert validate_annual_fiscal_year(duration(fiscal_year=None), 2024).status is FactStatus.NEEDS_VALIDATION


def test_missing_required_period_or_date_needs_validation() -> None:
    assert validate_annual_fiscal_year(duration(period_start=None), 2024).status is FactStatus.NEEDS_VALIDATION
    assert validate_annual_fiscal_year(point(balance_sheet_date=None), 2024, fiscal_year_end_date="2024-09-28").status is FactStatus.NEEDS_VALIDATION


def test_existing_missing_remains_missing() -> None:
    assert validate_annual_fiscal_year(duration(status=FactStatus.MISSING), 2024).status is FactStatus.MISSING


def test_existing_needs_validation_is_not_upgraded() -> None:
    record = duration(status=FactStatus.NEEDS_VALIDATION)
    assert validate_annual_fiscal_year(record, 2024).status is FactStatus.NEEDS_VALIDATION


def test_no_relabelling_or_period_substitution_and_metadata_preserved() -> None:
    record = duration(fiscal_year=2023, accession_number="A-1", source_url="source")
    result = validate_annual_fiscal_year(record, 2024)
    assert result.extracted_fiscal_year == 2023
    assert result.period_start == record.period_start
    assert result.period_end == record.period_end
    assert result.accession_number == "A-1"
    assert result.source_url == "source"
    assert result.original_record is record


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Task 86 fiscal-year validation tests passed")
