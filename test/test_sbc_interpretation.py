"""Tests for Task 95 stock-based-compensation interpretation."""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.ai_input_preparation import build_ai_analysis_input  # noqa: E402
from Analysis.sbc_interpretation import interpret_sbc  # noqa: E402
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def task_90_input(sbc_row):
    fiscal_year = sbc_row.get("Fiscal Year", 2025)
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
        sbc_df=pd.DataFrame([sbc_row]),
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )


def test_existing_sbc_severity_and_explanation_are_preserved() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Large SBC Flag": True,
            "Dilution Flag": True,
            "Buyback Offset Classification": "Buybacks partially offset share issuance",
            "Overall SBC Severity": "Medium",
            "Explanation": "Existing SBC explanation.",
        }
    )

    result = interpret_sbc(structured)

    assert result["existing_severities"] == [
        {"fiscal_year": 2025, "severity": "Medium"}
    ]
    assert result["yearly_assessments"][0]["source_explanation"] == (
        "Existing SBC explanation."
    )


def test_dilution_flag_is_interpreted_without_recalculation() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Large SBC Flag": False,
            "Dilution Flag": True,
            "Buyback Offset Classification": "No positive net share issuance to offset",
            "Overall SBC Severity": "Medium",
            "Explanation": "Existing dilution flag triggered.",
        }
    )

    result = interpret_sbc(structured)

    assert any("dilution flag triggered" in item for item in result["concerns"])
    assert any("no positive net share issuance" in item.lower() for item in result["positive_signals"])


def test_buybacks_more_than_offset_issuance_preserves_balanced_interpretation() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2024,
            "Large SBC Flag": False,
            "Dilution Flag": False,
            "Buyback Offset Classification": "Buybacks more than offset share issuance",
            "Overall SBC Severity": "Low",
            "Explanation": "Buybacks offset issuance but require company cash.",
        }
    )

    result = interpret_sbc(structured)

    assert any("more than offset" in item for item in result["positive_signals"])
    assert any("company cash" in item for item in result["concerns"])
    assert "both positive and concerning" in result["overall_assessment"]


def test_partial_buyback_offset_is_interpreted_as_concern() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Large SBC Flag": False,
            "Dilution Flag": False,
            "Buyback Offset Classification": "Buybacks partially offset share issuance",
            "Overall SBC Severity": "Low",
            "Explanation": "Existing classification requires review.",
        }
    )

    result = interpret_sbc(structured)

    assert any("partially offset" in item for item in result["concerns"])
    assert result["existing_severities"][0]["severity"] == "Low"


def test_missing_evidence_is_marked_unavailable_and_not_invented() -> None:
    structured = task_90_input({"Fiscal Year": 2025})

    result = interpret_sbc(structured)
    year = result["yearly_assessments"][0]

    assert year["assessment"].startswith("SBC assessment is unavailable")
    assert year["supporting_evidence"]["sbc"] is None
    assert year["supporting_evidence"]["buyback_offset_ratio"] is None
    assert "dilution_flag" in year["unavailable_evidence"]
    assert "overall_sbc_severity" in year["unavailable_evidence"]
    assert result["existing_severities"][0]["severity"] is None
    assert "not estimated" in result["explanation"]


def test_supplied_results_control_interpretation_without_core_calculations() -> None:
    # Values intentionally conflict with the supplied dilution and offset results.
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "SBC": 1,
            "SBC / Net Income": 0.00001,
            "Shares Outstanding": 1_000,
            "Shares Outstanding Growth": -0.75,
            "Dilution Flag": True,
            "Shares Repurchased": 10_000,
            "Shares Issued Net": 1,
            "Net Share Effect": -9_999,
            "Buyback Offset Ratio": 10_000,
            "Buyback Offset Classification": "Buybacks partially offset share issuance",
            "Overall SBC Severity": "High",
            "Explanation": "Use supplied outputs.",
        }
    )

    result = interpret_sbc(structured)
    evidence = result["yearly_assessments"][0]["supporting_evidence"]

    assert any("dilution flag triggered" in item for item in result["concerns"])
    assert any("partially offset" in item for item in result["concerns"])
    assert evidence["shares_outstanding_growth"] == -0.75
    assert evidence["buyback_offset_ratio"] == 10_000
    assert result["existing_severities"][0]["severity"] == "High"


def test_existing_project_sbc_results_are_preserved() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.sbc_red_flags import sbc_red_flags_df

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
        sbc_df=sbc_red_flags_df,
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )

    result = interpret_sbc(structured)
    source = sbc_red_flags_df.reset_index(drop=True)

    assert [item["severity"] for item in result["existing_severities"]] == source[
        "Overall SBC Severity"
    ].tolist()
    assert result["yearly_assessments"][0]["supporting_evidence"]["sbc"] == source.iloc[
        0
    ]["SBC"]
    assert result["yearly_assessments"][0]["supporting_evidence"][
        "buyback_offset_classification"
    ] == source.iloc[0]["Buyback Offset Classification"]
    assert result["yearly_assessments"][0]["source_explanation"] == source.iloc[0][
        "Explanation"
    ]


def test_task_90_structure_is_required() -> None:
    try:
        interpret_sbc({"sbc": []})
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
    print("Task 95 SBC interpretation tests passed")

