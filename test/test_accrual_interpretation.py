"""Tests for Task 91 accrual-quality interpretation."""

import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.accrual_interpretation import interpret_accrual_quality  # noqa: E402
from Analysis.ai_input_preparation import build_ai_analysis_input  # noqa: E402
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def task_90_input(cash_row, financial_row=None, working_capital_row=None):
    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(cash_row.get("Fiscal Year", 2025),),
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0,
    )
    empty = pd.DataFrame()
    return build_ai_analysis_input(
        company_name="Example Corp.",
        ticker="EXM",
        validation_gate=gate,
        financial_summary_df=pd.DataFrame([financial_row or {}]),
        cash_conversion_df=pd.DataFrame([cash_row]),
        working_capital_df=pd.DataFrame([working_capital_row or {}]),
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )


def test_existing_accrual_severity_is_preserved() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "AR Flag": True,
            "NI OCF Flag": True,
            "Combined Accrual Flag": True,
            "Severity": "High",
        }
    )

    result = interpret_accrual_quality(structured)

    assert result["existing_severities"] == [
        {"fiscal_year": 2025, "severity": "High"}
    ]
    assert result["yearly_assessments"][0]["existing_severity"] == "High"


def test_positive_existing_flags_are_interpreted_as_positive_signals() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2024,
            "AR Flag": False,
            "NI OCF Flag": False,
            "Combined Accrual Flag": False,
            "Severity": "None",
        }
    )

    result = interpret_accrual_quality(structured)

    assert result["key_concerns"] == []
    assert len(result["key_positive_signals"]) == 3
    assert "do not trigger" in result["overall_assessment"]


def test_negative_existing_flags_are_interpreted_as_concerns() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "AR Flag": True,
            "NI OCF Flag": True,
            "Combined Accrual Flag": True,
            "Severity": "High",
        }
    )

    result = interpret_accrual_quality(structured)

    assert len(result["key_concerns"]) == 3
    assert "concerns" in result["overall_assessment"]
    assert not any("buy" in item.lower() or "sell" in item.lower() for item in result["key_concerns"])


def test_missing_evidence_is_reported_and_not_invented() -> None:
    structured = task_90_input({"Fiscal Year": 2025, "Severity": None})

    result = interpret_accrual_quality(structured)
    year = result["yearly_assessments"][0]

    assert year["assessment"].startswith("Accrual assessment is unavailable")
    assert year["evidence"]["ar_growth"] is None
    assert year["evidence"]["net_income"] is None
    assert "ar_flag" in year["unavailable_evidence"]
    assert result["existing_severities"][0]["severity"] is None
    assert "not estimated" in result["explanation"]


def test_supplied_flags_control_interpretation_without_core_recalculation() -> None:
    # Deliberately inconsistent numbers prove that Task 91 follows Task 90's
    # existing flags rather than recreating AR/revenue or NI/OCF formulas.
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Revenue Growth": 0.90,
            "AR Growth": 0.01,
            "AR Revenue Gap": -0.89,
            "AR Flag": True,
            "NI OCF Flag": False,
            "Combined Accrual Flag": False,
            "Severity": "Medium",
        },
        {"Fiscal Year": 2025, "Net Income": -10, "OCF": 100},
        {"Fiscal Year": 2025, "Net Working Capital Cash Effect": -25},
    )

    result = interpret_accrual_quality(structured)
    evidence = result["yearly_assessments"][0]["evidence"]

    assert any("AR-versus-revenue rule triggered" in item for item in result["key_concerns"])
    assert evidence["ar_revenue_gap"] == -0.89
    assert evidence["net_working_capital_cash_effect"] == -25
    assert result["existing_severities"][0]["severity"] == "Medium"


def test_task_90_structure_is_required() -> None:
    try:
        interpret_accrual_quality({"cash_conversion": []})
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
    print("Task 91 accrual interpretation tests passed")

