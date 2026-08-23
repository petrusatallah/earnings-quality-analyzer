"""Focused tests for Task 85 annual duplicate-value validation."""

import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.duplicate_value_validator import (  # noqa: E402
    DuplicateClassification,
    validate_annual_duplicates,
)
from Data.financial_statement_fetcher import FactStatus  # noqa: E402


@dataclass(frozen=True)
class Record:
    metric_name: str
    fiscal_year: int
    raw_sec_value: object
    raw_unit: object = "USD"
    status: FactStatus = FactStatus.RETRIEVED
    xbrl_concept: object = "ExampleConcept"
    accession_number: object = "0001"
    source_url: object = "https://www.sec.gov/example"


def test_one_record_no_duplicate() -> None:
    result, = validate_annual_duplicates([Record("Revenue", 2024, 100)])
    assert result.classification is DuplicateClassification.NO_DUPLICATE
    assert result.matching_record_count == 1


def test_same_value_different_metrics_not_duplicate() -> None:
    results = validate_annual_duplicates([
        Record("Revenue", 2024, 100), Record("Net Income", 2024, 100)
    ])
    assert len(results) == 2
    assert all(r.classification is DuplicateClassification.NO_DUPLICATE for r in results)


def test_same_metric_value_different_years_not_duplicate() -> None:
    results = validate_annual_duplicates([
        Record("Revenue", 2023, 100), Record("Revenue", 2024, 100)
    ])
    assert len(results) == 2
    assert all(r.classification is DuplicateClassification.NO_DUPLICATE for r in results)


def test_exact_duplicate_records_are_reported() -> None:
    record = Record("Revenue", 2024, 100)
    result, = validate_annual_duplicates([record, record])
    assert result.classification is DuplicateClassification.IDENTICAL_DUPLICATE
    assert result.matching_record_count == 2
    assert result.original_records == (record, record)


def test_different_values_are_conflicting_and_need_validation() -> None:
    result, = validate_annual_duplicates([
        Record("Revenue", 2024, 100), Record("Revenue", 2024, 101)
    ])
    assert result.classification is DuplicateClassification.CONFLICTING_DUPLICATE
    assert result.status is FactStatus.NEEDS_VALIDATION
    assert result.involved_values == (100, 101)


def test_conflicting_units_need_validation() -> None:
    result, = validate_annual_duplicates([
        Record("Revenue", 2024, 100, "USD"), Record("Revenue", 2024, 100, "EUR")
    ])
    assert result.classification is DuplicateClassification.CONFLICTING_DUPLICATE
    assert result.status is FactStatus.NEEDS_VALIDATION


def test_existing_needs_validation_is_not_upgraded() -> None:
    result, = validate_annual_duplicates([
        Record("Revenue", 2024, 100, status=FactStatus.NEEDS_VALIDATION)
    ])
    assert result.status is FactStatus.NEEDS_VALIDATION


def test_existing_missing_is_not_upgraded() -> None:
    result, = validate_annual_duplicates([
        Record("Revenue", 2024, None, status=FactStatus.MISSING)
    ])
    assert result.status is FactStatus.MISSING


def test_original_records_and_provenance_are_preserved() -> None:
    records = (
        Record("Revenue", 2024, 100, accession_number="A"),
        Record("Revenue", 2024, 100, accession_number="B"),
    )
    result, = validate_annual_duplicates(records)
    assert result.original_records == records
    assert result.involved_provenance[0].accession_number == "A"
    assert result.involved_provenance[1].accession_number == "B"


def test_validator_does_not_combine_or_choose_duplicates() -> None:
    records = (Record("Revenue", 2024, 40), Record("Revenue", 2024, 60))
    before = tuple(records)
    result, = validate_annual_duplicates(records)
    assert result.involved_values == (40, 60)
    assert result.original_records == before
    assert not hasattr(result, "selected_value")
    assert tuple(records) == before


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Task 85 duplicate-value validation tests passed")
