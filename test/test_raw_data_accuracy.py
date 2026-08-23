"""Task 100: exact raw-data accuracy checks against the Task 99 benchmark."""

import contextlib
import io
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Data.apple_test_dataset import apple_financial_data_df  # noqa: E402

from Data.manual_verified_answer_sheet import (  # noqa: E402
    MANUAL_VERIFIED_ANSWER_SHEET,
)


FIELDS = (
    "Company",
    "Ticker",
    "Fiscal Year",
    "Metric",
    "Value",
    "Units",
    "Financial Statement",
    "Source",
    "Source Date",
)


def _expected_records_from_task_99():
    """Expose fixed Task 99 answers as rows without using production values."""

    sheet = MANUAL_VERIFIED_ANSWER_SHEET
    company = sheet["benchmark"]["company"]
    ticker = sheet["benchmark"]["ticker"]
    expected = {}

    for fiscal_year in sheet["benchmark"]["fiscal_years"]:
        year_answer = sheet["raw_financial_data"][fiscal_year]
        for metric, detail in year_answer["data"].items():
            key = (fiscal_year, metric)
            expected[key] = {
                "Company": company,
                "Ticker": ticker,
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": year_answer["expected_result"][metric],
                "Units": detail["units"],
                "Financial Statement": detail["financial_statement"],
                "Source": year_answer["source"]["name"],
                "Source Date": year_answer["source"]["source_date"],
            }
    return expected


def _actual_records_by_key():
    missing_columns = [field for field in FIELDS if field not in apple_financial_data_df]
    assert not missing_columns, f"Apple raw dataset is missing fields: {missing_columns!r}"

    records = apple_financial_data_df.loc[:, list(FIELDS)].to_dict("records")
    indexed = {}
    duplicates = []
    for record in records:
        key = (record["Fiscal Year"], record["Metric"])
        if key in indexed:
            duplicates.append(key)
        indexed[key] = record
    assert not duplicates, f"Duplicate Apple raw benchmark records: {duplicates!r}"
    return records, indexed


def test_all_raw_benchmark_records_match_task_99_exactly() -> None:
    expected = _expected_records_from_task_99()
    actual_rows, actual = _actual_records_by_key()
    errors = []

    expected_keys = set(expected)
    actual_keys = set(actual)
    for fiscal_year, metric in sorted(expected_keys - actual_keys):
        errors.append(
            "fiscal_year={!r}, metric={!r}, field='<record>', "
            "expected='present', actual='<missing>'".format(fiscal_year, metric)
        )
    for fiscal_year, metric in sorted(actual_keys - expected_keys):
        errors.append(
            "fiscal_year={!r}, metric={!r}, field='<record>', "
            "expected='<absent>', actual='present'".format(fiscal_year, metric)
        )

    for key in sorted(expected_keys & actual_keys):
        fiscal_year, metric = key
        for field in FIELDS:
            expected_value = expected[key][field]
            actual_value = actual[key][field]
            if actual_value != expected_value:
                errors.append(
                    "fiscal_year={!r}, metric={!r}, field={!r}, expected={!r}, "
                    "actual={!r}".format(
                        fiscal_year,
                        metric,
                        field,
                        expected_value,
                        actual_value,
                    )
                )

    assert len(expected) == 52, (
        f"Task 99 must contain 52 raw benchmark records; actual={len(expected)!r}"
    )
    assert len(actual_rows) == 52, (
        f"Apple dataset must contain 52 raw benchmark records; actual={len(actual_rows)!r}"
    )
    assert not errors, "Raw data accuracy mismatches:\n" + "\n".join(errors)


def test_task_99_covers_every_benchmark_year_and_raw_metric() -> None:
    sheet = MANUAL_VERIFIED_ANSWER_SHEET
    expected = _expected_records_from_task_99()
    years = sheet["benchmark"]["fiscal_years"]
    first_year_metrics = set(sheet["raw_financial_data"][years[0]]["data"])

    assert years == [2022, 2023, 2024, 2025]
    assert len(first_year_metrics) == 13
    assert set(expected) == {
        (fiscal_year, metric)
        for fiscal_year in years
        for metric in first_year_metrics
    }


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Task 100 raw data accuracy tests passed")

