"""Focused Task 110 tests for production-pipeline progress reporting."""

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    AnalysisValidationGateResult,
    BlockingIssue,
)
from main import PIPELINE_STAGES, PipelineModules, run_pipeline  # noqa: E402


def _gate(*, partial: bool = False, hard_stop: bool = False):
    issues = ()
    if partial or hard_stop:
        issues = (
            BlockingIssue(
                metric="Revenue",
                fiscal_year=2024,
                validation_source="Task 110 fixture",
                blocking_status=(
                    "INSUFFICIENT_ANNUAL_HISTORY" if hard_stop else "MISSING"
                ),
                explanation="Test validation issue.",
                manual_correction_used=False,
            ),
        )
    return AnalysisValidationGateResult(
        decision=(
            AnalysisDecision.STOP if issues else AnalysisDecision.CONTINUE
        ),
        can_analyze=not issues,
        requested_fiscal_years=(2022, 2023, 2024, 2025),
        blocking_issues=issues,
        metric_year_results=(),
        blocking_issue_count=len(issues),
    )


def _modules(validation, *, fail_calculations: bool = False):
    def calculate(data):
        if fail_calculations:
            raise RuntimeError("calculation failed")
        return ("calculations", data)

    return PipelineModules(
        identify_company=lambda query: ("company", query),
        extract_data=lambda company, years: ("extracted", company, years),
        validate_data=lambda data, years, corrections: validation,
        apply_manual_corrections=lambda data, corrections: (
            "corrected",
            data,
            corrections,
        ),
        run_calculations=calculate,
        run_red_flags_and_severity=lambda calculations: (
            "flags",
            calculations,
        ),
        build_structured_ai_input=lambda *inputs: ("ai input", inputs),
        run_interpretations=lambda structured: ("interpretations", structured),
        generate_excel=lambda *inputs: ("workbook", inputs),
    )


def _expected_events(stages=PIPELINE_STAGES):
    return [
        event
        for stage in stages
        for event in ((stage, "started"), (stage, "completed"))
    ]


def test_complete_analysis_reports_all_stages_in_exact_order():
    events = []

    result = run_pipeline(
        "AMZN",
        4,
        modules=_modules(_gate()),
        progress_callback=lambda stage, status: events.append((stage, status)),
    )

    assert PIPELINE_STAGES == (
        "Data extraction",
        "Validation",
        "Calculations",
        "Red flags",
        "AI interpretation",
        "Excel generation",
    )
    assert events == _expected_events()
    assert result.excel_output[0] == "workbook"


def test_partial_analysis_and_manual_correction_rerun_reach_excel_generation():
    events = []
    correction = object()

    result = run_pipeline(
        "AMZN",
        4,
        modules=_modules(_gate(partial=True)),
        manual_corrections=(correction,),
        progress_callback=lambda stage, status: events.append((stage, status)),
    )

    assert result.partial is True
    assert result.corrected_data[-1] == (correction,)
    assert events == _expected_events()


def test_hard_stop_completes_validation_but_no_later_stage():
    events = []

    result = run_pipeline(
        "AMZN",
        4,
        modules=_modules(_gate(hard_stop=True)),
        progress_callback=lambda stage, status: events.append((stage, status)),
    )

    assert result.blocked is True
    assert events == _expected_events(PIPELINE_STAGES[:2])


def test_failed_stage_is_started_but_never_completed_and_later_stages_do_not_run():
    events = []

    with pytest.raises(RuntimeError, match="calculation failed"):
        run_pipeline(
            "AMZN",
            4,
            modules=_modules(_gate(), fail_calculations=True),
            progress_callback=lambda stage, status: events.append((stage, status)),
        )

    assert events == [
        *_expected_events(PIPELINE_STAGES[:2]),
        ("Calculations", "started"),
    ]


def test_progress_callback_remains_optional():
    result = run_pipeline("AMZN", 4, modules=_modules(_gate()))

    assert result.excel_output[0] == "workbook"
