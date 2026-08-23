"""Validate completeness of required annual financial extractions.

This module only classifies values already produced by the extraction layer.  It
does not retrieve, derive, replace, or fill financial values.
"""

from dataclasses import dataclass
from enum import Enum
import math
from numbers import Real
from typing import Any, Iterable, Mapping, Tuple

from Data.financial_statement_fetcher import FactStatus


REQUIRED_ANNUAL_CORE_METRICS: Tuple[str, ...] = (
    "Revenue",
    "Net Income",
    "OCF",
    "AR",
    "Inventory",
    "AP",
    "D&A",
    "CapEx",
    "SBC",
    "Shares Outstanding",
    "Income Tax Expense",
    "DTA",
    "DTL",
)

_METRIC_ALIASES = {
    "revenue": "Revenue",
    "net income": "Net Income",
    "ocf": "OCF",
    "operating cash flow": "OCF",
    "ar": "AR",
    "accounts receivable": "AR",
    "inventory": "Inventory",
    "ap": "AP",
    "accounts payable": "AP",
    "d&a": "D&A",
    "depreciation & amortization": "D&A",
    "depreciation and amortization": "D&A",
    "capex": "CapEx",
    "capital expenditures": "CapEx",
    "sbc": "SBC",
    "stock-based compensation": "SBC",
    "stock based compensation": "SBC",
    "shares outstanding": "Shares Outstanding",
    "income tax expense": "Income Tax Expense",
    "tax expense": "Income Tax Expense",
    "dta": "DTA",
    "deferred tax assets": "DTA",
    "dtl": "DTL",
    "deferred tax liabilities": "DTL",
}


class ValidationStatus(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    NEEDS_VALIDATION = "NEEDS VALIDATION"


@dataclass(frozen=True)
class MetricYearValidation:
    metric: str
    fiscal_year: int
    status: ValidationStatus


@dataclass(frozen=True)
class MissingDataValidationResult:
    requested_fiscal_years: Tuple[int, ...]
    statuses: Tuple[MetricYearValidation, ...]
    missing_items: Tuple[MetricYearValidation, ...]
    needs_validation_items: Tuple[MetricYearValidation, ...]
    counts: Mapping[str, int]
    total_items: int
    overall_complete: bool

    @property
    def present_count(self) -> int:
        return self.counts[ValidationStatus.PRESENT.value]

    @property
    def missing_count(self) -> int:
        return self.counts[ValidationStatus.MISSING.value]

    @property
    def needs_validation_count(self) -> int:
        return self.counts[ValidationStatus.NEEDS_VALIDATION.value]

    def status_for(self, metric: str, fiscal_year: int) -> ValidationStatus:
        """Return the classification for one required metric and fiscal year."""

        canonical = _canonical_metric(metric)
        for item in self.statuses:
            if item.metric == canonical and item.fiscal_year == fiscal_year:
                return item.status
        raise KeyError((metric, fiscal_year))


def _attribute(record: Any, *names: str) -> Any:
    if isinstance(record, Mapping):
        for name in names:
            if name in record:
                return record[name]
    else:
        for name in names:
            if hasattr(record, name):
                return getattr(record, name)
    return None


def _canonical_metric(metric: Any) -> str:
    key = " ".join(str(metric).strip().lower().split())
    try:
        return _METRIC_ALIASES[key]
    except KeyError as error:
        raise KeyError(f"Unknown annual core metric: {metric!r}") from error


def _status_text(record: Any) -> str:
    status = _attribute(record, "status", "extraction_status", "Status")
    return str(getattr(status, "value", status) or "").strip().upper().replace("_", " ")


def _has_usable_value(record: Any) -> bool:
    value = _attribute(
        record,
        "raw_sec_value",
        "raw_value",
        "raw_amount",
        "value",
        "Value",
    )
    # Financial extraction values must be numeric.  bool is deliberately
    # excluded even though it is a subclass of int; zero remains valid.
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def _classify_records(records: Tuple[Any, ...]) -> ValidationStatus:
    if not records:
        return ValidationStatus.MISSING

    classifications = []
    for record in records:
        status = _status_text(record)
        if status == FactStatus.MISSING.value:
            classifications.append(ValidationStatus.MISSING)
        elif (
            "VALIDATION" in status
            or "UNCERTAIN" in status
            or "CONFLICT" in status
            or status != FactStatus.RETRIEVED.value
            or not _has_usable_value(record)
        ):
            classifications.append(ValidationStatus.NEEDS_VALIDATION)
        else:
            classifications.append(ValidationStatus.PRESENT)

    if ValidationStatus.PRESENT in classifications:
        return ValidationStatus.PRESENT
    if ValidationStatus.NEEDS_VALIDATION in classifications:
        return ValidationStatus.NEEDS_VALIDATION
    return ValidationStatus.MISSING


def validate_annual_missing_data(
    extraction_data: Any,
    requested_fiscal_years: Iterable[int],
) -> MissingDataValidationResult:
    """Classify every required annual metric/year without filling any value."""

    years = tuple(dict.fromkeys(int(year) for year in requested_fiscal_years))
    source_records = _attribute(extraction_data, "values")
    if source_records is None:
        source_records = extraction_data
    records = tuple(source_records)

    indexed: dict[tuple[str, int], list[Any]] = {}
    for record in records:
        metric = _attribute(
            record, "metric_name", "financial_field", "metric", "Metric"
        )
        year = _attribute(record, "fiscal_year", "Fiscal Year")
        if metric is None or year is None:
            continue
        try:
            canonical_metric = _canonical_metric(metric)
            canonical_year = int(year)
        except (KeyError, TypeError, ValueError):
            continue
        if canonical_year in years:
            indexed.setdefault((canonical_metric, canonical_year), []).append(record)

    statuses = tuple(
        MetricYearValidation(
            metric=metric,
            fiscal_year=year,
            status=_classify_records(tuple(indexed.get((metric, year), ()))),
        )
        for year in years
        for metric in REQUIRED_ANNUAL_CORE_METRICS
    )
    missing = tuple(item for item in statuses if item.status is ValidationStatus.MISSING)
    needs_validation = tuple(
        item for item in statuses if item.status is ValidationStatus.NEEDS_VALIDATION
    )
    present_count = sum(item.status is ValidationStatus.PRESENT for item in statuses)
    counts = {
        ValidationStatus.PRESENT.value: present_count,
        ValidationStatus.MISSING.value: len(missing),
        ValidationStatus.NEEDS_VALIDATION.value: len(needs_validation),
    }
    return MissingDataValidationResult(
        requested_fiscal_years=years,
        statuses=statuses,
        missing_items=missing,
        needs_validation_items=needs_validation,
        counts=counts,
        total_items=len(statuses),
        overall_complete=present_count == len(statuses),
    )


# Concise alias for callers that already know they are validating annual data.
validate_missing_data = validate_annual_missing_data
