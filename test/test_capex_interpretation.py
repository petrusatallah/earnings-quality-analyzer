"""Tests for Task 93 CapEx interpretation."""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.ai_input_preparation import build_ai_analysis_input  # noqa: E402
from Analysis.capex_interpretation import interpret_capex  # noqa: E402
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def task_90_input(financial_row, red_flag_row):
    fiscal_year = financial_row.get(
        "Fiscal Year", red_flag_row.get("Fiscal Year", 2025)
    )
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
        financial_summary_df=pd.DataFrame([financial_row]),
        cash_conversion_df=empty,
        working_capital_df=empty,
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=pd.DataFrame([red_flag_row]),
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )


def test_existing_capex_severity_and_explanation_are_preserved() -> None:
    structured = task_90_input(
        {"Fiscal Year": 2025, "CapEx Investigation Result": "Needs investigation"},
        {
            "Fiscal Year": 2025,
            "Metric": "CapEx vs D&A",
            "Result": "Flag",
            "Severity": "Medium",
            "Explanation": "Existing CapEx explanation.",
        },
    )

    result = interpret_capex(structured)

    assert result["existing_severities"] == [
        {"fiscal_year": 2025, "severity": "Medium"}
    ]
    assert result["yearly_assessments"][0]["source_explanation"] == (
        "Existing CapEx explanation."
    )


def test_positive_existing_result_is_interpreted_as_positive_signal() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2024,
            "CapEx Investigation Result": "No investigation triggered",
        },
        {
            "Fiscal Year": 2024,
            "Metric": "CapEx vs D&A",
            "Result": "No Flag",
            "Severity": "None",
            "Explanation": "Existing rule did not trigger.",
        },
    )

    result = interpret_capex(structured)

    assert result["concerns"] == []
    assert len(result["positive_signals"]) == 1
    assert "do not trigger" in result["overall_assessment"]


def test_negative_existing_result_is_interpreted_as_concern() -> None:
    structured = task_90_input(
        {"Fiscal Year": 2025, "CapEx Review Flag": True},
        {
            "Fiscal Year": 2025,
            "Metric": "CapEx vs D&A",
            "Result": "Flag",
            "Severity": "Medium",
            "Explanation": "Existing rule requires investigation.",
        },
    )

    result = interpret_capex(structured)

    assert len(result["concerns"]) == 1
    assert "items for review" in result["overall_assessment"]
    assert "buy" not in result["concerns"][0].lower()
    assert "sell" not in result["concerns"][0].lower()


def test_missing_evidence_is_marked_unavailable_and_not_invented() -> None:
    structured = task_90_input(
        {"Fiscal Year": 2025},
        {"Fiscal Year": 2025, "Metric": "CapEx vs D&A"},
    )

    result = interpret_capex(structured)
    year = result["yearly_assessments"][0]

    assert year["assessment"].startswith("CapEx assessment is unavailable")
    assert year["supporting_evidence"]["capex"] is None
    assert year["supporting_evidence"]["capex_to_da"] is None
    assert "capex_flag" in year["unavailable_evidence"]
    assert "severity" in year["unavailable_evidence"]
    assert result["existing_severities"][0]["severity"] is None
    assert "not estimated" in result["explanation"]


def test_supplied_result_controls_interpretation_without_recalculation() -> None:
    # The ratios deliberately conflict with the supplied flag/result. Task 93
    # must preserve and interpret existing outputs instead of applying a rule.
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "CapEx": 1,
            "D&A": 1_000,
            "Revenue": 50_000,
            "CapEx Growth": -0.95,
            "CapEx / Revenue": 0.00002,
            "CapEx / D&A": 0.001,
            "CapEx Review Flag": True,
            "CapEx Investigation Result": "Needs investigation",
        },
        {
            "Fiscal Year": 2025,
            "Metric": "CapEx vs D&A",
            "Result": "Flag",
            "Severity": "High",
            "Explanation": "Use the supplied result.",
        },
    )

    result = interpret_capex(structured)
    evidence = result["yearly_assessments"][0]["supporting_evidence"]

    assert len(result["concerns"]) == 1
    assert evidence["capex_to_da"] == 0.001
    assert evidence["capex_growth"] == -0.95
    assert result["existing_severities"][0]["severity"] == "High"


def test_existing_project_capex_results_are_preserved() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.master_analysis_table import master_analysis_df
        from Analysis.red_flag_table import red_flag_table_df

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
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=red_flag_table_df,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )

    result = interpret_capex(structured)
    capex_flags = red_flag_table_df.loc[
        red_flag_table_df["Metric"] == "CapEx vs D&A"
    ].reset_index(drop=True)

    severity_by_year = {
        item["fiscal_year"]: item["severity"]
        for item in result["existing_severities"]
    }
    assert severity_by_year[2022] is None
    assert [
        severity_by_year[year] for year in capex_flags["Fiscal Year"]
    ] == capex_flags["Severity"].tolist()
    assert result["yearly_assessments"][0]["supporting_evidence"]["capex"] == (
        master_analysis_df.iloc[0]["Capital Expenditures"]
    )
    assessments_by_year = {
        item["fiscal_year"]: item for item in result["yearly_assessments"]
    }
    first_flag = capex_flags.iloc[0]
    assert assessments_by_year[first_flag["Fiscal Year"]][
        "source_explanation"
    ] == first_flag["Explanation"]


def test_task_90_structure_is_required() -> None:
    try:
        interpret_capex({"financial_summary": [], "red_flags": []})
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
    print("Task 93 CapEx interpretation tests passed")
