"""Tests for Task 90 validated AI-input preparation."""

import contextlib
import io
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analysis.ai_input_preparation import (  # noqa: E402
    AnalysisInputBlockedError,
    build_ai_analysis_input,
)
from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
)


def gate(
    decision=AnalysisDecision.CONTINUE,
    years=(2024, 2025),
) -> AnalysisValidationGateResult:
    can_analyze = decision is AnalysisDecision.CONTINUE
    return AnalysisValidationGateResult(
        decision=decision,
        can_analyze=can_analyze,
        requested_fiscal_years=years,
        blocking_issues=(),
        metric_year_results=(),
        blocking_issue_count=0 if can_analyze else 1,
    )


def source_frames() -> dict[str, pd.DataFrame]:
    return {
        "financial_summary_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "Revenue": 391_035, "OCF": 118_254}]
        ),
        "cash_conversion_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "AR Flag": True, "Severity": "Medium"}]
        ),
        "working_capital_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "Net Cash Effect": 1_492}]
        ),
        "taxes_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "DTA Growth": pd.NA}]
        ),
        "sbc_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "SBC": 11_688, "Overall SBC Severity": "Medium"}]
        ),
        "normalized_earnings_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "Normalized Net Income": 94_111}]
        ),
        "red_flags_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "Metric": "AR growth", "Result": "Flag", "Severity": "Medium"}]
        ),
        "detailed_severity_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "Metric": "AR growth", "Final Severity": "Needs Investigation"}]
        ),
        "fiscal_year_severity_df": pd.DataFrame(
            [{"Fiscal Year": 2024, "High-Level Severity": "Needs Investigation"}]
        ),
        "overall_severity_df": pd.DataFrame(
            [{"Benchmark Severity": "Material Concern"}]
        ),
    }


def build(**overrides):
    arguments = {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "validation_gate": gate(),
        **source_frames(),
    }
    arguments.update(overrides)
    return build_ai_analysis_input(**arguments)


def test_structured_input_contains_all_required_sections() -> None:
    result = build()

    assert set(result) == {
        "company",
        "financial_summary",
        "cash_conversion",
        "working_capital",
        "taxes",
        "sbc",
        "normalized_earnings",
        "red_flags",
        "overall_assessment",
    }
    assert result["company"] == {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_years": [2024, 2025],
    }


def test_existing_values_flags_and_severities_are_preserved() -> None:
    result = build()

    assert result["financial_summary"][0]["Revenue"] == 391_035
    assert result["cash_conversion"][0]["AR Flag"] is True
    assert result["cash_conversion"][0]["Severity"] == "Medium"
    assert result["red_flags"][0] == {
        "Fiscal Year": 2024,
        "Metric": "AR growth",
        "Result": "Flag",
        "Severity": "Medium",
    }
    assert (
        result["overall_assessment"]["overall_severity"][0]
        ["Benchmark Severity"]
        == "Material Concern"
    )


def test_missing_values_remain_missing_and_are_not_invented() -> None:
    result = build()

    assert result["taxes"][0]["DTA Growth"] is None
    assert "Estimated DTA Growth" not in result["taxes"][0]


def test_result_can_be_serialized_with_json_dumps() -> None:
    serialized = json.dumps(build())

    assert '"DTA Growth": null' in serialized
    assert '"Material Concern"' in serialized


def test_existing_project_analysis_dataframes_are_serializable() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from Analysis.accrual_red_flags import accrual_red_flags_df
        from Analysis.master_analysis_table import analyst_summary_df
        from Analysis.normalization_red_flags import normalization_red_flags_df
        from Analysis.red_flag_table import red_flag_table_df
        from Analysis.sbc_red_flags import sbc_red_flags_df
        from Analysis.severity_system import (
            benchmark_severity_df,
            detailed_severity_table_df,
            fiscal_year_severity_summary_df,
        )
        from Analysis.tax_red_flags import tax_red_flags_df
        from Analysis.working_capital_red_flags import working_capital_red_flags_df

    result = build_ai_analysis_input(
        company_name="Apple Inc.",
        ticker="AAPL",
        validation_gate=gate(years=(2022, 2023, 2024, 2025)),
        financial_summary_df=analyst_summary_df,
        cash_conversion_df=accrual_red_flags_df,
        working_capital_df=working_capital_red_flags_df,
        taxes_df=tax_red_flags_df,
        sbc_df=sbc_red_flags_df,
        normalized_earnings_df=normalization_red_flags_df,
        red_flags_df=red_flag_table_df,
        detailed_severity_df=detailed_severity_table_df,
        fiscal_year_severity_df=fiscal_year_severity_summary_df,
        overall_severity_df=benchmark_severity_df,
    )

    json.dumps(result)
    assert result["financial_summary"][0]["Revenue"] == analyst_summary_df.iloc[0]["Revenue"]
    assert result["red_flags"][0]["Severity"] == red_flag_table_df.iloc[0]["Severity"]
    assert result["overall_assessment"]["overall_severity"][0][
        "Benchmark Severity"
    ] == benchmark_severity_df.iloc[0]["Benchmark Severity"]


def test_task_89_stop_decision_blocks_input_preparation() -> None:
    try:
        build(validation_gate=gate(AnalysisDecision.STOP))
    except AnalysisInputBlockedError as error:
        assert "Task 89" in str(error)
    else:
        raise AssertionError("A STOP gate must block analysis preparation")


def test_non_task_89_gate_object_is_rejected() -> None:
    try:
        build(validation_gate=True)
    except TypeError as error:
        assert "Task 89" in str(error)
    else:
        raise AssertionError("A non-Task 89 gate object must be rejected")


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Task 90 AI-input preparation tests passed")
