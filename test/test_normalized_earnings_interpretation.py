"""Tests for Task 96 normalized-earnings interpretation."""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.ai_input_preparation import build_ai_analysis_input  # noqa: E402
from Analysis.normalized_earnings_interpretation import (  # noqa: E402
    interpret_normalized_earnings,
)
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def task_90_input(normalized_row):
    fiscal_year = normalized_row.get("Fiscal Year", 2025)
    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(fiscal_year,),
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0,
    )
    empty = pd.DataFrame()
    return build_ai_analysis_input(
        company_name="Example Corp.",
        ticker="EXM",
        validation_gate=gate,
        financial_summary_df=empty,
        cash_conversion_df=empty,
        working_capital_df=empty,
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=pd.DataFrame([normalized_row]),
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )


def test_existing_normalization_severity_and_explanation_are_preserved() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Large Normalization Difference Flag": True,
            "Repeated One-Off Flag": True,
            "Overall Severity": "High",
            "Explanation": "Existing normalization explanation.",
        }
    )

    result = interpret_normalized_earnings(structured)

    assert result["existing_severities"] == [
        {"fiscal_year": 2025, "severity": "High"}
    ]
    assert result["yearly_assessments"][0]["source_explanation"] == (
        "Existing normalization explanation."
    )


def test_one_off_classification_and_review_status_are_preserved() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "One-Off Category": "Restructuring",
            "One-Off Description": "Supplied item description",
            "Classification": "Recurring operating item",
            "Review Status": "Review required",
            "Large Normalization Difference Flag": False,
            "Repeated One-Off Flag": True,
            "Overall Severity": "Medium",
            "Explanation": "Existing classification requires review.",
        }
    )

    result = interpret_normalized_earnings(structured)
    year = result["yearly_assessments"][0]

    assert year["one_off_classification"] == "Recurring operating item"
    assert year["review_status"] == "Review required"
    assert year["supporting_evidence"]["one_off_description"] == (
        "Supplied item description"
    )
    assert any("Review required" in item for item in result["concerns"])


def test_positive_existing_flags_are_interpreted_as_positive_signals() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2024,
            "Large Normalization Difference Flag": False,
            "Repeated One-Off Flag": False,
            "Review Status": "No review required",
            "Overall Severity": "None",
            "Explanation": "Existing normalization rules did not trigger.",
        }
    )

    result = interpret_normalized_earnings(structured)

    assert result["concerns"] == []
    assert len(result["positive_signals"]) == 3
    assert "do not trigger" in result["overall_assessment"]


def test_negative_existing_flags_are_interpreted_as_concerns() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Large Normalization Difference Flag": True,
            "Repeated One-Off Flag": True,
            "Overall Severity": "High",
            "Explanation": "Existing normalization results require review.",
        }
    )

    result = interpret_normalized_earnings(structured)

    assert len(result["concerns"]) == 2
    assert "items for review" in result["overall_assessment"]
    assert not any(
        "buy" in item.lower() or "sell" in item.lower()
        for item in result["concerns"]
    )


def test_missing_evidence_is_marked_unavailable_and_not_invented() -> None:
    structured = task_90_input({"Fiscal Year": 2025})

    result = interpret_normalized_earnings(structured)
    year = result["yearly_assessments"][0]

    assert year["assessment"].startswith(
        "Normalized-earnings assessment is unavailable"
    )
    assert year["supporting_evidence"]["normalized_net_income"] is None
    assert year["supporting_evidence"]["normalization_adjustment"] is None
    assert "repeated_one_off_flag" in year["unavailable_evidence"]
    assert "severity" in year["unavailable_evidence"]
    assert result["existing_severities"][0]["severity"] is None
    assert "not estimated" in result["explanation"]


def test_supplied_flags_control_interpretation_without_core_calculations() -> None:
    # Contradictory amounts prove that no adjustment, difference, percentage,
    # repeated-item, or large-difference rule is recreated by Task 96.
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Reported Net Income": 100,
            "Normalization Adjustment": 0,
            "Normalized Net Income": 100,
            "Normalization Difference": 0,
            "Normalization Difference %": 0,
            "Large Normalization Difference Flag": True,
            "Repeated One-Off Flag": True,
            "Overall Severity": "High",
            "Explanation": "Use supplied outputs.",
        }
    )

    result = interpret_normalized_earnings(structured)
    evidence = result["yearly_assessments"][0]["supporting_evidence"]

    assert len(result["concerns"]) == 2
    assert evidence["normalization_difference"] == 0
    assert evidence["normalization_difference_percentage"] == 0
    assert result["existing_severities"][0]["severity"] == "High"


def test_existing_project_normalization_results_are_preserved() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.normalization_red_flags import normalization_red_flags_df

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
        financial_summary_df=empty,
        cash_conversion_df=empty,
        working_capital_df=empty,
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=normalization_red_flags_df,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )

    result = interpret_normalized_earnings(structured)
    source = normalization_red_flags_df.reset_index(drop=True)

    assert [item["severity"] for item in result["existing_severities"]] == source[
        "Overall Severity"
    ].tolist()
    assert result["yearly_assessments"][0]["supporting_evidence"][
        "normalization_difference"
    ] == source.iloc[0]["Difference"]
    assert result["yearly_assessments"][0]["supporting_evidence"][
        "one_off_category"
    ] == source.iloc[0]["One-Off Categories Identified"]
    assert result["yearly_assessments"][0]["source_explanation"] == source.iloc[0][
        "Explanation"
    ]


def test_task_90_structure_is_required() -> None:
    try:
        interpret_normalized_earnings({"normalized_earnings": []})
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
    print("Task 96 normalized-earnings interpretation tests passed")

