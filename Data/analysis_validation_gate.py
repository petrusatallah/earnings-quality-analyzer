"""Final annual validation gate composed from Tasks 83 through 88 results.

This module does not reproduce validator logic.  It consumes their structured
outputs, records exact blockers, and optionally guards an analysis callable.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional, Tuple

from Data.duplicate_value_validator import DuplicateClassification
from Data.duplicate_value_validator import validate_annual_duplicates
from Data.financial_statement_fetcher import FactStatus
from Data.fiscal_year_validator import validate_annual_fiscal_year
from Data.label_mapper import LabelMappingStatus, map_annual_labels
from Data.manual_corrections import ManualCorrection
from Data.missing_data_validator import (
    REQUIRED_ANNUAL_CORE_METRICS,
    ValidationStatus,
    validate_annual_missing_data,
)
from Data.unit_validator import validate_annual_units


class AnalysisDecision(str, Enum):
    CONTINUE = "CONTINUE"
    STOP = "STOP"


@dataclass(frozen=True)
class BlockingIssue:
    metric: str
    fiscal_year: int
    validation_source: str
    blocking_status: str
    explanation: str
    manual_correction_used: bool
    effective_value: Any = None


@dataclass(frozen=True)
class MetricYearGateResult:
    metric: str
    fiscal_year: int
    manual_correction_used: bool
    effective_value: Any
    blocking_issues: Tuple[BlockingIssue, ...]


@dataclass(frozen=True)
class AnalysisValidationGateResult:
    decision: AnalysisDecision
    can_analyze: bool
    requested_fiscal_years: Tuple[int, ...]
    blocking_issues: Tuple[BlockingIssue, ...]
    metric_year_results: Tuple[MetricYearGateResult, ...]
    blocking_issue_count: int

    @property
    def manual_corrections_used(self) -> Tuple[MetricYearGateResult, ...]:
        return tuple(item for item in self.metric_year_results if item.manual_correction_used)


_STANDARD_NAMES = {
    "Revenue": "Revenue", "Net Income": "Net Income",
    "OCF": "Operating Cash Flow", "Operating Cash Flow": "Operating Cash Flow",
    "AR": "Accounts Receivable", "Accounts Receivable": "Accounts Receivable",
    "Inventory": "Inventory", "AP": "Accounts Payable",
    "Accounts Payable": "Accounts Payable", "D&A": "Depreciation & Amortization",
    "Depreciation & Amortization": "Depreciation & Amortization",
    "CapEx": "Capital Expenditures", "Capital Expenditures": "Capital Expenditures",
    "SBC": "Stock-Based Compensation", "Stock-Based Compensation": "Stock-Based Compensation",
    "Shares Outstanding": "Shares Outstanding", "Income Tax Expense": "Income Tax Expense",
    "Tax Expense": "Income Tax Expense",
    "DTA": "Deferred Tax Assets", "Deferred Tax Assets": "Deferred Tax Assets",
    "DTL": "Deferred Tax Liabilities", "Deferred Tax Liabilities": "Deferred Tax Liabilities",
}
STANDARD_CORE_METRICS = tuple(_STANDARD_NAMES[name] for name in REQUIRED_ANNUAL_CORE_METRICS)


def _attribute(item: Any, *names: str) -> Any:
    if isinstance(item, Mapping):
        for name in names:
            if name in item:
                return item[name]
    else:
        for name in names:
            if hasattr(item, name):
                return getattr(item, name)
    return None


def _metric(item: Any) -> Optional[str]:
    value = _attribute(item, "metric", "standardized_metric", "metric_name", "financial_field")
    return _STANDARD_NAMES.get(value)


def _year(item: Any) -> Optional[int]:
    value = _attribute(item, "fiscal_year", "requested_fiscal_year", "Fiscal Year")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().upper().replace("_", " ")


def _index(results: Any) -> dict[tuple[str, int], Any]:
    if results is None:
        return {}
    source = _attribute(results, "statuses")
    if source is None:
        source = results
    indexed = {}
    for item in source:
        metric, year = _metric(item), _year(item)
        if metric is not None and year is not None:
            indexed[(metric, year)] = item
    return indexed


def _correction_index(corrections: Iterable[ManualCorrection]) -> dict[tuple[str, int], ManualCorrection]:
    indexed = {}
    for correction in corrections:
        if not isinstance(correction, ManualCorrection):
            continue
        key = (_STANDARD_NAMES.get(correction.metric, correction.metric), correction.fiscal_year)
        # Only a fully auditable active correction is eligible. Reverted entries
        # remain audit history but do not affect the effective value.
        if (
            correction.is_active
            and correction.correction_reason.strip()
            and correction.original_record is not None
        ):
            indexed[key] = correction
    return indexed


def _issue(
    metric: str,
    year: int,
    source: str,
    status: Any,
    explanation: str,
    correction: Optional[ManualCorrection],
    value: Any,
) -> BlockingIssue:
    return BlockingIssue(
        metric, year, source, _text(status), explanation,
        correction is not None, value,
    )


def evaluate_analysis_validation_gate(
    *,
    requested_fiscal_years: Iterable[int],
    missing_data_result: Any,
    unit_results: Iterable[Any],
    duplicate_results: Iterable[Any],
    fiscal_year_results: Iterable[Any],
    label_results: Iterable[Any],
    corrections: Iterable[ManualCorrection] = (),
) -> AnalysisValidationGateResult:
    """Combine existing validator results into one annual analysis decision."""

    years = tuple(dict.fromkeys(int(year) for year in requested_fiscal_years))
    indexes = {
        "Task 83 missing-data validation": _index(missing_data_result),
        "Task 84 unit validation": _index(unit_results),
        "Task 85 duplicate validation": _index(duplicate_results),
        "Task 86 fiscal-year validation": _index(fiscal_year_results),
        "Task 87 label mapping": _index(label_results),
    }
    correction_by_key = _correction_index(corrections)
    evaluations = []

    for year in years:
        for metric in STANDARD_CORE_METRICS:
            key = (metric, year)
            correction = correction_by_key.get(key)
            value = correction.effective_value if correction is not None else None
            issues = []

            missing = indexes["Task 83 missing-data validation"].get(key)
            missing_status = _text(_attribute(missing, "status", "validation_status"))
            if missing is None:
                issues.append(_issue(metric, year, "Task 83 missing-data validation",
                    "MISSING RESULT", "No missing-data validation result exists for this required item.", correction, value))
            elif missing_status != ValidationStatus.PRESENT.value:
                if correction is None:
                    issues.append(_issue(metric, year, "Task 83 missing-data validation",
                        _attribute(missing, "status", "validation_status"),
                        "Required value is missing or not usable and has no active manual correction.", correction, value))

            # An absent required record is fully represented by Task 83. Avoid
            # manufacturing four downstream MISSING RESULT blockers for a fact
            # those validators could not receive. An active correction still
            # requires all unrelated evidence, so it does not take this path.
            if missing_status == ValidationStatus.MISSING.value and correction is None:
                evaluations.append(MetricYearGateResult(
                    metric, year, False, None, tuple(issues)
                ))
                continue

            unit = indexes["Task 84 unit validation"].get(key)
            if unit is None:
                issues.append(_issue(metric, year, "Task 84 unit validation", "MISSING RESULT",
                    "No raw-unit validation result exists for this required item.", correction, value))
            else:
                unit_status = _text(_attribute(unit, "validation_status", "status"))
                unit_reason = str(_attribute(unit, "reason", "explanation") or "Raw unit is unresolved.")
                correction_preserves_valid_unit = (
                    correction is not None
                    and _attribute(unit, "unit_is_valid") is True
                )
                if (
                    unit_status != FactStatus.RETRIEVED.value
                    and not correction_preserves_valid_unit
                ):
                    issues.append(_issue(metric, year, "Task 84 unit validation", unit_status,
                        unit_reason, correction, value))

            duplicate = indexes["Task 85 duplicate validation"].get(key)
            if duplicate is None:
                issues.append(_issue(metric, year, "Task 85 duplicate validation", "MISSING RESULT",
                    "No duplicate validation result exists for this required item.", correction, value))
            else:
                classification = _text(_attribute(duplicate, "duplicate_classification", "classification"))
                duplicate_status = _text(_attribute(duplicate, "validation_status", "status"))
                if classification == DuplicateClassification.CONFLICTING_DUPLICATE.value:
                    issues.append(_issue(metric, year, "Task 85 duplicate validation", classification,
                        str(_attribute(duplicate, "explanation") or "Conflicting duplicates remain unresolved."), correction, value))
                elif duplicate_status not in (FactStatus.RETRIEVED.value,):
                    if correction is None:
                        issues.append(_issue(metric, year, "Task 85 duplicate validation", duplicate_status,
                            str(_attribute(duplicate, "explanation") or "Duplicate validation is unresolved."), correction, value))

            fiscal = indexes["Task 86 fiscal-year validation"].get(key)
            if fiscal is None:
                issues.append(_issue(metric, year, "Task 86 fiscal-year validation", "MISSING RESULT",
                    "No fiscal-year validation result exists for this required item.", correction, value))
            else:
                fiscal_status = _text(
                    _attribute(fiscal, "validation_status", "status")
                )
                correction_preserves_valid_period = (
                    correction is not None
                    and _attribute(fiscal, "period_metadata_valid") is True
                )
                if (
                    fiscal_status != FactStatus.RETRIEVED.value
                    and not correction_preserves_valid_period
                ):
                    issues.append(_issue(metric, year, "Task 86 fiscal-year validation",
                        fiscal_status,
                        str(_attribute(fiscal, "explanation", "reason") or "Fiscal-year identity or period is unresolved."), correction, value))

            label = indexes["Task 87 label mapping"].get(key)
            if label is None:
                issues.append(_issue(metric, year, "Task 87 label mapping", "MISSING RESULT",
                    "No label-mapping result exists for this required item.", correction, value))
            else:
                mapping_status = _text(_attribute(label, "mapping_status"))
                label_status = _text(_attribute(label, "validation_status", "status"))
                if mapping_status != LabelMappingStatus.MAPPED.value:
                    issues.append(_issue(metric, year, "Task 87 label mapping", mapping_status,
                        str(_attribute(label, "explanation") or "Required label is unmapped or ambiguous."), correction, value))
                elif label_status != FactStatus.RETRIEVED.value and correction is None:
                    issues.append(_issue(metric, year, "Task 87 label mapping", label_status,
                        str(_attribute(label, "explanation") or "Mapped extraction remains unusable."), correction, value))

            evaluations.append(MetricYearGateResult(metric, year, correction is not None, value, tuple(issues)))

    blockers = tuple(issue for result in evaluations for issue in result.blocking_issues)
    can_analyze = not blockers
    return AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE if can_analyze else AnalysisDecision.STOP,
        can_analyze=can_analyze,
        requested_fiscal_years=years,
        blocking_issues=blockers,
        metric_year_results=tuple(evaluations),
        blocking_issue_count=len(blockers),
    )


def run_analysis_if_valid(
    gate_result: AnalysisValidationGateResult,
    analysis_function: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Call an analysis function only after a CONTINUE gate decision."""

    if not gate_result.can_analyze or gate_result.decision is AnalysisDecision.STOP:
        return None
    return analysis_function(*args, **kwargs)


run_validation_gate = evaluate_analysis_validation_gate


def evaluate_integrated_annual_dataset(
    records: Iterable[Any],
    *,
    requested_fiscal_years: Iterable[int],
    fiscal_year_end_dates: Optional[Mapping[int, str]] = None,
    corrections: Iterable[ManualCorrection] = (),
) -> AnalysisValidationGateResult:
    """Run Tasks 83-87 and pass their real outputs into the Task 89 gate."""

    if hasattr(records, "to_dict"):
        source_records = tuple(records.to_dict("records"))
    else:
        source_records = tuple(records)
    years = tuple(dict.fromkeys(int(year) for year in requested_fiscal_years))
    year_ends = dict(fiscal_year_end_dates or {})

    label_results = map_annual_labels(source_records)
    core_records = tuple(
        record
        for record, label in zip(source_records, label_results)
        if label.mapping_status is LabelMappingStatus.MAPPED
        and label.standardized_metric in STANDARD_CORE_METRICS
    )
    missing_result = validate_annual_missing_data(core_records, years)
    unit_results = validate_annual_units(core_records)
    duplicate_results = validate_annual_duplicates(core_records)
    fiscal_results = tuple(
        validate_annual_fiscal_year(
            record,
            int(_attribute(record, "fiscal_year", "Fiscal Year")),
            fiscal_year_end_date=year_ends.get(
                int(_attribute(record, "fiscal_year", "Fiscal Year"))
            ),
        )
        for record in core_records
    )
    return evaluate_analysis_validation_gate(
        requested_fiscal_years=years,
        missing_data_result=missing_result,
        unit_results=unit_results,
        duplicate_results=duplicate_results,
        fiscal_year_results=fiscal_results,
        label_results=label_results,
        corrections=corrections,
    )


run_integrated_validation_gate = evaluate_integrated_annual_dataset


ANALYSIS_SESSION_KEYS = frozenset(
    {
        "analysis_results",
        "analysis_outputs",
        "cached_analysis_results",
        "latest_analysis_results",
    }
)


def clear_blocked_analysis_state(session_state: Any) -> Tuple[str, ...]:
    """Remove stale analysis outputs without touching validation/corrections/UI state."""

    removed = []
    for key in ANALYSIS_SESSION_KEYS:
        if key in session_state:
            del session_state[key]
            removed.append(key)
    return tuple(sorted(removed))
