"""Tests for Task 94 deferred-tax interpretation."""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.ai_input_preparation import build_ai_analysis_input  # noqa: E402
from Analysis.deferred_tax_interpretation import (  # noqa: E402
    interpret_deferred_taxes,
)
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def task_90_input(tax_row, financial_row=None):
    fiscal_year = tax_row.get("Fiscal Year", 2025)
    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(fiscal_year,),
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0,
    )
    empty = pd.DataFrame()
    financial = pd.DataFrame([financial_row]) if financial_row else empty
    return build_ai_analysis_input(
        company_name="Example Corp.",
        ticker="EXM",
        validation_gate=gate,
        financial_summary_df=financial,
        cash_conversion_df=empty,
        working_capital_df=empty,
        taxes_df=pd.DataFrame([tax_row]),
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )


def test_existing_tax_severity_and_explanation_are_preserved() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "DTA Risk Flag": True,
            "Deferred Tax Movement Flag": True,
            "Overall Tax Severity": "High",
            "Explanation": "Existing tax explanation.",
        }
    )

    result = interpret_deferred_taxes(structured)

    assert result["existing_severities"] == [
        {"fiscal_year": 2025, "severity": "High"}
    ]
    assert result["yearly_assessments"][0]["source_explanation"] == (
        "Existing tax explanation."
    )


def test_positive_existing_flags_are_interpreted_as_positive_signals() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2024,
            "DTA Risk Flag": False,
            "Deferred Tax Movement Flag": False,
            "Overall Tax Severity": "None",
            "Explanation": "Existing tax rules did not trigger.",
        }
    )

    result = interpret_deferred_taxes(structured)

    assert result["concerns"] == []
    assert len(result["positive_signals"]) == 2
    assert "do not trigger" in result["overall_assessment"]


def test_negative_existing_flags_are_interpreted_as_concerns() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "DTA Risk Flag": True,
            "Deferred Tax Movement Flag": True,
            "Overall Tax Severity": "High",
            "Explanation": "Existing tax results require review.",
        }
    )

    result = interpret_deferred_taxes(structured)

    assert len(result["concerns"]) == 2
    assert "items for review" in result["overall_assessment"]
    assert not any(
        "buy" in item.lower() or "sell" in item.lower()
        for item in result["concerns"]
    )


def test_missing_evidence_is_marked_unavailable_and_not_invented() -> None:
    structured = task_90_input({"Fiscal Year": 2025})

    result = interpret_deferred_taxes(structured)
    year = result["yearly_assessments"][0]

    assert year["assessment"].startswith("Deferred-tax assessment is unavailable")
    assert year["supporting_evidence"]["tax_expense"] is None
    assert year["supporting_evidence"]["dta_growth"] is None
    assert "dta_risk_flag" in year["unavailable_evidence"]
    assert "overall_tax_severity" in year["unavailable_evidence"]
    assert result["existing_severities"][0]["severity"] is None
    assert "not estimated" in result["explanation"]


def test_supplied_flags_control_interpretation_without_recalculation() -> None:
    # Deliberately contradictory balances and growth values prove that Task 94
    # follows existing flags rather than applying a tax threshold or formula.
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Deferred Tax Assets": 1,
            "Deferred Tax Liabilities": 1_000_000,
            "DTA / Net Income": 0.00001,
            "DTA Growth": -0.99,
            "DTL Growth": 8.5,
            "DTA Risk Flag": True,
            "Deferred Tax Movement Flag": False,
            "Overall Tax Severity": "Medium",
            "Explanation": "Use supplied flags.",
        },
        {"Fiscal Year": 2025, "Tax Expense": 500},
    )

    result = interpret_deferred_taxes(structured)
    evidence = result["yearly_assessments"][0]["supporting_evidence"]

    assert len(result["concerns"]) == 1
    assert evidence["dta_to_net_income"] == 0.00001
    assert evidence["dtl_growth"] == 8.5
    assert evidence["tax_expense"] == 500
    assert result["existing_severities"][0]["severity"] == "Medium"


def test_existing_project_tax_results_are_preserved() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.master_analysis_table import master_analysis_df
        from Analysis.tax_red_flags import tax_red_flags_df

    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(2022, 2023, 2024, 2025),
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0,
    )
    empty = pd.DataFrame()
    structured = build_ai_analysis_input(
        company_name="Apple Inc.",
        ticker="AAPL",
        validation_gate=gate,
        financial_summary_df=master_analysis_df,
        cash_conversion_df=empty,
        working_capital_df=empty,
        taxes_df=tax_red_flags_df,
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )

    result = interpret_deferred_taxes(structured)
    source = tax_red_flags_df.reset_index(drop=True)

    assert [item["severity"] for item in result["existing_severities"]] == source[
        "Overall Tax Severity"
    ].tolist()
    assert result["yearly_assessments"][0]["supporting_evidence"][
        "deferred_tax_assets"
    ] == source.iloc[0]["Deferred Tax Assets"]
    assert result["yearly_assessments"][0]["source_explanation"] == source.iloc[0][
        "Explanation"
    ]


def test_task_90_structure_is_required() -> None:
    try:
        interpret_deferred_taxes({"financial_summary": [], "taxes": []})
    except ValueError as error:
        assert "Task 90" in str(error)
    else:
        raise AssertionError("Incomplete Task 90 input must be rejected")


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Task 94 deferred-tax interpretation tests passed")

