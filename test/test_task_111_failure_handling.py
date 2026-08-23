"""Focused Task 111 tests for stage-specific pipeline failures."""

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
from main import (  # noqa: E402
    PIPELINE_STAGES,
    PipelineModules,
    PipelineStageError,
    run_pipeline,
)


def _validation(*, partial=False, hard_stop=False):
    issues = ()
    if partial or hard_stop:
        issues = (
            BlockingIssue(
                metric="Revenue",
                fiscal_year=2024,
                validation_source="Task 111 fixture",
                blocking_status=(
                    "INSUFFICIENT_ANNUAL_HISTORY" if hard_stop else "MISSING"
                ),
                explanation="Fixture issue.",
                manual_correction_used=False,
            ),
        )
    return AnalysisValidationGateResult(
        decision=AnalysisDecision.STOP if issues else AnalysisDecision.CONTINUE,
        can_analyze=not issues,
        requested_fiscal_years=(2022, 2023, 2024, 2025),
        blocking_issues=issues,
        metric_year_results=(),
        blocking_issue_count=len(issues),
    )


def _modules(*, validation=None, failed_stage=None, original_error=None, executed=None):
    validation = validation or _validation()
    executed = executed if executed is not None else []

    def run_stage(stage, result):
        executed.append(stage)
        if stage == failed_stage:
            raise original_error
        return result

    return PipelineModules(
        identify_company=lambda query: ("company", query),
        extract_data=lambda company, years: run_stage(
            "Data extraction", ("data", company, years)
        ),
        validate_data=lambda data, years, corrections: run_stage(
            "Validation", validation
        ),
        apply_manual_corrections=lambda data, corrections: (
            "corrected",
            data,
            corrections,
        ),
        run_calculations=lambda data: run_stage("Calculations", ("calc", data)),
        run_red_flags_and_severity=lambda calculations: run_stage(
            "Red flags", ("flags", calculations)
        ),
        build_structured_ai_input=lambda *inputs: ("structured", inputs),
        run_interpretations=lambda structured: run_stage(
            "AI interpretation", ("interpretation", structured)
        ),
        generate_excel=lambda *inputs: run_stage(
            "Excel generation", ("excel", inputs)
        ),
    )


def _completed_events(stages):
    return [
        event
        for stage in stages
        for event in ((stage, "started"), (stage, "completed"))
    ]


@pytest.mark.parametrize("failed_stage", PIPELINE_STAGES)
def test_each_stage_failure_is_structured_and_stops_the_pipeline(failed_stage):
    original_error = ValueError(f"original details for {failed_stage}")
    executed = []
    events = []

    with pytest.raises(PipelineStageError) as captured:
        run_pipeline(
            "AMZN",
            4,
            modules=_modules(
                failed_stage=failed_stage,
                original_error=original_error,
                executed=executed,
            ),
            progress_callback=lambda stage, status: events.append((stage, status)),
        )

    failed_index = PIPELINE_STAGES.index(failed_stage)
    failure = captured.value
    assert failure.failed_stage == failed_stage
    assert failure.original_error is original_error
    assert failure.original_message == str(original_error)
    assert str(original_error) in str(failure)
    assert failure.__cause__ is original_error
    assert executed == list(PIPELINE_STAGES[: failed_index + 1])
    assert events == [
        *_completed_events(PIPELINE_STAGES[:failed_index]),
        (failed_stage, "started"),
    ]
    assert (failed_stage, "completed") not in events


def test_validation_hard_stop_remains_a_blocked_result_not_a_failure():
    events = []
    executed = []

    result = run_pipeline(
        "AMZN",
        4,
        modules=_modules(validation=_validation(hard_stop=True), executed=executed),
        progress_callback=lambda stage, status: events.append((stage, status)),
    )

    assert result.blocked is True
    assert executed == ["Data extraction", "Validation"]
    assert events == _completed_events(PIPELINE_STAGES[:2])


def test_partial_analysis_is_not_a_failure_and_reaches_excel_generation():
    events = []
    executed = []

    result = run_pipeline(
        "AMZN",
        4,
        modules=_modules(validation=_validation(partial=True), executed=executed),
        manual_corrections=(object(),),
        progress_callback=lambda stage, status: events.append((stage, status)),
    )

    assert result.partial is True
    assert result.excel_output[0] == "excel"
    assert executed == list(PIPELINE_STAGES)
    assert events == _completed_events(PIPELINE_STAGES)


def test_failure_handling_does_not_require_a_progress_callback():
    original_error = RuntimeError("excel writer unavailable")

    with pytest.raises(PipelineStageError) as captured:
        run_pipeline(
            "AMZN",
            4,
            modules=_modules(
                failed_stage="Excel generation",
                original_error=original_error,
            ),
        )

    assert captured.value.failed_stage == "Excel generation"
    assert captured.value.original_error is original_error


if __name__ == "__main__":
    exit_code = pytest.main([__file__, "-q"])
    if exit_code == 0:
        print("Task 111 failure handling tests passed")
    raise SystemExit(exit_code)
