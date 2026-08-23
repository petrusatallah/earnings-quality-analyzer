"""Focused tests for Task 88 immutable manual corrections."""

import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.financial_statement_fetcher import FactStatus  # noqa: E402
from Data.manual_corrections import (  # noqa: E402
    CorrectionStatus,
    create_manual_correction,
    effective_value,
    revert_manual_correction,
)


@dataclass(frozen=True)
class Record:
    metric_name: str
    fiscal_year: int
    raw_sec_value: object
    raw_unit: object = "USD"
    status: FactStatus = FactStatus.RETRIEVED
    accession_number: object = "A-1"
    source_url: object = "https://www.sec.gov/source"


def assert_raises(error_type: type[Exception], function, *args, **kwargs) -> None:
    try:
        function(*args, **kwargs)
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__}")


def test_correction_preserves_original_and_becomes_effective() -> None:
    record = Record("Revenue", 2024, 100)
    correction = create_manual_correction(record, 110, "Correct filing value")
    assert correction.original_value == 100
    assert correction.corrected_value == 110
    assert effective_value(record, correction) == 110
    assert correction.correction_status is CorrectionStatus.ACTIVE


def test_correction_requires_reason() -> None:
    assert_raises(
        ValueError,
        create_manual_correction,
        Record("Revenue", 2024, 100),
        110,
        "  ",
    )


def test_original_unit_is_preserved_and_cannot_change() -> None:
    record = Record("Revenue", 2024, 100, "EUR")
    correction = create_manual_correction(record, 110, "Correction", corrected_unit="EUR")
    assert correction.original_unit == "EUR"
    assert_raises(
        ValueError, create_manual_correction, record, 110, "Correction", corrected_unit="USD"
    )


def test_fiscal_year_and_metric_cannot_change() -> None:
    record = Record("Revenue", 2024, 100)
    assert_raises(
        ValueError, create_manual_correction, record, 110, "Correction", fiscal_year=2023
    )
    assert_raises(
        ValueError, create_manual_correction, record, 110, "Correction", metric="Net Income"
    )


def test_provenance_is_preserved() -> None:
    record = Record("Revenue", 2024, 100, accession_number="SEC-42")
    correction = create_manual_correction(record, 110, "Correction")
    assert correction.original_provenance.accession_number == "SEC-42"
    assert correction.original_provenance.source_url == record.source_url


def test_revert_restores_original_effective_value() -> None:
    record = Record("Revenue", 2024, 100)
    active = create_manual_correction(record, 110, "Correction")
    reverted = revert_manual_correction(active)
    assert effective_value(record, reverted) == 100
    assert reverted.correction_status is CorrectionStatus.REVERTED
    assert active.is_active


def test_original_record_is_not_mutated() -> None:
    record = Record("Revenue", 2024, 100)
    before = record
    correction = create_manual_correction(record, 110, "Correction")
    assert record == before
    assert record.raw_sec_value == 100
    assert correction.original_record is record


def test_missing_value_can_receive_explicit_correction_without_invention() -> None:
    record = Record("Inventory", 2024, None, status=FactStatus.MISSING,
                    accession_number=None, source_url=None)
    correction = create_manual_correction(record, 25, "Entered from reviewed filing")
    assert correction.original_value is None
    assert correction.original_extraction_status is FactStatus.MISSING
    assert correction.original_provenance.accession_number is None
    assert correction.original_provenance.source_url is None
    assert effective_value(record, correction) == 25


def test_different_metric_year_corrections_remain_separate() -> None:
    revenue = Record("Revenue", 2024, 100)
    income = Record("Net Income", 2025, 20)
    revenue_correction = create_manual_correction(revenue, 101, "Revenue correction")
    income_correction = create_manual_correction(income, 21, "Income correction")
    assert (revenue_correction.metric, revenue_correction.fiscal_year) != (
        income_correction.metric, income_correction.fiscal_year
    )
    assert effective_value(revenue, revenue_correction) == 101
    assert effective_value(income, income_correction) == 21


def test_correction_cannot_be_applied_to_another_record() -> None:
    revenue = Record("Revenue", 2024, 100)
    correction = create_manual_correction(revenue, 101, "Correction")
    assert_raises(
        ValueError, effective_value, Record("Revenue", 2025, 100), correction
    )


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Task 88 manual correction tests passed")
