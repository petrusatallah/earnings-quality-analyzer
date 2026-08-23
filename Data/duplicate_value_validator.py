"""Detect and classify duplicate annual core-metric extraction records.

The validator is intentionally non-destructive: it never selects, combines,
rewrites, or removes an extraction record.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Tuple

from Data.financial_statement_fetcher import FactStatus


REQUIRED_ANNUAL_CORE_METRICS: Tuple[str, ...] = (
    "Revenue",
    "Net Income",
    "Operating Cash Flow",
    "Accounts Receivable",
    "Inventory",
    "Accounts Payable",
    "Depreciation & Amortization",
    "Capital Expenditures",
    "Stock-Based Compensation",
    "Shares Outstanding",
    "Income Tax Expense",
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
)

_METRIC_ALIASES = {
    "revenue": "Revenue",
    "net income": "Net Income",
    "operating cash flow": "Operating Cash Flow",
    "ocf": "Operating Cash Flow",
    "accounts receivable": "Accounts Receivable",
    "ar": "Accounts Receivable",
    "inventory": "Inventory",
    "accounts payable": "Accounts Payable",
    "ap": "Accounts Payable",
    "depreciation & amortization": "Depreciation & Amortization",
    "depreciation and amortization": "Depreciation & Amortization",
    "d&a": "Depreciation & Amortization",
    "capital expenditures": "Capital Expenditures",
    "capex": "Capital Expenditures",
    "stock-based compensation": "Stock-Based Compensation",
    "stock based compensation": "Stock-Based Compensation",
    "sbc": "Stock-Based Compensation",
    "shares outstanding": "Shares Outstanding",
    "income tax expense": "Income Tax Expense",
    "tax expense": "Income Tax Expense",
    "deferred tax assets": "Deferred Tax Assets",
    "dta": "Deferred Tax Assets",
    "deferred tax liabilities": "Deferred Tax Liabilities",
    "dtl": "Deferred Tax Liabilities",
}


class DuplicateClassification(str, Enum):
    NO_DUPLICATE = "NO DUPLICATE"
    IDENTICAL_DUPLICATE = "IDENTICAL DUPLICATE"
    CONFLICTING_DUPLICATE = "CONFLICTING DUPLICATE"


@dataclass(frozen=True)
class DuplicateRecordProvenance:
    xbrl_taxonomy: Any
    xbrl_concept: Any
    accession_number: Any
    source_identifier: Any
    source_url: Any


@dataclass(frozen=True)
class DuplicateValidationResult:
    metric: str
    fiscal_year: int
    duplicate_classification: DuplicateClassification
    matching_record_count: int
    involved_values: Tuple[Any, ...]
    involved_units: Tuple[Any, ...]
    involved_provenance: Tuple[DuplicateRecordProvenance, ...]
    validation_status: FactStatus
    explanation: str
    original_records: Tuple[Any, ...]

    @property
    def status(self) -> FactStatus:
        return self.validation_status

    @property
    def classification(self) -> DuplicateClassification:
        return self.duplicate_classification

    @property
    def involved_source_identifiers(self) -> Tuple[Any, ...]:
        return tuple(item.source_identifier for item in self.involved_provenance)


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
        raise ValueError(f"Unsupported annual core metric: {metric!r}") from error


def _status_text(record: Any) -> str:
    status = _attribute(record, "status", "extraction_status", "Status")
    return str(getattr(status, "value", status) or "").strip().upper().replace("_", " ")


def _raw_value(record: Any) -> Any:
    return _attribute(
        record, "raw_sec_value", "raw_value", "raw_amount", "value", "Value"
    )


def _raw_unit(record: Any) -> Any:
    return _attribute(record, "raw_unit", "unit", "Raw Unit")


def _provenance(record: Any) -> DuplicateRecordProvenance:
    """Return auditable source identifiers without manufacturing missing data."""

    return DuplicateRecordProvenance(
        xbrl_taxonomy=_attribute(record, "xbrl_taxonomy", "XBRL Taxonomy"),
        xbrl_concept=_attribute(record, "xbrl_concept", "XBRL Concept"),
        accession_number=_attribute(record, "accession_number", "Accession Number"),
        source_identifier=_attribute(
            record, "sec_source_identifier", "source_identifier", "Source"
        ),
        source_url=_attribute(record, "source_url", "Source URL"),
    )


def _material_signature(record: Any) -> Tuple[Any, ...]:
    return (_raw_value(record), _raw_unit(record), _status_text(record), _provenance(record))


def _resulting_status(
    records: Tuple[Any, ...], classification: DuplicateClassification
) -> FactStatus:
    if classification is DuplicateClassification.CONFLICTING_DUPLICATE:
        return FactStatus.NEEDS_VALIDATION
    statuses = {_status_text(record) for record in records}
    if FactStatus.NEEDS_VALIDATION.value in statuses:
        return FactStatus.NEEDS_VALIDATION
    if FactStatus.MISSING.value in statuses:
        return FactStatus.MISSING
    if statuses == {FactStatus.RETRIEVED.value}:
        return FactStatus.RETRIEVED
    return FactStatus.NEEDS_VALIDATION


def _validate_group(
    metric: str, fiscal_year: int, records: Tuple[Any, ...]
) -> DuplicateValidationResult:
    if len(records) == 1:
        classification = DuplicateClassification.NO_DUPLICATE
        explanation = "Exactly one annual extraction record exists for this metric/year."
    elif all(_material_signature(record) == _material_signature(records[0]) for record in records[1:]):
        classification = DuplicateClassification.IDENTICAL_DUPLICATE
        explanation = (
            "Multiple records materially represent the same annual fact; all duplicates "
            "are reported and retained."
        )
    else:
        classification = DuplicateClassification.CONFLICTING_DUPLICATE
        explanation = (
            "Multiple records for the same metric/year conflict in value, unit, status, "
            "XBRL concept, accession, or source provenance; no record was selected."
        )

    return DuplicateValidationResult(
        metric=metric,
        fiscal_year=fiscal_year,
        duplicate_classification=classification,
        matching_record_count=len(records),
        involved_values=tuple(_raw_value(record) for record in records),
        involved_units=tuple(_raw_unit(record) for record in records),
        involved_provenance=tuple(_provenance(record) for record in records),
        validation_status=_resulting_status(records, classification),
        explanation=explanation,
        original_records=records,
    )


def validate_annual_duplicates(records: Iterable[Any]) -> Tuple[DuplicateValidationResult, ...]:
    """Classify duplicate records independently for each annual metric/year."""

    source_records = _attribute(records, "values")
    if source_records is None:
        source_records = records

    groups: dict[tuple[str, int], list[Any]] = {}
    for record in source_records:
        metric = _canonical_metric(
            _attribute(record, "metric_name", "financial_field", "metric", "Metric")
        )
        year = _attribute(record, "fiscal_year", "Fiscal Year")
        if year is None:
            raise ValueError("Annual duplicate validation requires a fiscal year")
        key = (metric, int(year))
        groups.setdefault(key, []).append(record)

    return tuple(
        _validate_group(metric, fiscal_year, tuple(group_records))
        for (metric, fiscal_year), group_records in groups.items()
    )


validate_duplicate_values = validate_annual_duplicates
