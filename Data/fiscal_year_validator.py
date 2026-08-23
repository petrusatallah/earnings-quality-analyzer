"""Validate fiscal-year metadata for annual financial extraction records.

No period is inferred, relabelled, substituted, or selected by this module.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Tuple

from Data.financial_statement_fetcher import (
    FULL_YEAR_MAX_DAYS,
    FULL_YEAR_MIN_DAYS,
    FactStatus,
)


ANNUAL_DURATION_METRICS: Tuple[str, ...] = (
    "Revenue",
    "Net Income",
    "Operating Cash Flow",
    "Depreciation & Amortization",
    "Capital Expenditures",
    "Stock-Based Compensation",
    "Income Tax Expense",
)
POINT_IN_TIME_METRICS: Tuple[str, ...] = (
    "Accounts Receivable",
    "Inventory",
    "Accounts Payable",
    "Shares Outstanding",
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
)
REQUIRED_ANNUAL_CORE_METRICS = ANNUAL_DURATION_METRICS + POINT_IN_TIME_METRICS

_METRIC_ALIASES = {
    "revenue": "Revenue", "net income": "Net Income",
    "operating cash flow": "Operating Cash Flow", "ocf": "Operating Cash Flow",
    "accounts receivable": "Accounts Receivable", "ar": "Accounts Receivable",
    "inventory": "Inventory", "accounts payable": "Accounts Payable",
    "ap": "Accounts Payable",
    "depreciation & amortization": "Depreciation & Amortization",
    "depreciation and amortization": "Depreciation & Amortization",
    "d&a": "Depreciation & Amortization",
    "capital expenditures": "Capital Expenditures", "capex": "Capital Expenditures",
    "stock-based compensation": "Stock-Based Compensation",
    "stock based compensation": "Stock-Based Compensation", "sbc": "Stock-Based Compensation",
    "shares outstanding": "Shares Outstanding",
    "income tax expense": "Income Tax Expense",
    "tax expense": "Income Tax Expense",
    "deferred tax assets": "Deferred Tax Assets", "dta": "Deferred Tax Assets",
    "deferred tax liabilities": "Deferred Tax Liabilities", "dtl": "Deferred Tax Liabilities",
}


class FiscalMetricType(str, Enum):
    ANNUAL_DURATION = "ANNUAL DURATION"
    POINT_IN_TIME = "POINT IN TIME"


@dataclass(frozen=True)
class FiscalYearValidationResult:
    metric: str
    requested_fiscal_year: int
    extracted_fiscal_year: Optional[int]
    metric_type: FiscalMetricType
    period_start: Optional[str]
    period_end: Optional[str]
    balance_sheet_date: Optional[str]
    validation_status: FactStatus
    explanation: str
    filing_form: Optional[str]
    accession_number: Optional[str]
    source_url: Optional[str]
    original_record: Any
    period_metadata_valid: Optional[bool] = None

    @property
    def status(self) -> FactStatus:
        return self.validation_status


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


def _iso_date(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_period_metadata(
    metric_type: FiscalMetricType,
    extracted_year: Optional[int],
    requested_year: int,
    period_start: Any,
    period_end: Any,
    point_date: Any,
    expected_year_end: Any,
) -> tuple[bool, str]:
    if extracted_year is None:
        return False, "Extracted fiscal-year metadata is missing or malformed; no year was inferred."
    if extracted_year != requested_year:
        return False, (
            f"Extracted fiscal year {extracted_year} does not match requested fiscal year "
            f"{requested_year}; the fact was not relabelled."
        )
    if metric_type is FiscalMetricType.ANNUAL_DURATION:
        start_date, end_date = _iso_date(period_start), _iso_date(period_end)
        if start_date is None or end_date is None:
            return False, "A valid period start and end are required for an annual duration fact."
        if end_date < start_date:
            return False, "The duration period end precedes its start."
        period_days = (end_date - start_date).days
        if not FULL_YEAR_MIN_DAYS <= period_days <= FULL_YEAR_MAX_DAYS:
            return False, (
                f"The {period_days}-day period is not a full fiscal year; quarterly or "
                "YTD facts are not accepted in annual mode."
            )
        return True, "Fiscal-year and annual-period metadata are valid."

    actual_date = _iso_date(point_date)
    expected_date = _iso_date(expected_year_end)
    if actual_date is None:
        return False, "A valid balance-sheet/end date is required for a point-in-time fact."
    if expected_date is None:
        return False, (
            "The requested fiscal-year-end date is missing or ambiguous; it was not inferred."
        )
    if actual_date != expected_date:
        return False, (
            f"Point-in-time date {point_date!r} does not match fiscal-year-end "
            f"{expected_year_end!r}; no alternate period was selected."
        )
    return True, "Fiscal-year and annual-period metadata are valid."


def validate_annual_fiscal_year(
    record: Any,
    requested_fiscal_year: int,
    *,
    fiscal_year_end_date: Optional[str] = None,
) -> FiscalYearValidationResult:
    """Validate one record in annual mode against a requested fiscal year."""

    requested_year = int(requested_fiscal_year)
    metric = _canonical_metric(
        _attribute(record, "metric_name", "financial_field", "metric", "Metric")
    )
    metric_type = (
        FiscalMetricType.ANNUAL_DURATION
        if metric in ANNUAL_DURATION_METRICS
        else FiscalMetricType.POINT_IN_TIME
    )
    raw_year = _attribute(record, "fiscal_year", "Fiscal Year")
    try:
        extracted_year = int(raw_year) if raw_year is not None else None
    except (TypeError, ValueError):
        extracted_year = None
    period_start = _attribute(record, "period_start", "Period Start")
    period_end = _attribute(record, "period_end", "Period End")
    balance_sheet_date = _attribute(
        record, "balance_sheet_date", "Balance Sheet Date"
    )
    point_date = balance_sheet_date if balance_sheet_date is not None else period_end
    extraction_status = _status_text(record)
    expected_year_end = fiscal_year_end_date or _attribute(
        record, "fiscal_year_end_date", "expected_fiscal_year_end"
    )
    period_metadata_valid, metadata_reason = _validate_period_metadata(
        metric_type,
        extracted_year,
        requested_year,
        period_start,
        period_end,
        point_date,
        expected_year_end,
    )

    status = FactStatus.RETRIEVED
    reason = metadata_reason
    if extraction_status == FactStatus.MISSING.value:
        status = FactStatus.MISSING
        reason = "The underlying annual extracted value is already MISSING."
    elif extraction_status != FactStatus.RETRIEVED.value:
        status = FactStatus.NEEDS_VALIDATION
        reason = "The underlying extraction is not in a usable RETRIEVED state."
    elif not period_metadata_valid:
        status = FactStatus.NEEDS_VALIDATION

    return FiscalYearValidationResult(
        metric=metric,
        requested_fiscal_year=requested_year,
        extracted_fiscal_year=extracted_year,
        metric_type=metric_type,
        period_start=period_start,
        period_end=period_end,
        balance_sheet_date=balance_sheet_date,
        validation_status=status,
        explanation=reason,
        filing_form=_attribute(record, "filing_form", "Filing Form"),
        accession_number=_attribute(record, "accession_number", "Accession Number"),
        source_url=_attribute(record, "source_url", "Source URL"),
        original_record=record,
        period_metadata_valid=period_metadata_valid,
    )


def validate_annual_fiscal_years(
    records: Iterable[Any],
    requested_fiscal_year: int,
    *,
    fiscal_year_end_date: Optional[str] = None,
) -> Tuple[FiscalYearValidationResult, ...]:
    """Validate multiple records against the same requested annual period."""

    source_records = _attribute(records, "values")
    if source_records is None:
        source_records = records
    return tuple(
        validate_annual_fiscal_year(
            record,
            requested_fiscal_year,
            fiscal_year_end_date=fiscal_year_end_date,
        )
        for record in source_records
    )


validate_fiscal_year = validate_annual_fiscal_year
validate_fiscal_years = validate_annual_fiscal_years
