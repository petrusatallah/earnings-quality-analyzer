"""Focused tests for the immutable reporting presentation contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from Analysis.reporting_view_model import (
    RULE_PRESENTATION_MAPPING,
    ReportingInputEnvelope,
    build_reporting_view_model,
)


class Decision(Enum):
    CONTINUE = "CONTINUE"


def _yearly_interpretation(
    key: str,
    years: tuple[int, ...],
    *,
    latest_severity: object = "None",
    latest_unavailable: tuple[str, ...] = (),
) -> dict[str, object]:
    assessments = []
    for year in years:
        unavailable = latest_unavailable if year == years[-1] else ()
        assessments.append(
            {
                "fiscal_year": year,
                "assessment": (
                    f"{key} assessment unavailable from finalized evidence."
                    if unavailable
                    else f"Approved {key} assessment for FY {year}."
                ),
                "existing_severity": (
                    "Unavailable"
                    if unavailable
                    else latest_severity
                    if year == years[-1]
                    else "None"
                ),
                "positive_signals": [f"Approved {key} positive {year}"],
                "concerns": [f"Approved {key} concern {year}"] if year == years[-1] else [],
                "supporting_evidence": {
                    "source_value": year * 10,
                    "source_label": f"{key}-{year}",
                },
                "source_explanation": f"Approved source explanation {key} {year}.",
                "unavailable_evidence": list(unavailable),
            }
        )
    return {
        "area": key,
        "overall_assessment": f"Approved overall {key} assessment.",
        "explanation": f"Approved {key} explanation.",
        "positive_signals": [f"Approved {key} positive"],
        "concerns": [f"Approved {key} concern"],
        "yearly_assessments": assessments,
    }


def _result(
    years: tuple[int, ...] = (2031, 2032, 2033, 2034, 2035),
    *,
    partial: bool = False,
    latest_triggers: str = "None",
    latest_unavailable: str = "None",
    mixed_sbc: bool = False,
    normalized_available: bool = True,
) -> SimpleNamespace:
    rows = []
    normalized_rows = []
    for index, year in enumerate(years):
        reported = 1_000 + index * 100
        normalized = reported + 25 if normalized_available else None
        rows.append(
            {
                "Fiscal Year": year,
                "Revenue": 10_000 + index * 500,
                "Net Income": reported,
                "Operating Cash Flow": 1_200 + index * 90,
                "Free Cash Flow": 900 + index * 80,
                "Normalized Net Income": normalized,
                "SBC / Net Income": 0.08 + index * 0.001,
                "Revenue Growth": None if index == 0 else 0.04 + index * 0.001,
                "AR Growth": None if index == 0 else 0.03 + index * 0.002,
                "Inventory Growth": None if index == 0 else 0.035 + index * 0.001,
                "Depreciation & Amortization": 400 + index * 10,
                "Capital Expenditures": 450 + index * 12,
                "Stock-Based Compensation": 80 + index * 3,
                "Shares Outstanding": 500 + index * 4,
                "Accrual Signal": "No accrual warning",
                "Accrual Severity": "None",
                "Working Capital Signal": "No working-capital warning",
                "Working Capital Severity": "None",
                "CapEx Investigation Result": "No investigation triggered",
                "Tax Signal": "No tax red flag",
                "Tax Severity": "None",
                "SBC Signal": (
                    "Unavailable" if mixed_sbc and year == years[-1] else "No SBC warning"
                ),
                "SBC Severity": (
                    "Unavailable" if mixed_sbc and year == years[-1] else "None"
                ),
                "Normalization Signal": (
                    "No normalization warning" if normalized_available else "Unavailable"
                ),
                "Normalization Severity": "None" if normalized_available else None,
                "Triggered Metrics": latest_triggers if year == years[-1] else "None",
                "Unavailable Metrics": latest_unavailable if year == years[-1] else "None",
            }
        )
        normalized_rows.append(
            {
                "Fiscal Year": year,
                "Reported Net Income": reported,
                "Normalized Net Income": normalized,
                "Normalization Signal": (
                    "No normalization warning" if normalized_available else "Unavailable"
                ),
                "Overall Severity": "None" if normalized_available else None,
                "Explanation": (
                    "Approved normalization result."
                    if normalized_available
                    else "Normalized-earnings evidence was not independently available."
                ),
            }
        )

    latest_year = years[-1]
    red_flags = pd.DataFrame(
        [
            {
                "Fiscal Year": latest_year,
                "Metric": "Earnings compared with cash",
                "Raw Data": "final raw evidence",
                "Calculation": "final calculation text",
                "Rule": "final approved rule",
                "Result": "Flag",
                "Severity": "Medium",
                "Explanation": "Approved triggered explanation.",
                "Missing Evidence": None,
            },
            {
                "Fiscal Year": latest_year,
                "Metric": "Share dilution",
                "Raw Data": "Unavailable",
                "Calculation": "Unavailable",
                "Rule": "final dilution rule",
                "Result": "Unavailable",
                "Severity": "Unavailable",
                "Explanation": "Unavailable because finalized share evidence is missing.",
                "Missing Evidence": "Shares Outstanding",
            },
            {
                "Fiscal Year": latest_year,
                "Metric": "CapEx vs D&A",
                "Raw Data": "final values",
                "Calculation": "final ratio",
                "Rule": "final capex rule",
                "Result": "No Flag",
                "Severity": "None",
                "Explanation": "Approved no-flag explanation.",
                "Missing Evidence": None,
            },
        ]
    )
    detailed = pd.DataFrame(
        [
            {
                "Fiscal Year": latest_year,
                "Metric": row["Metric"],
                "Final Severity": (
                    "Needs Investigation"
                    if row["Result"] == "Flag"
                    else "Unavailable"
                    if row["Result"] == "Unavailable"
                    else "Low Risk"
                ),
            }
            for row in red_flags.to_dict("records")
        ]
    )
    unavailable_rows = []
    if partial or latest_unavailable != "None" or mixed_sbc or not normalized_available:
        unavailable_rows.append(
            {
                "Analysis": "Reporting fixture",
                "Fiscal Year": latest_year,
                "Output": "Dependent output",
                "Status": "Unavailable",
                "Missing Metric": "Shares Outstanding" if mixed_sbc else "Evidence",
                "Missing Fiscal Year": latest_year,
                "Explanation": "Unavailable because finalized evidence is missing.",
            }
        )

    sbc_unavailable = ("dilution_flag",) if mixed_sbc else ()
    normalization_unavailable = ("normalized_net_income",) if not normalized_available else ()
    interpretations = {
        "accrual": _yearly_interpretation("accrual", years),
        "working_capital": _yearly_interpretation("working capital", years),
        "capex": _yearly_interpretation("capex", years),
        "deferred_taxes": _yearly_interpretation("deferred taxes", years),
        "sbc": _yearly_interpretation(
            "sbc", years, latest_unavailable=sbc_unavailable
        ),
        "normalized_earnings": _yearly_interpretation(
            "normalized earnings",
            years,
            latest_unavailable=normalization_unavailable,
        ),
    }
    interpretations["final_conclusion"] = {
        "earnings_quality_conclusion": "Needs Investigation",
        "explanation": "Approved final conclusion explanation.",
        **({"analysis_status": "Partial Analysis"} if partial else {}),
        "positive_signals": [{"area": "Cash", "signal": "Approved positive"}],
        "key_concerns": [{"area": "Accrual", "concern": "Approved concern"}],
        "areas_needing_investigation": [
            {"area": "Accrual", "concerns": ["Approved concern"]}
        ],
        "fiscal_years_covered": list(years),
    }

    calculations = {
        "financial_summary": pd.DataFrame(rows),
        "cash_conversion": pd.DataFrame(
            [{"Fiscal Year": year, "Explanation": "Approved accrual row."} for year in years]
        ),
        "normalized_earnings": pd.DataFrame(normalized_rows),
        "excel_support_tables": {
            "capex": pd.DataFrame(
                [{"Fiscal Year": year, "CapEx Review Result": "No investigation triggered"} for year in years]
            )
        },
    }
    analysis = {
        "working_capital": pd.DataFrame(
            [{"Fiscal Year": year, "Explanation": "Approved working-capital row."} for year in years]
        ),
        "taxes": pd.DataFrame(
            [{"Fiscal Year": year, "Explanation": "Approved tax row."} for year in years]
        ),
        "sbc": pd.DataFrame(
            [
                {
                    "Fiscal Year": year,
                    "Explanation": (
                        "Unavailable because finalized dilution evidence is missing."
                        if mixed_sbc and year == latest_year
                        else "Approved SBC row."
                    ),
                }
                for year in years
            ]
        ),
        "red_flags": red_flags,
        "detailed_severity": detailed,
        "overall_severity": pd.DataFrame(
            [{"Benchmark Severity": "Needs Investigation", "Availability": "Partial" if unavailable_rows else "Complete"}]
        ),
        "unavailable_outputs": pd.DataFrame(unavailable_rows),
    }
    return SimpleNamespace(
        company=SimpleNamespace(company_name="Northwind Media", ticker="NWM"),
        validation=SimpleNamespace(
            requested_fiscal_years=years,
            decision=Decision.CONTINUE,
            can_analyze=True,
        ),
        partial=partial,
        blocked=False,
        calculations=calculations,
        red_flags_and_severity=analysis,
        structured_ai_input=(
            {"partial_analysis": {"status": "Partial"}} if partial else {}
        ),
        interpretations=interpretations,
    )


def _series(chart, name):
    return next(item for item in chart.series if item.name == name)


def test_rule_presentation_mapping_uses_all_13_exact_approved_descriptions() -> None:
    expected = {
        "AR growth vs Revenue growth": (
            "Customer receivables vs revenue",
            "We review this when money owed by customers grows at least 10 percentage points faster than revenue. This may indicate that cash collection is not keeping pace with reported sales.",
        ),
        "Net Income growth vs OCF growth": (
            "Net income vs operating cash flow",
            "We flag this when net income increases but cash generated from normal business operations decreases. This means the improvement in reported profit is not being matched by operating cash flow.",
        ),
        "Inventory growth vs Revenue growth": (
            "Inventory vs revenue",
            "We review this when inventory grows at least 10 percentage points faster than revenue. This may indicate that products are accumulating faster than they are being sold.",
        ),
        "Accounts Payable pattern": (
            "Supplier payment pattern",
            "We flag possible payment pressure when amounts owed to suppliers grow at least 10 percentage points faster than revenue while operating cash flow is falling. This may indicate that the company is taking longer to pay suppliers while generating less operating cash.\n\nWe also review supplier financing when amounts owed to suppliers grow faster than revenue while operating cash flow remains positive. This may indicate that the company is relying more heavily on supplier credit to support its operations.",
        ),
        "Selected-account working-capital proxy": (
            "Selected-account working-capital proxy",
            "This estimate shows whether changes in customer receivables, inventory, and supplier payables may have absorbed or released cash. It uses selected balance-sheet accounts and is not the working-capital amount reported in the cash-flow statement.",
        ),
        "CapEx vs D&A": (
            "Investment spending vs depreciation and amortization",
            "We review this when spending on long-term assets is at least 1.2 times depreciation and amortization expense. This may indicate unusually heavy investment, but it is not automatically a negative sign.",
        ),
        "Deferred tax movement": (
            "Deferred-tax balance movement",
            "We review this when deferred-tax assets or deferred-tax liabilities change by at least 25% in one year. A large movement may reflect important tax assumptions, transactions, or timing differences that require explanation.",
        ),
        "Deferred Tax Asset risk": (
            "Deferred-tax asset usability",
            "We flag this when deferred-tax assets are at least 50% of net income and the company has no profit or net income has fallen by at least 10%. This raises a question about whether future taxable profits will be sufficient to use those tax benefits.",
        ),
        "Large SBC": (
            "Stock-based compensation level",
            "We review this when stock-based compensation is at least 10% of net income. Although it may not require an immediate cash payment, it is a real employee-compensation cost and may affect shareholders.",
        ),
        "SBC dilution": (
            "Shareholder dilution",
            "We flag this when shares outstanding increase by at least 1% in one year. An increasing share count means each existing shareholder owns a smaller percentage of the company.",
        ),
        "Buyback offset": (
            "Buybacks used to offset dilution",
            "This check shows whether the company is spending cash on share repurchases to offset shares issued through employee compensation. Buybacks may reduce dilution, but they do not remove the economic cost of stock-based compensation.",
        ),
        "Large normalization difference": (
            "Reported earnings vs normalized earnings",
            "We review this when normalized earnings differ from reported earnings by at least 10%. A large difference means unusual items had a meaningful effect on reported profit.",
        ),
        "Repeated one-off items": (
            "Repeated unusual items",
            "We review this when the same type of supposedly unusual item appears in at least two fiscal years. Repetition may indicate that the item is becoming part of normal business performance.",
        ),
    }

    assert len(RULE_PRESENTATION_MAPPING) == 13
    assert {
        key: (value.display_name, value.plain_english_explanation)
        for key, value in RULE_PRESENTATION_MAPPING.items()
    } == expected


def _assert_unchanged(actual, expected) -> None:
    if isinstance(expected, pd.DataFrame):
        pd.testing.assert_frame_equal(actual, expected)
    elif isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            _assert_unchanged(actual[key], expected[key])
    else:
        assert actual == expected


def test_complete_result_builds_the_full_frozen_contract() -> None:
    result = _result()
    view = build_reporting_view_model(result)

    assert (view.company, view.ticker) == ("Northwind Media", "NWM")
    assert view.fiscal_years == (2031, 2032, 2033, 2034, 2035)
    assert view.latest_fiscal_year == 2035
    assert view.status.validation_decision == "CONTINUE"
    assert view.status.is_partial is False
    assert view.existing_overall_severity == "Needs Investigation"
    assert view.final_conclusion.label == "Needs Investigation"
    assert view.latest_year_kpis.revenue == 12_000
    assert view.latest_year_kpis.operating_cash_flow == 1_560
    assert view.latest_year_kpis.sbc_net_income == pytest.approx(0.084)
    assert view.primary_drivers.state == "complete_no_triggers"
    assert view.primary_drivers.display_text == "No triggered drivers"
    assert tuple(area.key for area in view.analysis_areas) == (
        "accrual_and_cash",
        "working_capital",
        "da_and_capex",
        "deferred_taxes",
        "sbc_and_dilution",
        "normalized_earnings",
    )
    accrual = view.area("accrual_and_cash")
    assert accrual.approved_explanation == "Approved accrual explanation."
    assert accrual.concerns == ("Approved accrual concern",)
    assert accrual.positive_signals == ("Approved accrual positive",)
    assert accrual.yearly_assessments[-1].supporting_evidence["source_value"] == 20350
    assert accrual.supporting_evidence[-1].fiscal_year == 2035
    assert accrual.source_columns == ("Fiscal Year", "Explanation")
    assert accrual.finalized_rows[-1]["Fiscal Year"] == 2035
    assert accrual.finalized_rows[-1]["Explanation"] == "Approved accrual row."
    with pytest.raises(TypeError):
        accrual.finalized_rows[-1]["Explanation"] = "Changed"


def test_partial_result_preserves_validation_and_unavailable_evidence() -> None:
    result = _result(partial=True, latest_unavailable="Inventory growth")
    view = build_reporting_view_model(result)

    assert view.status.is_partial is True
    assert view.status.analysis_status == "Partial Analysis"
    assert len(view.status.unavailable_evidence) == 1
    evidence = view.status.unavailable_evidence[0]
    assert evidence.status == "Unavailable"
    assert evidence.missing_fiscal_year == 2035
    assert evidence.explanation == "Unavailable because finalized evidence is missing."


def test_no_triggers_with_unavailable_evidence_is_not_a_clean_driver_state() -> None:
    view = build_reporting_view_model(
        _result(latest_triggers="None", latest_unavailable="Inventory growth; SBC dilution")
    )

    assert view.primary_drivers.state == "unavailable"
    assert view.primary_drivers.triggered_metrics == ()
    assert view.primary_drivers.unavailable_metrics == (
        "Inventory growth",
        "SBC dilution",
    )
    assert view.primary_drivers.display_text == "Unavailable — incomplete evidence"
    assert "No triggered drivers" not in view.primary_drivers.display_text


def test_partial_run_uses_finalized_unavailable_rules_when_summary_text_is_empty() -> None:
    view = build_reporting_view_model(
        _result(partial=True, latest_triggers="None", latest_unavailable="None")
    )

    assert view.primary_drivers.state == "unavailable"
    assert view.primary_drivers.triggered_metrics == ()
    assert view.primary_drivers.unavailable_metrics == ("Share dilution",)
    assert view.primary_drivers.display_text.startswith("Unavailable")
    assert "incomplete evidence" in view.primary_drivers.display_text
    assert "No triggered drivers" not in view.primary_drivers.display_text


def test_mixed_sbc_availability_preserves_ratio_and_marks_dilution_unavailable() -> None:
    view = build_reporting_view_model(_result(mixed_sbc=True))

    assert view.latest_year_kpis.sbc_net_income == pytest.approx(0.084)
    sbc = view.area("sbc_and_dilution")
    assert sbc.signal == "Unavailable"
    assert sbc.severity == "Unavailable"
    assert sbc.availability == "unavailable"
    assert sbc.yearly_assessments[-1].unavailable_evidence == ("dilution_flag",)
    assert sbc.supporting_evidence[-1].values["source_value"] == 20350
    assert sbc.unavailable_reasons


def test_unavailable_normalization_preserves_reported_series_only() -> None:
    result = _result(normalized_available=False)
    view = build_reporting_view_model(result)

    assert view.latest_year_kpis.normalized_net_income is None
    normalized_area = view.area("normalized_earnings")
    assert normalized_area.signal == "Unavailable"
    assert normalized_area.availability == "unavailable"
    assert normalized_area.yearly_assessments[-1].unavailable_evidence == (
        "normalized_net_income",
    )

    chart = view.chart("reported_vs_normalized_net_income")
    assert _series(chart, "Reported Net Income").values == (
        1_000,
        1_100,
        1_200,
        1_300,
        1_400,
    )
    normalized = _series(chart, "Normalized Net Income")
    assert normalized.values == (None, None, None, None, None)
    assert normalized.availability == "unavailable"
    assert chart.availability == "partial"


def test_triggered_flags_and_unavailable_rules_remain_separate() -> None:
    view = build_reporting_view_model(_result())

    assert [item.metric for item in view.triggered_red_flags] == [
        "Earnings compared with cash"
    ]
    assert [item.metric for item in view.unavailable_rules] == ["Share dilution"]
    assert view.triggered_red_flags[0].final_severity == "Needs Investigation"
    assert view.unavailable_rules[0].final_severity == "Unavailable"
    assert view.unavailable_rules[0].missing_evidence == "Shares Outstanding"
    assert all(item.result != "Unavailable" for item in view.triggered_red_flags)
    assert all(item.result == "Unavailable" for item in view.unavailable_rules)


def test_primary_drivers_are_deduplicated_finalized_triggered_metrics() -> None:
    view = build_reporting_view_model(
        _result(
            latest_triggers=(
                "Large SBC; Large SBC; Deferred tax movement; Large SBC"
            )
        )
    )

    assert view.primary_drivers.triggered_metrics == (
        "Large SBC",
        "Deferred tax movement",
    )
    assert view.primary_drivers.display_text == "Large SBC; Deferred tax movement"
    assert view.existing_overall_severity == "Needs Investigation"


def test_chart_values_exactly_match_finalized_source_tables() -> None:
    result = _result()
    view = build_reporting_view_model(result)
    summary = result.calculations["financial_summary"]
    normalized = result.calculations["normalized_earnings"]

    expected = {
        "net_income_vs_operating_cash_flow": (summary, ("Net Income", "Operating Cash Flow")),
        "revenue_growth_vs_ar_growth": (summary, ("Revenue Growth", "AR Growth")),
        "revenue_growth_vs_inventory_growth": (
            summary,
            ("Revenue Growth", "Inventory Growth"),
        ),
        "da_vs_capital_expenditures": (summary, ("Depreciation & Amortization", "Capital Expenditures")),
        "operating_cash_flow_vs_free_cash_flow": (
            summary,
            ("Operating Cash Flow", "Free Cash Flow"),
        ),
        "stock_based_compensation": (summary, ("Stock-Based Compensation",)),
        "shares_outstanding": (summary, ("Shares Outstanding",)),
        "reported_vs_normalized_net_income": (normalized, ("Reported Net Income", "Normalized Net Income")),
    }
    for chart_key, (source, columns) in expected.items():
        chart = view.chart(chart_key)
        assert chart.categories == view.fiscal_years
        indexed = source.set_index("Fiscal Year")
        for column in columns:
            actual_values = _series(chart, column).values
            expected_values = tuple(indexed.loc[year, column] for year in view.fiscal_years)
            for actual, expected_value in zip(actual_values, expected_values):
                if pd.isna(expected_value):
                    assert actual is None
                else:
                    assert actual == expected_value


@pytest.mark.parametrize("count", (4, 7, 10))
def test_chart_categories_follow_dynamic_requested_fiscal_year_range(count: int) -> None:
    years = tuple(range(2040, 2040 + count))
    view = build_reporting_view_model(_result(years))

    assert view.fiscal_years == years
    assert all(chart.categories == years for chart in view.charts)
    assert all(len(series.values) == count for chart in view.charts for series in chart.series)


def test_contract_is_deeply_immutable() -> None:
    view = build_reporting_view_model(_result())

    with pytest.raises(FrozenInstanceError):
        view.company = "Changed"
    with pytest.raises(FrozenInstanceError):
        view.latest_year_kpis.revenue = 0
    with pytest.raises(TypeError):
        view.area("accrual_and_cash").yearly_assessments[-1].supporting_evidence[
            "source_value"
        ] = 0
    assert isinstance(view.final_conclusion.positive_signals, tuple)
    assert isinstance(view.analysis_areas, tuple)
    assert isinstance(view.charts, tuple)


def test_input_envelope_is_frozen_and_preserves_exact_source_references() -> None:
    result = _result()
    corrected_data = pd.DataFrame({"Fiscal Year": result.validation.requested_fiscal_years})
    envelope = ReportingInputEnvelope(
        company=result.company,
        validation=result.validation,
        corrected_data=corrected_data,
        calculations=result.calculations,
        red_flags_and_severity=result.red_flags_and_severity,
        structured_ai_input=result.structured_ai_input,
        interpretations=result.interpretations,
    )

    assert envelope.company is result.company
    assert envelope.validation is result.validation
    assert envelope.corrected_data is corrected_data
    assert envelope.calculations is result.calculations
    assert envelope.red_flags_and_severity is result.red_flags_and_severity
    assert envelope.structured_ai_input is result.structured_ai_input
    assert envelope.interpretations is result.interpretations
    with pytest.raises(FrozenInstanceError):
        envelope.validation = object()


def test_source_result_is_unchanged_and_contract_has_no_company_or_year_dependency() -> None:
    result = _result(tuple(range(2042, 2052)), partial=True)
    calculations_before = {
        key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else deepcopy(value)
        for key, value in result.calculations.items()
    }
    analysis_before = {
        key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else deepcopy(value)
        for key, value in result.red_flags_and_severity.items()
    }
    interpretations_before = deepcopy(result.interpretations)

    view = build_reporting_view_model(result)

    for key, expected in calculations_before.items():
        _assert_unchanged(result.calculations[key], expected)
    for key, expected in analysis_before.items():
        _assert_unchanged(result.red_flags_and_severity[key], expected)
    assert result.interpretations == interpretations_before
    assert view.company == "Northwind Media"
    assert view.ticker == "NWM"
    assert view.fiscal_years == tuple(range(2042, 2052))

    implementation = Path("Analysis/reporting_view_model.py").read_text(encoding="utf-8")
    assert "AAPL" not in implementation
    assert "import main" not in implementation
    assert "from main" not in implementation
