"""Tests for Task 92 working-capital interpretation."""

import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.ai_input_preparation import build_ai_analysis_input  # noqa: E402
from Analysis.working_capital_interpretation import (  # noqa: E402
    interpret_working_capital,
)
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def task_90_input(working_capital_row):
    fiscal_year = working_capital_row.get("Fiscal Year", 2025)
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
        working_capital_df=pd.DataFrame([working_capital_row]),
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )


def test_existing_working_capital_severity_is_preserved() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Inventory Flag": True,
            "AP Classification": "Possible payment pressure",
            "Working Capital Cash Use": True,
            "Overall Severity": "Medium",
            "Explanation": "Existing source explanation.",
        }
    )

    result = interpret_working_capital(structured)

    assert result["existing_severities"] == [
        {"fiscal_year": 2025, "severity": "Medium"}
    ]
    assert result["yearly_assessments"][0]["source_explanation"] == (
        "Existing source explanation."
    )


def test_positive_existing_results_are_interpreted_as_positive_signals() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2023,
            "Inventory Flag": False,
            "AP Classification": "No AP concern triggered",
            "Working Capital Cash Use": False,
            "Overall Severity": "None",
            "Explanation": "Existing working-capital rules did not trigger.",
        }
    )

    result = interpret_working_capital(structured)

    assert result["concerns"] == []
    assert len(result["positive_signals"]) == 3
    assert "do not trigger" in result["overall_assessment"]


def test_negative_existing_results_are_interpreted_as_concerns() -> None:
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Inventory Flag": True,
            "AP Classification": "Possible payment pressure",
            "Working Capital Cash Use": True,
            "Overall Severity": "Medium",
            "Explanation": "Existing results require review.",
        }
    )

    result = interpret_working_capital(structured)

    assert len(result["concerns"]) == 3
    assert "items for review" in result["overall_assessment"]
    assert not any(
        "buy" in item.lower() or "sell" in item.lower()
        for item in result["concerns"]
    )


def test_missing_evidence_is_marked_unavailable_and_not_invented() -> None:
    structured = task_90_input({"Fiscal Year": 2025})

    result = interpret_working_capital(structured)
    year = result["yearly_assessments"][0]

    assert year["assessment"].startswith("Working-capital assessment is unavailable")
    assert year["supporting_evidence"]["inventory_growth"] is None
    assert year["supporting_evidence"]["ar_change"] is None
    assert "inventory_flag" in year["unavailable_evidence"]
    assert "overall_severity" in year["unavailable_evidence"]
    assert result["existing_severities"][0]["severity"] is None
    assert "not estimated" in result["explanation"]


def test_supplied_results_control_interpretation_without_recalculation() -> None:
    # Contradictory raw numbers demonstrate that no growth, cash-effect, flag,
    # classification, or severity rule is recreated here.
    structured = task_90_input(
        {
            "Fiscal Year": 2025,
            "Revenue Growth": 0.90,
            "Inventory Growth": 0.01,
            "AP Growth": -0.50,
            "OCF Growth": 0.75,
            "AR Change": 10,
            "Inventory Change": 20,
            "AP Change": 30,
            "Net Working Capital Cash Effect": 999,
            "Inventory Flag": True,
            "AP Classification": "Possible payment pressure",
            "Working Capital Cash Use": True,
            "Overall Severity": "Low",
            "Explanation": "Use the supplied results.",
        }
    )

    result = interpret_working_capital(structured)
    evidence = result["yearly_assessments"][0]["supporting_evidence"]

    assert len(result["concerns"]) == 3
    assert evidence["net_working_capital_cash_effect"] == 999
    assert evidence["inventory_growth"] == 0.01
    assert result["existing_severities"][0]["severity"] == "Low"


def test_existing_project_working_capital_results_are_preserved() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.working_capital_red_flags import working_capital_red_flags_df

    gate = AnalysisValidationGateResult(
        decision=AnalysisDecision.CONTINUE,
        can_analyze=True,
        requested_fiscal_years=(2023, 2024, 2025),
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
        working_capital_df=working_capital_red_flags_df,
        taxes_df=empty,
        sbc_df=empty,
        normalized_earnings_df=empty,
        red_flags_df=empty,
        detailed_severity_df=empty,
        fiscal_year_severity_df=empty,
        overall_severity_df=empty,
    )

    result = interpret_working_capital(structured)
    source = working_capital_red_flags_df.reset_index(drop=True)

    assert [item["severity"] for item in result["existing_severities"]] == source[
        "Overall Severity"
    ].tolist()
    assert result["yearly_assessments"][0]["supporting_evidence"][
        "net_working_capital_cash_effect"
    ] == source.iloc[0]["Net Working Capital Cash Effect"]
    assert result["yearly_assessments"][0]["source_explanation"] == source.iloc[0][
        "Explanation"
    ]


def test_positive_and_negative_selected_account_proxies_keep_formula_and_caveat() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.working_capital_red_flags import working_capital_red_flags_df
        from Calculations.working_capital_analysis import working_capital_analysis_df

    calculations = working_capital_analysis_df.set_index("Fiscal Year")
    flags = working_capital_red_flags_df.set_index("Fiscal Year")

    for fiscal_year, expected_value, expected_phrase in (
        (2024, 1492, "proxy suggests a cash benefit"),
        (2025, -3899, "proxy suggests a cash use"),
    ):
        calculation = calculations.loc[fiscal_year]
        expected_formula = (
            -calculation["AR Change"]
            - calculation["Inventory Change"]
            + calculation["AP Change"]
        )
        assert calculation["Net Working-Capital Cash Effect"] == expected_formula
        assert expected_formula == expected_value
        assert expected_phrase in calculation["Net Cash Classification"].lower()
        assert expected_phrase in flags.loc[fiscal_year, "WC Classification"].lower()
        explanation = flags.loc[fiscal_year, "Explanation"].lower()
        assert expected_phrase in explanation
        assert "may cause this proxy to differ from the cash-flow statement" in explanation

    positive_input = task_90_input(flags.loc[2024].to_dict() | {"Fiscal Year": 2024})
    negative_input = task_90_input(flags.loc[2025].to_dict() | {"Fiscal Year": 2025})
    for result, expected_phrase in (
        (interpret_working_capital(positive_input), "proxy suggests a cash benefit"),
        (interpret_working_capital(negative_input), "proxy suggests a cash use"),
    ):
        yearly_text = " ".join(
            result["yearly_assessments"][0]["positive_signals"]
            + result["yearly_assessments"][0]["concerns"]
        ).lower()
        assert expected_phrase in yearly_text
        assert "other working-capital accounts" in result["explanation"].lower()
        assert "foreign exchange" in result["explanation"].lower()
        assert "non-cash effects" in result["explanation"].lower()


def test_task_90_structure_is_required() -> None:
    try:
        interpret_working_capital({"working_capital": []})
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
    print("Task 92 working-capital interpretation tests passed")
