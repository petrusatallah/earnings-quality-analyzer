"""Auditable manual corrections layered over extracted annual financial facts.

Corrections are immutable overlays.  Source records, raw SEC values, units, and
provenance are never mutated or replaced by this module.
"""

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any, Mapping, Optional, Tuple

from Data.financial_statement_fetcher import FactStatus


class CorrectionStatus(str, Enum):
    ACTIVE = "ACTIVE MANUAL CORRECTION"
    REVERTED = "REVERTED MANUAL CORRECTION"


@dataclass(frozen=True)
class OriginalProvenance:
    filing_form: Any = None
    filing_date: Any = None
    accession_number: Any = None
    source_identifier: Any = None
    source_url: Any = None
    xbrl_taxonomy: Any = None
    xbrl_concept: Any = None
    period_start: Any = None
    period_end: Any = None
    balance_sheet_date: Any = None


@dataclass(frozen=True)
class ManualCorrection:
    metric: str
    fiscal_year: int
    original_value: Any
    corrected_value: Any
    original_unit: Any
    correction_reason: str
    original_extraction_status: Any
    original_provenance: OriginalProvenance
    correction_status: CorrectionStatus
    original_record: Any

    @property
    def is_active(self) -> bool:
        return self.correction_status is CorrectionStatus.ACTIVE

    @property
    def effective_value(self) -> Any:
        return self.corrected_value if self.is_active else self.original_value


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


def _identity(record: Any) -> Tuple[str, int]:
    metric = _attribute(record, "metric_name", "financial_field", "metric", "Metric")
    year = _attribute(record, "fiscal_year", "Fiscal Year")
    if not isinstance(metric, str) or not metric.strip():
        raise ValueError("A manual correction requires an existing metric identity")
    if year is None:
        raise ValueError("A manual correction requires an existing fiscal year")
    return metric, int(year)


def _original_value(record: Any) -> Any:
    return _attribute(
        record, "raw_sec_value", "raw_value", "raw_amount", "value", "Value"
    )


def _original_unit(record: Any) -> Any:
    return _attribute(record, "raw_unit", "unit", "Raw Unit", "Units")


def _provenance(record: Any) -> OriginalProvenance:
    return OriginalProvenance(
        filing_form=_attribute(record, "filing_form", "Financial Statement"),
        filing_date=_attribute(record, "filing_date", "Source Date"),
        accession_number=_attribute(record, "accession_number"),
        source_identifier=_attribute(
            record, "sec_source_identifier", "source_identifier", "Source"
        ),
        source_url=_attribute(record, "source_url"),
        xbrl_taxonomy=_attribute(record, "xbrl_taxonomy"),
        xbrl_concept=_attribute(record, "xbrl_concept"),
        period_start=_attribute(record, "period_start"),
        period_end=_attribute(record, "period_end"),
        balance_sheet_date=_attribute(record, "balance_sheet_date"),
    )


def _status(record: Any) -> Any:
    status = _attribute(record, "status", "extraction_status")
    return status if status is not None else FactStatus.RETRIEVED


def create_manual_correction(
    record: Any,
    corrected_value: Any,
    correction_reason: str,
    *,
    corrected_unit: Any = None,
    metric: Optional[str] = None,
    fiscal_year: Optional[int] = None,
) -> ManualCorrection:
    """Create an active immutable correction overlay for one annual record."""

    original_metric, original_year = _identity(record)
    reason = correction_reason.strip() if isinstance(correction_reason, str) else ""
    if not reason:
        raise ValueError("A non-empty correction reason is required")
    if (
        not isinstance(corrected_value, (int, float))
        or isinstance(corrected_value, bool)
        or (isinstance(corrected_value, float) and not math.isfinite(corrected_value))
    ):
        raise ValueError("The corrected value must be a finite numeric value")
    if metric is not None and metric != original_metric:
        raise ValueError("A correction cannot change the metric identity")
    if fiscal_year is not None and int(fiscal_year) != original_year:
        raise ValueError("A correction cannot change the fiscal year")

    original_unit = _original_unit(record)
    if corrected_unit is not None and corrected_unit != original_unit:
        raise ValueError("A correction cannot change or invent the original unit")

    return ManualCorrection(
        metric=original_metric,
        fiscal_year=original_year,
        original_value=_original_value(record),
        corrected_value=corrected_value,
        original_unit=original_unit,
        correction_reason=reason,
        original_extraction_status=_status(record),
        original_provenance=_provenance(record),
        correction_status=CorrectionStatus.ACTIVE,
        original_record=record,
    )


def revert_manual_correction(correction: ManualCorrection) -> ManualCorrection:
    """Return a reverted audit record; the original correction remains immutable."""

    if not isinstance(correction, ManualCorrection):
        raise TypeError("correction must be a ManualCorrection")
    return replace(correction, correction_status=CorrectionStatus.REVERTED)


def effective_value(record: Any, correction: Optional[ManualCorrection] = None) -> Any:
    """Return an active correction value, or the untouched extracted value."""

    if correction is None:
        return _original_value(record)
    if not isinstance(correction, ManualCorrection):
        raise TypeError("correction must be a ManualCorrection or None")
    metric, year = _identity(record)
    if (metric, year) != (correction.metric, correction.fiscal_year):
        raise ValueError("The correction belongs to a different metric/fiscal year")
    if correction.original_record is not record and (
        _original_value(record) != correction.original_value
        or _original_unit(record) != correction.original_unit
    ):
        raise ValueError("The correction does not belong to this extracted record")
    return correction.effective_value


apply_manual_correction = create_manual_correction
revert_correction = revert_manual_correction
get_effective_value = effective_value
