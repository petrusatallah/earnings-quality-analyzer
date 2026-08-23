"""Task 102: verify every Task 99 red-flag rule and severity output."""

import contextlib
import io
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.accrual_red_flags import accrual_red_flags_df
    from Analysis.capex_rule import capex_rule_df
    from Analysis.normalization_red_flags import normalization_red_flags_df
    from Analysis.red_flag_table import (
        REQUIRED_YEARS,
        RULE_AGGREGATION_MAPPING,
        red_flag_table_df,
    )
    from Analysis.sbc_red_flags import BUYBACK_OFFSET_RULE, sbc_red_flags_df
    from Analysis.severity_system import (
        benchmark_severity_df,
        fiscal_year_severity_summary_df,
    )
    from Analysis.tax_red_flags import tax_red_flags_df
    from Analysis.working_capital_red_flags import working_capital_red_flags_df

from Data.manual_verified_answer_sheet import MANUAL_VERIFIED_ANSWER_SHEET


def _compare(errors, area, year, field, expected, actual):
    if actual != expected:
        errors.append(
            "area={!r}, fiscal_year={!r}, field={!r}, expected={!r}, actual={!r}".format(
                area, year, field, expected, actual
            )
        )


def test_every_red_flag_rule_and_severity_matches_task_99() -> None:
    fixed = MANUAL_VERIFIED_ANSWER_SHEET["red_flag_results"]
    errors = []

    accrual = accrual_red_flags_df.set_index("Fiscal Year")
    accrual_fields = {
        "ar_flag": "AR Flag",
        "ni_ocf_flag": "NI OCF Flag",
        "combined_accrual_flag": "Combined Accrual Flag",
        "signal": "Accrual Signal",
        "severity": "Severity",
    }
    for year, expected in fixed["accrual_quality"]["expected_result"].items():
        for expected_field, actual_field in accrual_fields.items():
            _compare(errors, "accrual_quality", year, expected_field, expected[expected_field], accrual.loc[year, actual_field])
        _compare(errors, "accrual_quality", year, "ar_rule", fixed["accrual_quality"]["formula_or_rule"]["ar"], accrual.loc[year, "AR Rule"])
        _compare(errors, "accrual_quality", year, "ni_ocf_rule", fixed["accrual_quality"]["formula_or_rule"]["ni_ocf"], accrual.loc[year, "NI OCF Rule"])
        _compare(
            errors,
            "accrual_quality",
            year,
            "combined_rule_result",
            expected["combined_accrual_flag"],
            bool(accrual.loc[year, "AR Flag"] and accrual.loc[year, "NI OCF Flag"]),
        )
    _compare(
        errors,
        "accrual_quality",
        "all",
        "combined_rule",
        "AR Flag AND NI OCF Flag",
        fixed["accrual_quality"]["formula_or_rule"]["combined"],
    )

    working = working_capital_red_flags_df.set_index("Fiscal Year")
    working_fields = {
        "inventory_flag": "Inventory Flag",
        "ap_classification": "AP Classification",
        "working_capital_cash_use": "Working Capital Cash Use",
        "overall_severity": "Overall Severity",
    }
    for year, expected in fixed["working_capital"]["expected_result"].items():
        for expected_field, actual_field in working_fields.items():
            _compare(errors, "working_capital", year, expected_field, expected[expected_field], working.loc[year, actual_field])
        _compare(errors, "working_capital", year, "inventory_rule", fixed["working_capital"]["formula_or_rule"]["inventory"], working.loc[year, "Inventory Rule"])
        expected_ap_rule = (
            "Possible payment pressure: "
            + fixed["working_capital"]["formula_or_rule"]["ap_payment_pressure"]
            + "; Normal supplier financing pattern: "
            + fixed["working_capital"]["formula_or_rule"]["ap_supplier_financing"]
        )
        _compare(errors, "working_capital", year, "ap_rule", expected_ap_rule, working.loc[year, "AP Rule"])
        if "Working Capital Cash Use" in working.columns:
            _compare(
                errors,
                "working_capital",
                year,
                "cash_use_rule_result",
                expected["working_capital_cash_use"],
                bool(working.loc[year, "Net Working Capital Cash Effect"] < 0),
            )
    if "Working Capital Cash Use" in working.columns:
        _compare(
            errors,
            "working_capital",
            "all",
            "cash_use_rule",
            "Net Working-Capital Cash Effect < 0",
            fixed["working_capital"]["formula_or_rule"]["cash_use"],
        )

    capex = capex_rule_df.set_index("Fiscal Year")
    capex_red = red_flag_table_df.loc[
        red_flag_table_df["Metric"] == "CapEx vs D&A"
    ].set_index("Fiscal Year")
    for year, expected in fixed["capex"]["expected_result"].items():
        _compare(errors, "capex", year, "status", expected["status"], capex.loc[year, "Status"])
        _compare(errors, "capex", year, "rule", fixed["capex"]["formula_or_rule"], capex.loc[year, "Exact Rule"])
    _compare(errors, "capex", "all", "rule_years", set(fixed["capex"]["expected_result"]), set(capex.index))
    _compare(errors, "capex", "consolidated", "fiscal_years", set(REQUIRED_YEARS), set(capex_red.index))
    for year in REQUIRED_YEARS:
        expected = fixed["capex"]["expected_result"][year]
        _compare(errors, "capex", year, "flag", expected["flag"], capex_red.loc[year, "Result"] == "Flag")
        _compare(errors, "capex", year, "severity", expected["severity"], capex_red.loc[year, "Severity"])

    expected_consolidated_metrics = {
        "AR growth vs Revenue growth",
        "Net Income growth vs OCF growth",
        "Inventory growth vs Revenue growth",
        "Accounts Payable pattern",
        "Selected-account working-capital proxy",
        "CapEx vs D&A",
        "Deferred Tax Asset risk",
        "Deferred tax movement",
        "Large SBC",
        "SBC dilution",
        "Buyback offset",
        "Large normalization difference",
        "Repeated one-off items",
    }
    _compare(
        errors,
        "red_flag_table",
        "all",
        "mapping_metrics",
        expected_consolidated_metrics,
        {metric for metric, _ in RULE_AGGREGATION_MAPPING},
    )
    _compare(
        errors,
        "red_flag_table",
        "all",
        "row_count",
        len(REQUIRED_YEARS) * len(expected_consolidated_metrics),
        len(red_flag_table_df),
    )
    metrics_per_year = red_flag_table_df.groupby("Fiscal Year")["Metric"].nunique().to_dict()
    _compare(
        errors,
        "red_flag_table",
        "all",
        "metrics_per_year",
        {year: len(expected_consolidated_metrics) for year in REQUIRED_YEARS},
        metrics_per_year,
    )
    _compare(
        errors,
        "red_flag_table",
        "all",
        "severity_counts",
        {"High": 2, "Medium": 8, "Low": 6, "None": 23},
        red_flag_table_df["Severity"].value_counts().to_dict(),
    )
    duplicate_count = red_flag_table_df.duplicated(
        subset=["Fiscal Year", "Metric"]
    ).sum()
    _compare(errors, "red_flag_table", "all", "duplicate_count", 0, duplicate_count)
    _compare(
        errors,
        "red_flag_table",
        2023,
        "deferred_tax_movement_result",
        "Review",
        red_flag_table_df.set_index(["Fiscal Year", "Metric"]).loc[
            (2023, "Deferred tax movement"), "Result"
        ],
    )
    for year in REQUIRED_YEARS:
        _compare(
            errors,
            "red_flag_table",
            year,
            "large_sbc_result",
            sbc_red_flags_df.set_index("Fiscal Year").loc[year, "Large SBC Result"],
            red_flag_table_df.set_index(["Fiscal Year", "Metric"]).loc[
                (year, "Large SBC"), "Result"
            ],
        )
    consolidated = red_flag_table_df.set_index(["Fiscal Year", "Metric"])
    normalization = normalization_red_flags_df.set_index("Fiscal Year")
    consolidated_sbc = sbc_red_flags_df.set_index("Fiscal Year")
    for year in REQUIRED_YEARS:
        for metric, expected_result, expected_severity in (
            (
                "Selected-account working-capital proxy",
                working.loc[year, "WC Result"],
                working.loc[year, "WC Severity"],
            ),
            (
                "Buyback offset",
                consolidated_sbc.loc[year, "Buyback Offset Result"],
                consolidated_sbc.loc[year, "Buyback Offset Severity"],
            ),
            (
                "Large normalization difference",
                normalization.loc[year, "Large Normalization Difference Result"],
                normalization.loc[year, "Large Normalization Difference Severity"],
            ),
            (
                "Repeated one-off items",
                normalization.loc[year, "Repeated One-Off Result"],
                normalization.loc[year, "Repeated One-Off Severity"],
            ),
        ):
            _compare(
                errors,
                "red_flag_table",
                year,
                f"{metric} result",
                expected_result,
                consolidated.loc[(year, metric), "Result"],
            )
            _compare(
                errors,
                "red_flag_table",
                year,
                f"{metric} severity",
                expected_severity,
                consolidated.loc[(year, metric), "Internal Severity"],
            )

    taxes = tax_red_flags_df.set_index("Fiscal Year")
    tax_fields = {
        "dta_risk_flag": "DTA Risk Flag",
        "deferred_tax_movement_flag": "Deferred Tax Movement Flag",
        "movement_classification": "Deferred Tax Movement Classification",
        "overall_tax_severity": "Overall Tax Severity",
    }
    for year, expected in fixed["deferred_taxes"]["expected_result"].items():
        for expected_field, actual_field in tax_fields.items():
            _compare(errors, "deferred_taxes", year, expected_field, expected[expected_field], taxes.loc[year, actual_field])
        _compare(errors, "deferred_taxes", year, "dta_rule", fixed["deferred_taxes"]["formula_or_rule"]["dta_risk"], taxes.loc[year, "DTA Risk Rule"])
        _compare(errors, "deferred_taxes", year, "movement_rule", fixed["deferred_taxes"]["formula_or_rule"]["movement"], taxes.loc[year, "Deferred Tax Movement Rule"])

    sbc = sbc_red_flags_df.set_index("Fiscal Year")
    sbc_fields = {
        "large_sbc_flag": "Large SBC Flag",
        "dilution_flag": "Dilution Flag",
        "buyback_offset_classification": "Buyback Offset Classification",
        "overall_sbc_severity": "Overall SBC Severity",
    }
    for year, expected in fixed["sbc"]["expected_result"].items():
        for expected_field, actual_field in sbc_fields.items():
            _compare(errors, "sbc", year, expected_field, expected[expected_field], sbc.loc[year, actual_field])
        _compare(errors, "sbc", year, "large_sbc_rule", fixed["sbc"]["formula_or_rule"]["large_sbc"], sbc.loc[year, "Large SBC Rule"])
        _compare(errors, "sbc", year, "dilution_rule", fixed["sbc"]["formula_or_rule"]["dilution"], sbc.loc[year, "Dilution Rule"])
        expected_buyback_flag = expected["buyback_offset_classification"] == (
            "Buybacks more than offset share issuance"
        )
        _compare(
            errors,
            "sbc",
            year,
            "buyback_offset_rule_result",
            expected_buyback_flag,
            sbc.loc[year, "Buyback Offset Flag"],
        )
    expected_buyback_rule = fixed["sbc"]["formula_or_rule"]["buyback_offset"]
    _compare(
        errors,
        "sbc",
        "all",
        "buyback_offset_rule",
        expected_buyback_rule,
        BUYBACK_OFFSET_RULE.split(";", 1)[0],
    )

    severity = fiscal_year_severity_summary_df.set_index("Fiscal Year")
    for year, expected in fixed["overall_severity"]["expected_result"].items():
        if year == "benchmark":
            continue
        _compare(
            errors,
            "overall_severity",
            year,
            "high_level_severity",
            expected["high_level_severity"],
            severity.loc[year, "High-Level Severity"],
        )
        consolidated_year = red_flag_table_df.loc[
            red_flag_table_df["Fiscal Year"].eq(year)
        ]
        for final_severity, count_column in (
            ("Material Concern", "Material Concern Count"),
            ("Needs Investigation", "Needs Investigation Count"),
            ("Low Risk", "Low Risk Count"),
            ("Unavailable", "Unavailable Count"),
        ):
            _compare(
                errors,
                "overall_severity",
                year,
                count_column,
                int(consolidated_year["Final Severity"].eq(final_severity).sum()),
                severity.loc[year, count_column],
            )
        expected_triggered = "; ".join(
            consolidated_year.loc[
                consolidated_year["Result"].isin(("Flag", "Review")), "Metric"
            ].drop_duplicates()
        ) or "None"
        _compare(
            errors,
            "overall_severity",
            year,
            "triggered_metrics",
            expected_triggered,
            severity.loc[year, "Triggered Metrics"],
        )
    benchmark_expected = fixed["overall_severity"]["expected_result"]["benchmark"]["severity"]
    _compare(errors, "overall_severity", "benchmark", "severity", benchmark_expected, benchmark_severity_df.iloc[0]["Benchmark Severity"])

    assert not errors, "Red-flag rule mismatches:\n" + "\n".join(errors)


if __name__ == "__main__":
    test_every_red_flag_rule_and_severity_matches_task_99()
    print("Task 102 red-flag rule tests passed")
