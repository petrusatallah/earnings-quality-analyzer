"""Focused tests for Task 89 final annual analysis validation gate."""

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Data.analysis_validation_gate import (  # noqa: E402
    AnalysisDecision,
    STANDARD_CORE_METRICS,
    clear_blocked_analysis_state,
    evaluate_analysis_validation_gate,
    evaluate_integrated_annual_dataset,
    run_analysis_if_valid,
)
from Data.fiscal_year_validator import ANNUAL_DURATION_METRICS  # noqa: E402
from Data.duplicate_value_validator import DuplicateClassification  # noqa: E402
from Data.financial_statement_fetcher import FactStatus  # noqa: E402
from Data.label_mapper import LabelMappingStatus  # noqa: E402
from Data.manual_corrections import create_manual_correction  # noqa: E402
from Data.missing_data_validator import (  # noqa: E402
    ValidationStatus,
    validate_annual_missing_data,
)


@dataclass(frozen=True)
class Record:
    metric_name: str
    fiscal_year: int
    raw_sec_value: object
    raw_unit: str = "USD"
    status: FactStatus = FactStatus.RETRIEVED
    source_url: str = "https://www.sec.gov/source"


def valid_inputs(years=(2024,)) -> dict:
    missing = []
    units = []
    duplicates = []
    fiscal = []
    labels = []
    for year in years:
        for metric in STANDARD_CORE_METRICS:
            missing.append(SimpleNamespace(metric=metric, fiscal_year=year,
                                           status=ValidationStatus.PRESENT))
            units.append(SimpleNamespace(metric=metric, fiscal_year=year,
                                         validation_status=FactStatus.RETRIEVED,
                                         reason=None, unit_is_valid=True))
            duplicates.append(SimpleNamespace(
                metric=metric, fiscal_year=year,
                duplicate_classification=DuplicateClassification.NO_DUPLICATE,
                validation_status=FactStatus.RETRIEVED,
                explanation="One usable record.",
            ))
            fiscal.append(SimpleNamespace(metric=metric, requested_fiscal_year=year,
                                          validation_status=FactStatus.RETRIEVED,
                                          explanation="Valid annual period.",
                                          period_metadata_valid=True))
            labels.append(SimpleNamespace(metric=metric, fiscal_year=year,
                                          mapping_status=LabelMappingStatus.MAPPED,
                                          validation_status=FactStatus.RETRIEVED,
                                          explanation="Controlled mapping."))
    return {
        "requested_fiscal_years": years,
        "missing_data_result": SimpleNamespace(statuses=missing),
        "unit_results": units,
        "duplicate_results": duplicates,
        "fiscal_year_results": fiscal,
        "label_results": labels,
    }


def integrated_records(years=(2024,)) -> list[Record]:
    records = []
    for year in years:
        for metric in STANDARD_CORE_METRICS:
            is_duration = metric in ANNUAL_DURATION_METRICS
            records.append(SimpleNamespace(
                metric_name=metric,
                fiscal_year=year,
                raw_sec_value=100,
                raw_unit="shares" if metric == "Shares Outstanding" else "USD",
                status=FactStatus.RETRIEVED,
                period_start=f"{year - 1}-01-01" if is_duration else None,
                period_end=f"{year - 1}-12-31" if is_duration else None,
                balance_sheet_date=None if is_duration else f"{year - 1}-12-31",
                filing_form="10-K",
                accession_number=f"{year}-{metric}",
                source_url="https://www.sec.gov/source",
            ))
    return records


def selected_app_dataframe() -> pd.DataFrame:
    rows = []
    for metric in STANDARD_CORE_METRICS:
        display_metric = "Tax Expense" if metric == "Income Tax Expense" else metric
        is_duration = metric in ANNUAL_DURATION_METRICS
        rows.append(
            {
                "Fiscal Year": 2022,
                "Metric": display_metric,
                "Value": 4946 if metric == "Inventory" else 100,
                "Units": (
                    "millions of shares"
                    if metric == "Shares Outstanding"
                    else "USD millions"
                ),
                "Raw Unit": "shares" if metric == "Shares Outstanding" else "USD",
                "Status": FactStatus.RETRIEVED,
                "Period Start": "2021-09-26" if is_duration else None,
                "Period End": "2022-09-24" if is_duration else None,
                "Balance Sheet Date": None if is_duration else "2022-09-24",
                "Filing Form": "10-K",
                "Source": "Apple Form 10-K",
            }
        )
    return pd.DataFrame(rows)


def replace_result(items, metric, year, **changes):
    for index, item in enumerate(items):
        item_metric = getattr(item, "metric")
        item_year = getattr(item, "fiscal_year", getattr(item, "requested_fiscal_year", None))
        if item_metric == metric and item_year == year:
            values = vars(item).copy()
            values.update(changes)
            items[index] = SimpleNamespace(**values)
            return
    raise AssertionError("Result not found")


def test_completely_valid_dataset_continues() -> None:
    gate = evaluate_analysis_validation_gate(**valid_inputs())
    assert gate.decision is AnalysisDecision.CONTINUE
    assert gate.can_analyze
    assert gate.blocking_issue_count == 0


def test_one_required_missing_metric_stops() -> None:
    inputs = valid_inputs()
    replace_result(inputs["missing_data_result"].statuses, "Revenue", 2024,
                   status=ValidationStatus.MISSING)
    gate = evaluate_analysis_validation_gate(**inputs)
    assert gate.decision is AnalysisDecision.STOP
    assert any(i.metric == "Revenue" and i.fiscal_year == 2024 for i in gate.blocking_issues)


def test_multiple_missing_items_are_all_reported() -> None:
    inputs = valid_inputs((2023, 2024))
    statuses = inputs["missing_data_result"].statuses
    replace_result(statuses, "Inventory", 2023, status=ValidationStatus.MISSING)
    replace_result(statuses, "Deferred Tax Assets", 2024, status=ValidationStatus.MISSING)
    gate = evaluate_analysis_validation_gate(**inputs)
    pairs = {(i.metric, i.fiscal_year) for i in gate.blocking_issues}
    assert ("Inventory", 2023) in pairs
    assert ("Deferred Tax Assets", 2024) in pairs


def test_conflicting_duplicate_stops() -> None:
    inputs = valid_inputs()
    replace_result(inputs["duplicate_results"], "Revenue", 2024,
                   duplicate_classification=DuplicateClassification.CONFLICTING_DUPLICATE,
                   validation_status=FactStatus.NEEDS_VALIDATION)
    gate = evaluate_analysis_validation_gate(**inputs)
    assert gate.decision is AnalysisDecision.STOP
    assert any(i.blocking_status == "CONFLICTING DUPLICATE" for i in gate.blocking_issues)


def test_invalid_unit_stops() -> None:
    inputs = valid_inputs()
    replace_result(inputs["unit_results"], "Revenue", 2024,
                   validation_status=FactStatus.NEEDS_VALIDATION,
                   reason="Raw unit 'shares' is incompatible.")
    gate = evaluate_analysis_validation_gate(**inputs)
    assert any(i.validation_source.startswith("Task 84") for i in gate.blocking_issues)


def test_wrong_fiscal_year_stops() -> None:
    inputs = valid_inputs()
    replace_result(inputs["fiscal_year_results"], "Inventory", 2024,
                   validation_status=FactStatus.NEEDS_VALIDATION,
                   explanation="Point-in-time date does not match fiscal-year-end.")
    gate = evaluate_analysis_validation_gate(**inputs)
    assert any(i.metric == "Inventory" and "fiscal-year" in i.explanation for i in gate.blocking_issues)


def test_unmapped_required_label_stops() -> None:
    inputs = valid_inputs()
    replace_result(inputs["label_results"], "Revenue", 2024,
                   mapping_status=LabelMappingStatus.UNMAPPED,
                   validation_status=FactStatus.NEEDS_VALIDATION)
    assert evaluate_analysis_validation_gate(**inputs).decision is AnalysisDecision.STOP


def test_identical_duplicate_does_not_automatically_stop() -> None:
    inputs = valid_inputs()
    replace_result(inputs["duplicate_results"], "Revenue", 2024,
                   duplicate_classification=DuplicateClassification.IDENTICAL_DUPLICATE)
    assert evaluate_analysis_validation_gate(**inputs).decision is AnalysisDecision.CONTINUE


def test_active_manual_correction_can_supply_missing_value_without_erasing_original() -> None:
    inputs = valid_inputs()
    replace_result(inputs["missing_data_result"].statuses, "Revenue", 2024,
                   status=ValidationStatus.MISSING)
    replace_result(inputs["unit_results"], "Revenue", 2024,
                   validation_status=FactStatus.MISSING,
                   reason="Underlying value is MISSING.")
    replace_result(inputs["duplicate_results"], "Revenue", 2024,
                   validation_status=FactStatus.MISSING)
    replace_result(inputs["label_results"], "Revenue", 2024,
                   validation_status=FactStatus.MISSING)
    record = Record("Revenue", 2024, None, status=FactStatus.MISSING)
    correction = create_manual_correction(record, 125, "Reviewed annual filing")
    inputs["corrections"] = [correction]
    gate = evaluate_analysis_validation_gate(**inputs)
    result = next(item for item in gate.metric_year_results if item.metric == "Revenue")
    assert gate.decision is AnalysisDecision.CONTINUE
    assert result.manual_correction_used and result.effective_value == 125
    assert record.raw_sec_value is None
    assert correction.original_record is record


def test_correction_does_not_bypass_unrelated_failures() -> None:
    inputs = valid_inputs()
    record = Record("Revenue", 2024, 100)
    inputs["corrections"] = [create_manual_correction(record, 125, "Reviewed filing")]
    replace_result(inputs["unit_results"], "Revenue", 2024,
                   validation_status=FactStatus.NEEDS_VALIDATION,
                   reason="Invalid unit.", unit_is_valid=False)
    replace_result(inputs["fiscal_year_results"], "Revenue", 2024,
                   validation_status=FactStatus.NEEDS_VALIDATION,
                   explanation="Wrong fiscal year.", period_metadata_valid=False)
    gate = evaluate_analysis_validation_gate(**inputs)
    assert gate.decision is AnalysisDecision.STOP
    assert {i.validation_source[:7] for i in gate.blocking_issues} >= {"Task 84", "Task 86"}


def test_analysis_callable_is_guarded_by_decision() -> None:
    calls = []
    valid_gate = evaluate_analysis_validation_gate(**valid_inputs())
    assert run_analysis_if_valid(valid_gate, lambda: calls.append("ran") or 7) == 7
    assert calls == ["ran"]

    invalid = valid_inputs()
    replace_result(invalid["unit_results"], "Revenue", 2024,
                   validation_status=FactStatus.NEEDS_VALIDATION)
    stopped_gate = evaluate_analysis_validation_gate(**invalid)
    assert run_analysis_if_valid(stopped_gate, lambda: calls.append("must not run")) is None
    assert calls == ["ran"]


def test_valid_integrated_dataset_runs_validators_and_continues() -> None:
    records = integrated_records()
    gate = evaluate_integrated_annual_dataset(
        records,
        requested_fiscal_years=[2024],
        fiscal_year_end_dates={2024: "2023-12-31"},
    )
    assert gate.decision is AnalysisDecision.CONTINUE
    assert gate.blocking_issues == ()


def test_selected_app_value_is_present_to_task_83() -> None:
    selected_data = selected_app_dataframe()
    result = validate_annual_missing_data(selected_data.to_dict("records"), [2022])
    assert result.status_for("Inventory", 2022) is ValidationStatus.PRESENT
    assert result.present_count == 13
    assert result.missing_count == 0


def test_2022_inventory_4946_is_not_reported_missing_by_integrated_gate() -> None:
    selected_data = selected_app_dataframe()
    inventory = selected_data.loc[
        selected_data["Metric"].eq("Inventory")
        & selected_data["Fiscal Year"].eq(2022),
        "Value",
    ].iloc[0]
    assert inventory == 4946

    gate = evaluate_integrated_annual_dataset(
        selected_data,
        requested_fiscal_years=[2022],
        fiscal_year_end_dates={2022: "2022-09-24"},
    )
    assert gate.decision is AnalysisDecision.CONTINUE
    assert gate.can_analyze
    assert not any(
        issue.validation_source == "Task 83 missing-data validation"
        for issue in gate.blocking_issues
    )
    assert not any(
        issue.metric == "Inventory" and issue.fiscal_year == 2022
        for issue in gate.blocking_issues
    )


def test_active_correction_resolves_missing_raw_value_with_valid_metadata() -> None:
    selected_data = selected_app_dataframe()
    inventory_mask = selected_data["Metric"].eq("Inventory")
    selected_data.loc[inventory_mask, "Value"] = None
    selected_data.loc[inventory_mask, "Status"] = FactStatus.MISSING
    assert pd.isna(selected_data.loc[inventory_mask, "Value"].iloc[0])
    assert selected_data.loc[inventory_mask, "Value"].iloc[0] != 0
    missing_record = selected_data.loc[inventory_mask].iloc[0].to_dict()
    correction = create_manual_correction(
        missing_record,
        4946,
        "Confirmed from the annual filing",
        corrected_unit="USD",
    )

    gate = evaluate_integrated_annual_dataset(
        selected_data,
        requested_fiscal_years=[2022],
        fiscal_year_end_dates={2022: "2022-09-24"},
        corrections=[correction],
    )
    inventory_result = next(
        item for item in gate.metric_year_results if item.metric == "Inventory"
    )
    assert gate.decision is AnalysisDecision.CONTINUE
    assert gate.can_analyze
    assert not any(
        issue.validation_source == "Task 83 missing-data validation"
        for issue in gate.blocking_issues
    )
    assert inventory_result.manual_correction_used
    assert inventory_result.effective_value == 4946
    assert pd.isna(missing_record["Value"])
    assert missing_record["Status"] is FactStatus.MISSING


def test_first_year_derived_na_values_are_not_raw_validation_failures() -> None:
    selected_data = selected_app_dataframe()
    derived_names = (
        "Revenue Growth",
        "AR Growth",
        "Inventory Growth",
        "Working Capital Change",
    )
    for name in derived_names:
        selected_data[name] = None

    derived_rows = pd.DataFrame(
        {
            "Fiscal Year": [2022] * len(derived_names),
            "Metric": derived_names,
            "Value": [None] * len(derived_names),
            "Status": [FactStatus.MISSING] * len(derived_names),
        }
    )
    validation_input = pd.concat([selected_data, derived_rows], ignore_index=True)
    raw_inventory_before = validation_input.loc[
        validation_input["Metric"].eq("Inventory"), ["Value", "Status"]
    ].iloc[0].copy()

    gate = evaluate_integrated_annual_dataset(
        validation_input,
        requested_fiscal_years=[2022],
        fiscal_year_end_dates={2022: "2022-09-24"},
    )
    assert gate.decision is AnalysisDecision.CONTINUE
    assert gate.blocking_issues == ()
    assert not any(
        issue.validation_source == "Task 83 missing-data validation"
        for issue in gate.blocking_issues
    )
    assert all(name not in {item.metric for item in gate.metric_year_results} for name in derived_names)
    raw_inventory_after = validation_input.loc[
        validation_input["Metric"].eq("Inventory"), ["Value", "Status"]
    ].iloc[0]
    assert raw_inventory_after.equals(raw_inventory_before)
    assert raw_inventory_after["Value"] == 4946
    assert raw_inventory_after["Status"] is FactStatus.RETRIEVED


def test_validation_and_analysis_share_all_metric_year_records_without_view_layer() -> None:
    selected_data = selected_app_dataframe()
    before = selected_data[["Fiscal Year", "Metric", "Value"]].copy(deep=True)
    gate = evaluate_integrated_annual_dataset(
        selected_data,
        requested_fiscal_years=[2022],
        fiscal_year_end_dates={2022: "2022-09-24"},
    )
    validated_keys = {
        (item.fiscal_year, item.metric) for item in gate.metric_year_results
    }
    analysis_keys = {
        (int(row["Fiscal Year"]), "Income Tax Expense" if row["Metric"] == "Tax Expense" else row["Metric"])
        for row in selected_data.to_dict("records")
    }
    assert validated_keys == analysis_keys
    assert len(validated_keys) == 13
    pd.testing.assert_frame_equal(
        before, selected_data[["Fiscal Year", "Metric", "Value"]]
    )

    gate_source = (PROJECT_ROOT / "Data" / "analysis_validation_gate.py").read_text(
        encoding="utf-8"
    )
    app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    assert "_ValidationRecordView" not in gate_source
    assert "selected_annual_records" not in app_source
    assert gate.decision is AnalysisDecision.CONTINUE
    assert gate.blocking_issues == ()
    assert all(
        issue.blocking_status != "MISSING RESULT" for issue in gate.blocking_issues
    )


def test_integrated_missing_item_reports_only_exact_task_83_blocker() -> None:
    records = [
        record for record in integrated_records()
        if record.metric_name != "Inventory"
    ]
    gate = evaluate_integrated_annual_dataset(
        records,
        requested_fiscal_years=[2024],
        fiscal_year_end_dates={2024: "2023-12-31"},
    )
    assert gate.decision is AnalysisDecision.STOP
    assert gate.blocking_issue_count == 1
    issue = gate.blocking_issues[0]
    assert (issue.fiscal_year, issue.metric) == (2024, "Inventory")
    assert issue.validation_source == "Task 83 missing-data validation"
    assert issue.blocking_status == "MISSING"
    assert "MISSING RESULT" not in {item.blocking_status for item in gate.blocking_issues}

    missing_values = {
        (item.fiscal_year, item.metric)
        for item in gate.blocking_issues
        if item.validation_source == "Task 83 missing-data validation"
    }
    assert missing_values == {(2024, "Inventory")}


def test_blocked_ui_state_clears_stale_analysis_but_preserves_corrections() -> None:
    state = {
        "analysis_results": {"stale": True},
        "cached_analysis_results": [1, 2, 3],
        "manual_corrections": {("Revenue", 2024): "keep"},
        "analysis_validation_gate_result": "keep gate",
    }
    removed = clear_blocked_analysis_state(state)
    assert set(removed) == {"analysis_results", "cached_analysis_results"}
    assert "analysis_results" not in state
    assert "cached_analysis_results" not in state
    assert state["manual_corrections"] == {("Revenue", 2024): "keep"}
    assert state["analysis_validation_gate_result"] == "keep gate"


def test_app_uses_non_terminating_blocked_layout_with_manual_corrections() -> None:
    app_source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.stop()" not in app_source
    assert "if not analysis_blocked:" in app_source
    assert "Analysis unavailable until the validation issues above are resolved." in app_source
    assert "clear_blocked_analysis_state(st.session_state)" in app_source
    assert 'st.expander(f"Missing Values ({len(missing_values)})"' in app_source
    assert 'st.expander("Correct Extracted Data", expanded=False)' in app_source
    assert "No missing required values." in app_source
    assert "Validation Audit Details" not in app_source
    assert 'st.button("Analyze"' in app_source
    assert 'st.popover("Download Reports"' in app_source
    assert "background-color: #fdecee" in app_source
    assert '.format(na_rep="", subset=["Value"])' in app_source

if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items() if name.startswith("test_")]
    for test in tests:
        test()
    print("Repair Task 3 UI and end-to-end tests passed")
