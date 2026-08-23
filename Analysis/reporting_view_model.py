"""Immutable presentation contract for one finalized pipeline result.

This module deliberately depends only on the shape of a completed result.  It
does not import the pipeline controller, rerun calculations, or reinterpret
financial evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class FrozenMapping(Mapping[str, Any]):
    """Small immutable mapping used for finalized nested evidence."""

    entries: tuple[tuple[str, Any], ...] = ()

    def __getitem__(self, key: str) -> Any:
        for candidate, value in self.entries:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.entries)

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True)
class ReportingInputEnvelope:
    """Direct, immutable references to one finalized production run."""

    company: Any
    validation: Any
    corrected_data: Any
    calculations: Any
    red_flags_and_severity: Any
    structured_ai_input: Any
    interpretations: Any


@dataclass(frozen=True)
class UnavailableEvidence:
    analysis: Any
    fiscal_year: Any
    output: Any
    status: Any
    missing_metric: Any
    missing_fiscal_year: Any
    explanation: Any


@dataclass(frozen=True)
class ReportingStatus:
    validation_decision: Any
    can_analyze: Any
    is_blocked: bool
    is_partial: bool
    analysis_status: str
    unavailable_evidence: tuple[UnavailableEvidence, ...]


@dataclass(frozen=True)
class LatestYearKpis:
    revenue: Any
    net_income: Any
    operating_cash_flow: Any
    free_cash_flow: Any
    normalized_net_income: Any
    sbc_net_income: Any


@dataclass(frozen=True)
class PrimaryDrivers:
    """Availability-aware latest-year driver selection."""

    state: str
    triggered_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]
    display_text: str


@dataclass(frozen=True)
class SupportingEvidence:
    fiscal_year: Any
    values: FrozenMapping


@dataclass(frozen=True)
class YearlyAssessment:
    fiscal_year: Any
    assessment: Any
    existing_severity: Any
    positive_signals: tuple[Any, ...]
    concerns: tuple[Any, ...]
    supporting_evidence: FrozenMapping
    source_explanation: Any
    unavailable_evidence: tuple[Any, ...]


@dataclass(frozen=True)
class AnalysisAreaSummary:
    key: str
    label: str
    availability: str
    signal: Any
    severity: Any
    approved_explanation: Any
    concerns: tuple[Any, ...]
    positive_signals: tuple[Any, ...]
    yearly_assessments: tuple[YearlyAssessment, ...]
    supporting_evidence: tuple[SupportingEvidence, ...]
    unavailable_reasons: tuple[str, ...]
    source_columns: tuple[str, ...]
    finalized_rows: tuple[FrozenMapping, ...]


@dataclass(frozen=True)
class RuleResult:
    fiscal_year: Any
    metric: Any
    result: Any
    severity: Any
    final_severity: Any
    explanation: Any
    rule: Any
    raw_data: Any
    calculation: Any
    missing_evidence: Any
    finalized_values: FrozenMapping


@dataclass(frozen=True)
class RulePresentation:
    """Approved investor-facing wording for one finalized technical rule."""

    display_name: str
    plain_english_explanation: str
    exact_technical_rule: str


RULE_PRESENTATION_MAPPING = MappingProxyType({
    "AR growth vs Revenue growth": RulePresentation(
        display_name="Customer receivables vs revenue",
        plain_english_explanation=(
            "We review this when money owed by customers grows at least 10 "
            "percentage points faster than revenue. This may indicate that cash "
            "collection is not keeping pace with reported sales."
        ),
        exact_technical_rule=(
            "AR Growth - Revenue Growth >= 10 percentage points"
        ),
    ),
    "Net Income growth vs OCF growth": RulePresentation(
        display_name="Net income vs operating cash flow",
        plain_english_explanation=(
            "We flag this when net income increases but cash generated from normal "
            "business operations decreases. This means the improvement in reported "
            "profit is not being matched by operating cash flow."
        ),
        exact_technical_rule=(
            "Net Income Growth > 0 AND Operating Cash Flow Growth < 0"
        ),
    ),
    "Inventory growth vs Revenue growth": RulePresentation(
        display_name="Inventory vs revenue",
        plain_english_explanation=(
            "We review this when inventory grows at least 10 percentage points "
            "faster than revenue. This may indicate that products are accumulating "
            "faster than they are being sold."
        ),
        exact_technical_rule=(
            "Inventory Growth - Revenue Growth >= 10 percentage points"
        ),
    ),
    "Accounts Payable pattern": RulePresentation(
        display_name="Supplier payment pattern",
        plain_english_explanation=(
            "We flag possible payment pressure when amounts owed to suppliers grow "
            "at least 10 percentage points faster than revenue while operating cash "
            "flow is falling. This may indicate that the company is taking longer "
            "to pay suppliers while generating less operating cash.\n\n"
            "We also review supplier financing when amounts owed to suppliers grow "
            "faster than revenue while operating cash flow remains positive. This "
            "may indicate that the company is relying more heavily on supplier "
            "credit to support its operations."
        ),
        exact_technical_rule=(
            "AP Growth - Revenue Growth >= 10 percentage points AND OCF Growth < 0\n"
            "AP Growth > Revenue Growth AND OCF Growth >= 0"
        ),
    ),
    "Selected-account working-capital proxy": RulePresentation(
        display_name="Selected-account working-capital proxy",
        plain_english_explanation=(
            "This estimate shows whether changes in customer receivables, inventory, "
            "and supplier payables may have absorbed or released cash. It uses "
            "selected balance-sheet accounts and is not the working-capital amount "
            "reported in the cash-flow statement."
        ),
        exact_technical_rule="-AR Change - Inventory Change + AP Change",
    ),
    "CapEx vs D&A": RulePresentation(
        display_name="Investment spending vs depreciation and amortization",
        plain_english_explanation=(
            "We review this when spending on long-term assets is at least 1.2 times "
            "depreciation and amortization expense. This may indicate unusually "
            "heavy investment, but it is not automatically a negative sign."
        ),
        exact_technical_rule="CapEx / D&A >= 1.20x",
    ),
    "Deferred tax movement": RulePresentation(
        display_name="Deferred-tax balance movement",
        plain_english_explanation=(
            "We review this when deferred-tax assets or deferred-tax liabilities "
            "change by at least 25% in one year. A large movement may reflect "
            "important tax assumptions, transactions, or timing differences that "
            "require explanation."
        ),
        exact_technical_rule=(
            "abs(DTA Growth) >= 25% OR abs(DTL Growth) >= 25%"
        ),
    ),
    "Deferred Tax Asset risk": RulePresentation(
        display_name="Deferred-tax asset usability",
        plain_english_explanation=(
            "We flag this when deferred-tax assets are at least 50% of net income "
            "and the company has no profit or net income has fallen by at least 10%. "
            "This raises a question about whether future taxable profits will be "
            "sufficient to use those tax benefits."
        ),
        exact_technical_rule=(
            "DTA / |Net Income| >= 50% AND (Net Income Growth <= -10% OR Net Income <= 0)"
        ),
    ),
    "Large SBC": RulePresentation(
        display_name="Stock-based compensation level",
        plain_english_explanation=(
            "We review this when stock-based compensation is at least 10% of net "
            "income. Although it may not require an immediate cash payment, it is a "
            "real employee-compensation cost and may affect shareholders."
        ),
        exact_technical_rule="SBC / |Net Income| >= 10%",
    ),
    "SBC dilution": RulePresentation(
        display_name="Shareholder dilution",
        plain_english_explanation=(
            "We flag this when shares outstanding increase by at least 1% in one "
            "year. An increasing share count means each existing shareholder owns a "
            "smaller percentage of the company."
        ),
        exact_technical_rule="Shares Outstanding Growth >= 1%",
    ),
    "Buyback offset": RulePresentation(
        display_name="Buybacks used to offset dilution",
        plain_english_explanation=(
            "This check shows whether the company is spending cash on share "
            "repurchases to offset shares issued through employee compensation. "
            "Buybacks may reduce dilution, but they do not remove the economic cost "
            "of stock-based compensation."
        ),
        exact_technical_rule=(
            "Shares Issued Net > 0 AND Shares Repurchased >= Shares Issued Net; "
            "Shares Issued Net > 0 AND Shares Repurchased < Shares Issued Net"
        ),
    ),
    "Large normalization difference": RulePresentation(
        display_name="Reported earnings vs normalized earnings",
        plain_english_explanation=(
            "We review this when normalized earnings differ from reported earnings "
            "by at least 10%. A large difference means unusual items had a meaningful "
            "effect on reported profit."
        ),
        exact_technical_rule=(
            "Absolute Normalization Difference Percentage >= 10%"
        ),
    ),
    "Repeated one-off items": RulePresentation(
        display_name="Repeated unusual items",
        plain_english_explanation=(
            "We review this when the same type of supposedly unusual item appears in "
            "at least two fiscal years. Repetition may indicate that the item is "
            "becoming part of normal business performance."
        ),
        exact_technical_rule="Years Appearing >= 2",
    ),
})


@dataclass(frozen=True)
class ChartSeries:
    name: str
    values: tuple[Any, ...]
    availability: str


@dataclass(frozen=True)
class ChartSpec:
    key: str
    title: str
    categories: tuple[int, ...]
    series: tuple[ChartSeries, ...]
    availability: str


@dataclass(frozen=True)
class FinalConclusion:
    label: Any
    explanation: Any
    analysis_status: Any
    positive_signals: tuple[Any, ...]
    concerns: tuple[Any, ...]
    areas_needing_investigation: tuple[Any, ...]
    fiscal_years_covered: tuple[Any, ...]
    finalized_values: FrozenMapping


@dataclass(frozen=True)
class ReportingViewModel:
    company: str
    ticker: str
    fiscal_years: tuple[int, ...]
    latest_fiscal_year: int
    status: ReportingStatus
    existing_overall_severity: Any
    final_conclusion: FinalConclusion
    latest_year_kpis: LatestYearKpis
    primary_drivers: PrimaryDrivers
    analysis_areas: tuple[AnalysisAreaSummary, ...]
    triggered_red_flags: tuple[RuleResult, ...]
    unavailable_rules: tuple[RuleResult, ...]
    charts: tuple[ChartSpec, ...]

    def area(self, key: str) -> AnalysisAreaSummary:
        """Return one named analysis area without exposing a mutable index."""

        for area in self.analysis_areas:
            if area.key == key:
                return area
        raise KeyError(key)

    def chart(self, key: str) -> ChartSpec:
        """Return one named chart without exposing a mutable index."""

        for chart in self.charts:
            if chart.key == key:
                return chart
        raise KeyError(key)


_AREA_SPECS = (
    ("accrual_and_cash", "Accrual and Cash", "accrual", "Accrual Signal", "Accrual Severity", "cash_conversion"),
    ("working_capital", "Working Capital", "working_capital", "Working Capital Signal", "Working Capital Severity", "working_capital"),
    ("da_and_capex", "D&A and CapEx", "capex", "CapEx Investigation Result", None, "capex"),
    ("deferred_taxes", "Deferred Taxes", "deferred_taxes", "Tax Signal", "Tax Severity", "taxes"),
    ("sbc_and_dilution", "SBC and Dilution", "sbc", "SBC Signal", "SBC Severity", "sbc"),
    ("normalized_earnings", "Normalized Earnings", "normalized_earnings", "Normalization Signal", "Normalization Severity", "normalized_earnings"),
)


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, bool):
        return result
    item = getattr(result, "item", None)
    if callable(item):
        try:
            return bool(item())
        except (TypeError, ValueError):
            return False
    return False


def _scalar(value: Any) -> Any:
    if _missing(value):
        return None
    if isinstance(value, Enum):
        return _scalar(value.value)
    item = getattr(value, "item", None)
    if callable(item) and not isinstance(value, (str, bytes)):
        try:
            return item()
        except (TypeError, ValueError):
            pass
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, FrozenMapping):
        return value
    if isinstance(value, Mapping):
        return FrozenMapping(
            tuple((str(key), _freeze(item)) for key, item in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return _scalar(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _frame(mapping: Mapping[str, Any], key: str) -> pd.DataFrame:
    value = mapping.get(key)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _latest_row(frame: pd.DataFrame, fiscal_year: int) -> Mapping[str, Any]:
    if frame.empty:
        return {}
    if "Fiscal Year" in frame.columns:
        matches = frame.loc[frame["Fiscal Year"].eq(fiscal_year)]
        if matches.empty:
            return {}
        return matches.iloc[-1].to_dict()
    return frame.iloc[-1].to_dict()


def _text_items(value: Any) -> tuple[str, ...]:
    if value is None or _missing(value):
        return ()
    if isinstance(value, str):
        if value.strip().casefold() in {"", "none", "n/a", "unavailable"}:
            return ()
        return tuple(dict.fromkeys(
            part.strip() for part in value.split(";") if part.strip()
        ))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(dict.fromkeys(
            str(_scalar(item)) for item in value if not _missing(item)
        ))
    return (str(_scalar(value)),)


def _tuple_field(mapping: Mapping[str, Any], *keys: str) -> tuple[Any, ...]:
    for key in keys:
        if key in mapping:
            value = mapping.get(key)
            if value is None:
                return ()
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return tuple(_freeze(item) for item in value)
            return (_freeze(value),)
    return ()


def _yearly_assessments(interpretation: Mapping[str, Any]) -> tuple[YearlyAssessment, ...]:
    output = []
    source = interpretation.get("yearly_assessments")
    if not isinstance(source, Sequence) or isinstance(source, (str, bytes)):
        return ()
    for value in source:
        if not isinstance(value, Mapping):
            continue
        evidence = value.get("supporting_evidence", value.get("evidence", {}))
        output.append(
            YearlyAssessment(
                fiscal_year=_scalar(value.get("fiscal_year")),
                assessment=_scalar(value.get("assessment")),
                existing_severity=_scalar(value.get("existing_severity")),
                positive_signals=_tuple_field(value, "positive_signals", "positives"),
                concerns=_tuple_field(value, "concerns"),
                supporting_evidence=_freeze(evidence) if isinstance(evidence, Mapping) else FrozenMapping(),
                source_explanation=_scalar(value.get("source_explanation")),
                unavailable_evidence=_tuple_field(value, "unavailable_evidence"),
            )
        )
    return tuple(output)


def _latest_assessment_severity(
    assessments: tuple[YearlyAssessment, ...], fiscal_year: int
) -> Any:
    for assessment in assessments:
        if assessment.fiscal_year == fiscal_year:
            return assessment.existing_severity
    return None


def _source_frame(
    calculations: Mapping[str, Any], analysis: Mapping[str, Any], source_key: str
) -> pd.DataFrame:
    if source_key in calculations:
        return _frame(calculations, source_key)
    if source_key in analysis:
        return _frame(analysis, source_key)
    if source_key == "capex":
        support = _mapping(calculations.get("excel_support_tables"))
        return _frame(support, "capex")
    return pd.DataFrame()


def _area_summary(
    *,
    spec: tuple[str, str, str, str, str | None, str],
    fiscal_year: int,
    latest_summary: Mapping[str, Any],
    calculations: Mapping[str, Any],
    analysis: Mapping[str, Any],
    interpretations: Mapping[str, Any],
) -> AnalysisAreaSummary:
    key, label, interpretation_key, signal_column, severity_column, source_key = spec
    interpretation = _mapping(interpretations.get(interpretation_key))
    assessments = _yearly_assessments(interpretation)
    signal = _scalar(latest_summary.get(signal_column))
    severity = (
        _scalar(latest_summary.get(severity_column))
        if severity_column is not None
        else _latest_assessment_severity(assessments, fiscal_year)
    )

    unavailable_assessments = tuple(
        assessment for assessment in assessments if assessment.unavailable_evidence
    )
    unavailable_reasons = []
    for assessment in unavailable_assessments:
        reason = assessment.assessment or assessment.source_explanation
        if reason is not None and str(reason) not in unavailable_reasons:
            unavailable_reasons.append(str(reason))

    source_frame = _source_frame(calculations, analysis, source_key)
    source_row = _latest_row(source_frame, fiscal_year)
    source_explanation = _scalar(source_row.get("Explanation"))
    if (
        str(signal).casefold() == "unavailable"
        and source_explanation is not None
        and str(source_explanation) not in unavailable_reasons
    ):
        unavailable_reasons.append(str(source_explanation))

    latest_unavailable = any(
        assessment.fiscal_year == fiscal_year and assessment.unavailable_evidence
        for assessment in assessments
    )
    latest_marked_unavailable = (
        str(signal).casefold() == "unavailable"
        or str(severity).casefold() == "unavailable"
        or latest_unavailable
    )
    availability = (
        "unavailable"
        if latest_marked_unavailable
        else "partial"
        if unavailable_assessments
        else "available"
    )
    supporting = tuple(
        SupportingEvidence(assessment.fiscal_year, assessment.supporting_evidence)
        for assessment in assessments
    )
    return AnalysisAreaSummary(
        key=key,
        label=label,
        availability=availability,
        signal=signal,
        severity=severity,
        approved_explanation=_scalar(
            interpretation.get("explanation", interpretation.get("overall_assessment"))
        ),
        concerns=_tuple_field(interpretation, "key_concerns", "concerns"),
        positive_signals=_tuple_field(
            interpretation, "key_positive_signals", "positive_signals"
        ),
        yearly_assessments=assessments,
        supporting_evidence=supporting,
        unavailable_reasons=tuple(unavailable_reasons),
        source_columns=tuple(str(column) for column in source_frame.columns),
        finalized_rows=tuple(
            _freeze(record) for record in source_frame.to_dict("records")
        ),
    )


def _unavailable_rows(analysis: Mapping[str, Any]) -> tuple[UnavailableEvidence, ...]:
    frame = _frame(analysis, "unavailable_outputs")
    rows = []
    for record in frame.to_dict("records"):
        rows.append(
            UnavailableEvidence(
                analysis=_scalar(record.get("Analysis")),
                fiscal_year=_scalar(record.get("Fiscal Year")),
                output=_scalar(record.get("Output")),
                status=_scalar(record.get("Status")),
                missing_metric=_scalar(record.get("Missing Metric")),
                missing_fiscal_year=_scalar(record.get("Missing Fiscal Year")),
                explanation=_scalar(record.get("Explanation")),
            )
        )
    return tuple(rows)


def _rule_results(analysis: Mapping[str, Any]) -> tuple[tuple[RuleResult, ...], tuple[RuleResult, ...]]:
    red_flags = _frame(analysis, "red_flags")
    detailed = _frame(analysis, "detailed_severity")
    final_lookup = {}
    if {"Fiscal Year", "Metric", "Final Severity"}.issubset(detailed.columns):
        for record in detailed.to_dict("records"):
            final_lookup[(record.get("Fiscal Year"), record.get("Metric"))] = record.get(
                "Final Severity"
            )
    triggered = []
    unavailable = []
    for record in red_flags.to_dict("records"):
        result = _scalar(record.get("Result"))
        item = RuleResult(
            fiscal_year=_scalar(record.get("Fiscal Year")),
            metric=_scalar(record.get("Metric")),
            result=result,
            severity=_scalar(record.get("Severity", record.get("Internal Severity"))),
            final_severity=_scalar(
                record.get(
                    "Final Severity",
                    final_lookup.get((record.get("Fiscal Year"), record.get("Metric"))),
                )
            ),
            explanation=_scalar(record.get("Explanation")),
            rule=_scalar(record.get("Rule")),
            raw_data=_scalar(record.get("Raw Data")),
            calculation=_scalar(record.get("Calculation")),
            missing_evidence=_scalar(record.get("Missing Evidence")),
            finalized_values=_freeze(record),
        )
        if result in {"Flag", "Review"}:
            triggered.append(item)
        elif result == "Unavailable":
            unavailable.append(item)
    return tuple(triggered), tuple(unavailable)


def _series_values(
    frame: pd.DataFrame, fiscal_years: tuple[int, ...], column: str
) -> tuple[Any, ...]:
    if frame.empty or "Fiscal Year" not in frame.columns or column not in frame.columns:
        return tuple(None for _ in fiscal_years)
    by_year = {
        int(record["Fiscal Year"]): _scalar(record.get(column))
        for record in frame.to_dict("records")
        if not _missing(record.get("Fiscal Year"))
    }
    return tuple(by_year.get(year) for year in fiscal_years)


def _chart(
    *,
    key: str,
    title: str,
    frame: pd.DataFrame,
    fiscal_years: tuple[int, ...],
    columns: Iterable[str],
) -> ChartSpec:
    series = []
    for column in columns:
        values = _series_values(frame, fiscal_years, column)
        series.append(
            ChartSeries(
                name=column,
                values=values,
                availability=(
                    "unavailable" if all(value is None for value in values) else "available"
                ),
            )
        )
    availability_values = {item.availability for item in series}
    availability = (
        "unavailable"
        if availability_values == {"unavailable"}
        else "partial"
        if "unavailable" in availability_values
        else "available"
    )
    return ChartSpec(key, title, fiscal_years, tuple(series), availability)


def _charts(
    calculations: Mapping[str, Any], fiscal_years: tuple[int, ...]
) -> tuple[ChartSpec, ...]:
    summary = _frame(calculations, "financial_summary")
    normalized = _frame(calculations, "normalized_earnings")
    return (
        _chart(
            key="net_income_vs_operating_cash_flow",
            title="Net Income vs Operating Cash Flow",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Net Income", "Operating Cash Flow"),
        ),
        _chart(
            key="revenue_growth_vs_ar_growth",
            title="Revenue Growth vs AR Growth",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Revenue Growth", "AR Growth"),
        ),
        _chart(
            key="revenue_growth_vs_inventory_growth",
            title="Revenue Growth vs Inventory Growth",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Revenue Growth", "Inventory Growth"),
        ),
        _chart(
            key="da_vs_capital_expenditures",
            title="D&A vs Capital Expenditures",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Depreciation & Amortization", "Capital Expenditures"),
        ),
        _chart(
            key="operating_cash_flow_vs_free_cash_flow",
            title="Operating Cash Flow vs Free Cash Flow",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Operating Cash Flow", "Free Cash Flow"),
        ),
        _chart(
            key="stock_based_compensation",
            title="Stock-Based Compensation Trend",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Stock-Based Compensation",),
        ),
        _chart(
            key="shares_outstanding",
            title="Shares Outstanding Trend",
            frame=summary,
            fiscal_years=fiscal_years,
            columns=("Shares Outstanding",),
        ),
        _chart(
            key="reported_vs_normalized_net_income",
            title="Reported vs Normalized Net Income",
            frame=normalized,
            fiscal_years=fiscal_years,
            columns=("Reported Net Income", "Normalized Net Income"),
        ),
    )


def _decision_value(validation: Any) -> Any:
    return _scalar(getattr(validation, "decision", None))


def build_reporting_view_model(result: Any) -> ReportingViewModel:
    """Build a frozen, calculation-free view of one finalized pipeline result."""

    company_identity = getattr(result, "company", None)
    company = str(
        getattr(company_identity, "company_name", getattr(company_identity, "name", ""))
    )
    ticker = str(getattr(company_identity, "ticker", ""))
    validation = getattr(result, "validation", None)
    requested_years = getattr(validation, "requested_fiscal_years", ())
    fiscal_years = tuple(sorted({int(year) for year in requested_years}))
    if not 4 <= len(fiscal_years) <= 10:
        raise ValueError("A finalized reporting result must contain 4 to 10 fiscal years")
    latest_year = fiscal_years[-1]

    calculations = _mapping(getattr(result, "calculations", None))
    analysis = _mapping(getattr(result, "red_flags_and_severity", None))
    structured = _mapping(getattr(result, "structured_ai_input", None))
    interpretations = _mapping(getattr(result, "interpretations", None))
    summary = _frame(calculations, "financial_summary")
    latest = _latest_row(summary, latest_year)

    unavailable = _unavailable_rows(analysis)
    partial_block = _mapping(structured.get("partial_analysis"))
    final_source = _mapping(interpretations.get("final_conclusion"))
    reported_partial = bool(getattr(result, "partial", False))
    is_partial = reported_partial or bool(partial_block) or bool(unavailable)
    analysis_status = _scalar(
        final_source.get("analysis_status", partial_block.get("status"))
    ) or ("Partial" if is_partial else "Complete")

    overall = _frame(analysis, "overall_severity")
    existing_severity = (
        _scalar(overall.iloc[0].get("Benchmark Severity"))
        if not overall.empty
        else None
    )
    final_conclusion = FinalConclusion(
        label=_scalar(final_source.get("earnings_quality_conclusion")),
        explanation=_scalar(final_source.get("explanation")),
        analysis_status=_scalar(final_source.get("analysis_status")),
        positive_signals=_tuple_field(final_source, "positive_signals"),
        concerns=_tuple_field(final_source, "key_concerns", "concerns"),
        areas_needing_investigation=_tuple_field(
            final_source, "areas_needing_investigation"
        ),
        fiscal_years_covered=_tuple_field(final_source, "fiscal_years_covered"),
        finalized_values=_freeze(final_source),
    )

    triggered_red_flags, unavailable_rules = _rule_results(analysis)
    triggered_metrics = _text_items(latest.get("Triggered Metrics"))
    unavailable_metrics = _text_items(latest.get("Unavailable Metrics"))
    if is_partial and not unavailable_metrics:
        latest_unavailable_rules = tuple(
            str(item.metric)
            for item in unavailable_rules
            if item.fiscal_year == latest_year and item.metric is not None
        )
        unavailable_metrics = tuple(dict.fromkeys(latest_unavailable_rules))
    if unavailable_metrics:
        driver_state = "partial" if triggered_metrics else "unavailable"
        driver_text = (
            "; ".join(triggered_metrics)
            if triggered_metrics
            else "Unavailable — incomplete evidence"
        )
    elif triggered_metrics:
        driver_state = "triggered"
        driver_text = "; ".join(triggered_metrics)
    else:
        driver_state = "complete_no_triggers"
        driver_text = "No triggered drivers"
    drivers = PrimaryDrivers(
        state=driver_state,
        triggered_metrics=triggered_metrics,
        unavailable_metrics=unavailable_metrics,
        display_text=driver_text,
    )

    areas = tuple(
        _area_summary(
            spec=spec,
            fiscal_year=latest_year,
            latest_summary=latest,
            calculations=calculations,
            analysis=analysis,
            interpretations=interpretations,
        )
        for spec in _AREA_SPECS
    )
    return ReportingViewModel(
        company=company,
        ticker=ticker,
        fiscal_years=fiscal_years,
        latest_fiscal_year=latest_year,
        status=ReportingStatus(
            validation_decision=_decision_value(validation),
            can_analyze=_scalar(getattr(validation, "can_analyze", None)),
            is_blocked=bool(getattr(result, "blocked", False)),
            is_partial=is_partial,
            analysis_status=str(analysis_status),
            unavailable_evidence=unavailable,
        ),
        existing_overall_severity=existing_severity,
        final_conclusion=final_conclusion,
        latest_year_kpis=LatestYearKpis(
            revenue=_scalar(latest.get("Revenue")),
            net_income=_scalar(latest.get("Net Income")),
            operating_cash_flow=_scalar(latest.get("Operating Cash Flow")),
            free_cash_flow=_scalar(latest.get("Free Cash Flow")),
            normalized_net_income=_scalar(latest.get("Normalized Net Income")),
            sbc_net_income=_scalar(latest.get("SBC / Net Income")),
        ),
        primary_drivers=drivers,
        analysis_areas=areas,
        triggered_red_flags=triggered_red_flags,
        unavailable_rules=unavailable_rules,
        charts=_charts(calculations, fiscal_years),
    )


__all__ = [
    "AnalysisAreaSummary",
    "ChartSeries",
    "ChartSpec",
    "FinalConclusion",
    "FrozenMapping",
    "LatestYearKpis",
    "PrimaryDrivers",
    "ReportingInputEnvelope",
    "ReportingStatus",
    "ReportingViewModel",
    "RULE_PRESENTATION_MAPPING",
    "RulePresentation",
    "RuleResult",
    "SupportingEvidence",
    "UnavailableEvidence",
    "YearlyAssessment",
    "build_reporting_view_model",
]
