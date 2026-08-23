"""Shared provenance representation and validation for extracted values."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple


class ProvenanceStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE_NEEDS_VALIDATION = "INCOMPLETE / NEEDS VALIDATION"


@dataclass(frozen=True)
class ExtractionLocation:
    filing_section_or_note: Optional[str] = None
    balance_sheet_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    source_evidence: Optional[str] = None


@dataclass(frozen=True)
class ExtractedValueProvenance:
    metric_name: Optional[str]
    raw_value: Any
    raw_unit: Optional[str]
    fiscal_year: Optional[int]
    filing_form: Optional[str]
    filing_date: Optional[str]
    accession_number: Optional[str]
    source_url: Optional[str]
    xbrl_concept: Optional[str]
    extraction_location: ExtractionLocation
    extraction_status: Optional[str]
    provenance_status: ProvenanceStatus
    missing_required_fields: Tuple[str, ...] = ()


_POINT_IN_TIME_METRICS = frozenset(
    {
        "Accounts Receivable", "Inventory", "Accounts Payable",
        "Shares Outstanding", "Deferred Tax Assets", "Deferred Tax Liabilities",
    }
)
_DURATION_METRICS = frozenset(
    {
        "Revenue", "Net Income", "Operating Cash Flow",
        "Depreciation & Amortization", "Capital Expenditures",
        "Stock-Based Compensation", "Income Tax Expense",
    }
)


def _value(source: Any, *names: str) -> Any:
    for name in names:
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _status_text(status: Any) -> Optional[str]:
    if status is None:
        return None
    value = getattr(status, "value", status)
    return str(value) if value is not None else None


def provenance_for(extracted_value: Any) -> ExtractedValueProvenance:
    """Create and validate provenance without changing the extracted value."""

    metric_name = _value(extracted_value, "metric_name", "financial_field")
    if metric_name is None and hasattr(extracted_value, "candidate_name"):
        metric_name = "Potential One-Off: " + str(extracted_value.candidate_name)
    raw_value = _value(extracted_value, "raw_sec_value", "raw_value", "raw_amount")
    raw_unit = _value(extracted_value, "raw_unit", "unit")
    status = _status_text(_value(extracted_value, "status"))
    location = ExtractionLocation(
        filing_section_or_note=_value(extracted_value, "filing_section_or_note"),
        balance_sheet_date=_value(extracted_value, "balance_sheet_date"),
        period_start=_value(extracted_value, "period_start"),
        period_end=_value(extracted_value, "period_end"),
        source_evidence=_value(extracted_value, "source_evidence"),
    )
    fields = {
        "metric_name": metric_name,
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "fiscal_year": _value(extracted_value, "fiscal_year"),
        "filing_form": _value(extracted_value, "filing_form"),
        "filing_date": _value(extracted_value, "filing_date"),
        "accession_number": _value(extracted_value, "accession_number"),
        "source_url": _value(extracted_value, "source_url"),
        "xbrl_concept": _value(extracted_value, "xbrl_concept"),
        "extraction_status": status,
    }
    missing = []
    if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
        for name in (
            "metric_name", "raw_unit", "fiscal_year", "filing_form", "filing_date",
            "accession_number", "source_url", "extraction_status",
        ):
            if fields[name] is None or fields[name] == "":
                missing.append(name)
        # Dedicated financial extractors are XBRL-based. Text candidates may
        # legitimately have no concept, so evidence/location remains auditable.
        if hasattr(extracted_value, "xbrl_taxonomy") and not fields["xbrl_concept"]:
            missing.append("xbrl_concept")
        if metric_name in _POINT_IN_TIME_METRICS and not location.balance_sheet_date:
            missing.append("balance_sheet_date")
        if metric_name in _DURATION_METRICS:
            if not location.period_start:
                missing.append("period_start")
            if not location.period_end:
                missing.append("period_end")

    provenance_status = (
        ProvenanceStatus.INCOMPLETE_NEEDS_VALIDATION
        if missing else ProvenanceStatus.COMPLETE
    )
    return ExtractedValueProvenance(
        metric_name=metric_name,
        raw_value=raw_value,
        raw_unit=raw_unit,
        fiscal_year=fields["fiscal_year"],
        filing_form=fields["filing_form"],
        filing_date=fields["filing_date"],
        accession_number=fields["accession_number"],
        source_url=fields["source_url"],
        xbrl_concept=fields["xbrl_concept"],
        extraction_location=location,
        extraction_status=status,
        provenance_status=provenance_status,
        missing_required_fields=tuple(missing),
    )


def validate_provenance(extracted_value: Any) -> ExtractedValueProvenance:
    """Validate and return the standardized provenance record."""

    return provenance_for(extracted_value)


class ProvenanceMixin:
    @property
    def provenance(self) -> ExtractedValueProvenance:
        return provenance_for(self)
