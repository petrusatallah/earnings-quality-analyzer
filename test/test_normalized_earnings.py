"""Task 103: verify normalized earnings against fixed Task 99 answers."""

import contextlib
import io
import math
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.normalization_red_flags import normalization_red_flags_df
    from Calculations.normalized_net_income import (
        available_items,
        normalized_net_income_df,
    )

from Data.manual_verified_answer_sheet import MANUAL_VERIFIED_ANSWER_SHEET


TOLERANCE = 1e-9


def _compare(errors, year, field, expected, actual):
    if isinstance(expected, float):
        matches = math.isclose(float(actual), expected, rel_tol=TOLERANCE, abs_tol=TOLERANCE)
    else:
        matches = actual == expected
    if not matches:
        errors.append(
            "fiscal_year={!r}, field={!r}, expected={!r}, actual={!r}".format(
                year, field, expected, actual
            )
        )


def test_normalized_earnings_and_related_flags_match_task_99() -> None:
    fixed = MANUAL_VERIFIED_ANSWER_SHEET["normalized_earnings_results"]
    expected = fixed["expected_result"]
    normalized = normalized_net_income_df.set_index("Fiscal Year")
    flags = normalization_red_flags_df.set_index("Fiscal Year")
    errors = []

    calculation_fields = {
        "normalized_net_income": "Normalized Net Income",
        "difference": "Normalized NI Difference",
        "percentage_difference": "Normalized NI Difference Percentage",
    }
    flag_fields = {
        "large_difference_flag": "Large Normalization Difference Flag",
        "repeated_one_off_flag": "Repeated One-Off Flag",
        "overall_severity": "Overall Severity",
    }
    for year, year_expected in expected.items():
        _compare(errors, year, "reported_net_income", fixed["data"][year]["reported_net_income"], normalized.loc[year, "Reported Net Income"])
        _compare(errors, year, "net_normalization_adjustment", fixed["data"][year]["net_normalization_adjustment"], normalized.loc[year, "Net Normalization Adjustment"])
        for expected_field, actual_field in calculation_fields.items():
            _compare(errors, year, expected_field, year_expected[expected_field], normalized.loc[year, actual_field])
        for expected_field, actual_field in flag_fields.items():
            _compare(errors, year, expected_field, year_expected[expected_field], flags.loc[year, actual_field])
        if "normalization_signal" in year_expected:
            _compare(errors, year, "normalization_signal", year_expected["normalization_signal"], flags.loc[year, "Normalization Signal"])

    known = available_items.loc[
        (available_items["Fiscal Year"] == 2024)
        & (available_items["Category"] == "Unusual tax gains/losses")
    ]
    if len(known) != 1:
        errors.append(
            "fiscal_year=2024, field='one_off_record_count', expected=1, actual={!r}".format(len(known))
        )
    else:
        actual_item = known.iloc[0]
        expected_item = fixed["data"][2024]
        item_fields = {
            "one_off_categories": "Category",
            "description": "Description",
            "direction": "Direction",
            "tax_basis": "Tax Basis",
            "manual_classification": "Manual Classification",
            "manual_review_status": "Manual Review Status",
            "adjustment_status": "Adjustment Status",
            "net_normalization_adjustment": "Normalization Adjustment",
        }
        for expected_field, actual_field in item_fields.items():
            _compare(errors, 2024, expected_field, expected_item[expected_field], actual_item[actual_field])

    _compare(errors, "all", "large_difference_rule", fixed["formula_or_rule"]["large_difference"], flags["Large Difference Rule"].iloc[0])
    _compare(errors, "all", "repeated_one_off_rule", fixed["formula_or_rule"]["repeated_one_off"], flags["Repeated One-Off Rule"].iloc[0])
    assert not errors, "Normalized-earnings mismatches:\n" + "\n".join(errors)


if __name__ == "__main__":
    test_normalized_earnings_and_related_flags_match_task_99()
    print("Task 103 normalized earnings tests passed")
