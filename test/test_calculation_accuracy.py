"""Task 101: compare every benchmarked calculation with fixed Task 99 answers."""

import contextlib
import io
import math
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.ap_warning import ap_warning_df  # noqa: E402
    from Analysis.buyback_adjustment import buyback_adjustment_df  # noqa: E402
    from Analysis.dta_analysis import dta_analysis_df  # noqa: E402
    from Analysis.dtl_analysis import dtl_analysis_df  # noqa: E402
    from Analysis.inventory_warning import inventory_warning_df  # noqa: E402
    from Calculations.ar_growth import ar_growth_df  # noqa: E402
    from Calculations.capex_analysis import capex_analysis_df  # noqa: E402
    from Calculations.da_analysis import da_analysis_df  # noqa: E402
    from Calculations.free_cash_flow import free_cash_flow_df  # noqa: E402
    from Calculations.net_income_growth import net_income_growth_df  # noqa: E402
    from Calculations.ocf_growth import ocf_growth_df  # noqa: E402
    from Calculations.revenue_growth import revenue_growth_df  # noqa: E402
    from Calculations.sbc_analysis import sbc_analysis_df  # noqa: E402
    from Calculations.share_dilution import share_dilution_df  # noqa: E402
    from Calculations.working_capital_analysis import (  # noqa: E402
        working_capital_analysis_df,
    )
    from Calculations.working_capital_movements import (  # noqa: E402
        working_capital_movements_df,
    )

from Data.manual_verified_answer_sheet import (  # noqa: E402
    MANUAL_VERIFIED_ANSWER_SHEET,
)


DECIMAL_ABS_TOLERANCE = 1e-9
DECIMAL_REL_TOLERANCE = 1e-9

EXPECTED_CALCULATIONS = {
    "Revenue Growth",
    "Net Income Growth",
    "OCF Growth",
    "AR Growth",
    "AR vs Revenue Gap",
    "D&A Growth",
    "D&A / Revenue",
    "CapEx Growth",
    "CapEx / Revenue",
    "CapEx / D&A",
    "Free Cash Flow",
    "AR Change",
    "Inventory Change",
    "AP Change",
    "Net Working-Capital Cash Effect",
    "Inventory Growth",
    "AP Growth",
    "SBC / Revenue",
    "SBC / OCF",
    "SBC / Net Income",
    "Shares Outstanding Growth",
    "Net Share Effect",
    "Buyback Offset Ratio",
    "DTA / Net Income",
    "DTA Growth",
    "DTL Growth",
}


def _is_missing(value):
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _record_error(errors, calculation, fiscal_year, expected, actual):
    if expected is None:
        matches = _is_missing(actual)
    elif isinstance(expected, float):
        try:
            matches = not _is_missing(actual) and math.isclose(
                float(actual),
                expected,
                rel_tol=DECIMAL_REL_TOLERANCE,
                abs_tol=DECIMAL_ABS_TOLERANCE,
            )
        except (TypeError, ValueError):
            matches = False
    else:
        matches = actual == expected

    if not matches:
        errors.append(
            "calculation={!r}, fiscal_year={!r}, expected={!r}, actual={!r}".format(
                calculation,
                fiscal_year,
                expected,
                actual,
            )
        )


def _compare_series(errors, covered, calculation, expected_by_year, actual_by_year):
    covered.add(calculation)
    expected_years = set(expected_by_year)
    actual_years = set(actual_by_year)

    for fiscal_year in sorted(expected_years - actual_years):
        _record_error(
            errors,
            calculation,
            fiscal_year,
            expected_by_year[fiscal_year],
            "<missing fiscal year>",
        )
    for fiscal_year in sorted(actual_years - expected_years):
        errors.append(
            "calculation={!r}, fiscal_year={!r}, expected='<absent>', actual={!r}".format(
                calculation,
                fiscal_year,
                actual_by_year[fiscal_year],
            )
        )
    for fiscal_year in sorted(expected_years & actual_years):
        _record_error(
            errors,
            calculation,
            fiscal_year,
            expected_by_year[fiscal_year],
            actual_by_year[fiscal_year],
        )


def _column_by_year(frame, column):
    return frame.set_index("Fiscal Year")[column].to_dict()


def test_every_production_calculation_matches_task_99() -> None:
    fixed = MANUAL_VERIFIED_ANSWER_SHEET["calculated_financial_metrics"]
    errors = []
    covered = set()

    growth = fixed["growth_and_accrual_metrics"]["expected_result"]
    growth_sources = (
        ("Revenue Growth", "revenue_growth", revenue_growth_df, "Result"),
        ("Net Income Growth", "net_income_growth", net_income_growth_df, "NI Growth Result"),
        ("OCF Growth", "ocf_growth", ocf_growth_df, "OCF Growth Result"),
        ("AR Growth", "ar_growth", ar_growth_df, "AR Growth Result"),
        (
            "AR vs Revenue Gap",
            "ar_revenue_gap",
            ar_growth_df,
            "Difference: AR Growth minus Revenue Growth",
        ),
    )
    for calculation, expected_field, frame, actual_column in growth_sources:
        _compare_series(
            errors,
            covered,
            calculation,
            {year: values[expected_field] for year, values in growth.items()},
            _column_by_year(frame, actual_column),
        )

    da_expected = fixed["da"]["expected_result"]
    for calculation, expected_field, actual_column in (
        ("D&A Growth", "da_growth", "D&A Growth"),
        ("D&A / Revenue", "da_to_revenue", "D&A / Revenue"),
    ):
        _compare_series(
            errors,
            covered,
            calculation,
            {year: values[expected_field] for year, values in da_expected.items()},
            _column_by_year(da_analysis_df, actual_column),
        )

    capex_expected = fixed["capex"]["expected_result"]
    for calculation, expected_field, actual_column in (
        ("CapEx Growth", "capex_growth", "CapEx Growth"),
        ("CapEx / Revenue", "capex_to_revenue", "CapEx / Revenue"),
        ("CapEx / D&A", "capex_to_da", "CapEx / D&A"),
    ):
        _compare_series(
            errors,
            covered,
            calculation,
            {year: values[expected_field] for year, values in capex_expected.items()},
            _column_by_year(capex_analysis_df, actual_column),
        )

    _compare_series(
        errors,
        covered,
        "Free Cash Flow",
        fixed["free_cash_flow"]["expected_result"],
        _column_by_year(free_cash_flow_df, "Free Cash Flow"),
    )

    movement_expected = fixed["working_capital"]["expected_result"]
    movement_by_metric = working_capital_movements_df.set_index(
        ["Fiscal Year", "Metric"]
    )["Change"]
    for calculation, expected_field, metric in (
        ("AR Change", "ar_change", "Accounts Receivable"),
        ("Inventory Change", "inventory_change", "Inventory"),
        ("AP Change", "ap_change", "Accounts Payable"),
    ):
        _compare_series(
            errors,
            covered,
            calculation,
            {year: values[expected_field] for year, values in movement_expected.items()},
            {
                year: value
                for (year, row_metric), value in movement_by_metric.items()
                if row_metric == metric
            },
        )

    _compare_series(
        errors,
        covered,
        "Net Working-Capital Cash Effect",
        {
            year: values["net_working_capital_cash_effect"]
            for year, values in movement_expected.items()
        },
        _column_by_year(
            working_capital_analysis_df, "Net Working-Capital Cash Effect"
        ),
    )

    inventory_ap_expected = fixed["inventory_and_ap_growth"]["expected_result"]
    _compare_series(
        errors,
        covered,
        "Inventory Growth",
        {
            year: values["inventory_growth"]
            for year, values in inventory_ap_expected.items()
        },
        _column_by_year(inventory_warning_df, "Inventory Growth"),
    )
    _compare_series(
        errors,
        covered,
        "AP Growth",
        {
            year: values["ap_growth"]
            for year, values in inventory_ap_expected.items()
        },
        _column_by_year(ap_warning_df, "AP Growth"),
    )

    sbc_expected = fixed["sbc_and_shares"]["expected_result"]
    for calculation, expected_field, actual_column in (
        ("SBC / Revenue", "sbc_to_revenue", "SBC / Revenue"),
        ("SBC / OCF", "sbc_to_ocf", "SBC / OCF"),
        ("SBC / Net Income", "sbc_to_net_income", "SBC / Net Income"),
    ):
        _compare_series(
            errors,
            covered,
            calculation,
            {year: values[expected_field] for year, values in sbc_expected.items()},
            _column_by_year(sbc_analysis_df, actual_column),
        )

    _compare_series(
        errors,
        covered,
        "Shares Outstanding Growth",
        {year: values["shares_growth"] for year, values in sbc_expected.items()},
        _column_by_year(share_dilution_df, "Shares Outstanding Growth"),
    )
    _compare_series(
        errors,
        covered,
        "Net Share Effect",
        {year: values["net_share_effect"] for year, values in sbc_expected.items()},
        _column_by_year(buyback_adjustment_df, "Net Share Effect"),
    )
    _compare_series(
        errors,
        covered,
        "Buyback Offset Ratio",
        {
            year: values["buyback_offset_ratio"]
            for year, values in sbc_expected.items()
        },
        _column_by_year(buyback_adjustment_df, "Buyback Offset Ratio"),
    )

    tax_expected = fixed["deferred_taxes"]["expected_result"]
    for calculation, expected_field, frame, actual_column in (
        ("DTA / Net Income", "dta_to_net_income", dta_analysis_df, "DTA / Net Income"),
        ("DTA Growth", "dta_growth", dta_analysis_df, "DTA Growth"),
        ("DTL Growth", "dtl_growth", dtl_analysis_df, "DTL Growth"),
    ):
        _compare_series(
            errors,
            covered,
            calculation,
            {year: values[expected_field] for year, values in tax_expected.items()},
            _column_by_year(frame, actual_column),
        )

    assert covered == EXPECTED_CALCULATIONS, (
        f"Calculation coverage mismatch: expected={sorted(EXPECTED_CALCULATIONS)!r}, "
        f"actual={sorted(covered)!r}"
    )
    assert not errors, "Calculation accuracy mismatches:\n" + "\n".join(errors)


if __name__ == "__main__":
    tests = [
        value
        for name, value in globals().copy().items()
        if name.startswith("test_")
    ]
    for test in tests:
        test()
    print("Task 101 calculation accuracy tests passed")
