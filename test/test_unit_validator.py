"""Focused tests for Task 84 annual raw-unit validation."""

import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.financial_statement_fetcher import FactStatus  # noqa: E402
from Data.unit_validator import ExpectedUnitType, validate_annual_unit  # noqa: E402


@dataclass(frozen=True)
class Record:
    metric_name: str
    fiscal_year: int
    raw_sec_value: object
    raw_unit: object
    status: FactStatus = FactStatus.RETRIEVED
    normalized_usd_millions: object = None


def test_usd_revenue_passes() -> None:
    result = validate_annual_unit(Record("Revenue", 2025, 10, "USD"))
    assert result.validation_status is FactStatus.RETRIEVED
    assert result.expected_unit_type is ExpectedUnitType.MONETARY


def test_eur_revenue_passes_and_remains_eur_without_fx_conversion() -> None:
    record = Record("Revenue", 2025, 10, "EUR")
    result = validate_annual_unit(record)
    assert result.validation_status is FactStatus.RETRIEVED
    assert result.raw_unit == "EUR"
    assert record.raw_sec_value == 10
    assert record.normalized_usd_millions is None


def test_shares_unit_for_shares_outstanding_passes() -> None:
    result = validate_annual_unit(Record("Shares Outstanding", 2025, 10, "shares"))
    assert result.validation_status is FactStatus.RETRIEVED
    assert result.expected_unit_type is ExpectedUnitType.SHARE_COUNT


def test_shares_unit_for_revenue_needs_validation() -> None:
    result = validate_annual_unit(Record("Revenue", 2025, 10, "shares"))
    assert result.validation_status is FactStatus.NEEDS_VALIDATION
    assert result.reason


def test_currency_unit_for_shares_outstanding_needs_validation() -> None:
    result = validate_annual_unit(Record("Shares Outstanding", 2025, 10, "USD"))
    assert result.validation_status is FactStatus.NEEDS_VALIDATION


def test_missing_and_blank_units_need_validation() -> None:
    assert validate_annual_unit(Record("Revenue", 2025, 10, None)).status is FactStatus.NEEDS_VALIDATION
    assert validate_annual_unit(Record("Revenue", 2025, 10, "  ")).status is FactStatus.NEEDS_VALIDATION


def test_already_missing_value_stays_missing() -> None:
    result = validate_annual_unit(Record("Revenue", 2025, None, None, FactStatus.MISSING))
    assert result.validation_status is FactStatus.MISSING


def test_zero_monetary_value_with_currency_passes() -> None:
    assert validate_annual_unit(Record("Revenue", 2025, 0, "CAD")).status is FactStatus.RETRIEVED


def test_raw_unit_is_preserved_exactly() -> None:
    record = Record("Revenue", 2025, 10, " USD ")
    result = validate_annual_unit(record)
    assert result.raw_unit == " USD "
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert record.raw_unit == " USD "


def test_no_silent_conversion_of_shares_to_monetary_units() -> None:
    record = Record("Shares Outstanding", 2025, 2_000_000, "shares")
    result = validate_annual_unit(record)
    assert result.raw_unit == "shares"
    assert record.raw_sec_value == 2_000_000
    assert record.normalized_usd_millions is None


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Task 84 unit validation tests passed")
