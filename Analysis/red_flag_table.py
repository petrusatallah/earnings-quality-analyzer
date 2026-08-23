import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# The component modules remain authoritative for every rule, result, severity,
# calculation, and explanation aggregated here.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.accrual_red_flags import accrual_red_flags_df
    from Analysis.capex_rule import capex_rule_df
    from Analysis.normalization_red_flags import normalization_red_flags_df
    from Analysis.sbc_red_flags import BUYBACK_OFFSET_RULE, sbc_red_flags_df
    from Analysis.tax_red_flags import tax_red_flags_df
    from Analysis.working_capital_red_flags import working_capital_red_flags_df


REQUIRED_YEARS = [2023, 2024, 2025]
WORKING_CAPITAL_PROXY_RULE = "-AR Change - Inventory Change + AP Change"
INTERNAL_TO_FINAL_SEVERITY = {
    "None": "Low Risk",
    "Low": "Needs Investigation",
    "Medium": "Needs Investigation",
    "High": "Material Concern",
    "Unavailable": "Unavailable",
}
SEVERITY_PRIORITY = {
    "High": 0,
    "Medium": 1,
    "Low": 2,
    "None": 3,
    "Unavailable": 4,
}
REQUIRED_COLUMNS = [
    "Fiscal Year",
    "Metric",
    "Raw Data",
    "Calculation",
    "Rule",
    "Result",
    "Severity",
    "Internal Severity",
    "Final Severity",
    "Explanation",
]


def pct(value):
    if value is None or pd.isna(value):
        return "Unavailable"
    return f"{value:.2%}"


def pp(value):
    if value is None or pd.isna(value):
        return "Unavailable"
    return f"{value * 100:.2f}pp"


def number(value):
    if value is None or pd.isna(value):
        return "Unavailable"
    return f"{value:g}"


def _row(result, severity, *, raw_data, calculation, rule, explanation):
    internal_severity = "Unavailable" if result == "Unavailable" else severity
    return {
        "Raw Data": "Unavailable" if result == "Unavailable" else raw_data,
        "Calculation": "Unavailable" if result == "Unavailable" else calculation,
        "Rule": rule,
        "Result": result,
        # Compatibility field retained for existing consumers.
        "Severity": internal_severity,
        "Internal Severity": internal_severity,
        "Final Severity": INTERNAL_TO_FINAL_SEVERITY[internal_severity],
        "Explanation": explanation,
    }


accrual_by_year = accrual_red_flags_df.set_index("Fiscal Year")
working_capital_by_year = working_capital_red_flags_df.set_index("Fiscal Year")
capex_by_year = capex_rule_df.set_index("Fiscal Year")
tax_by_year = tax_red_flags_df.set_index("Fiscal Year")
sbc_by_year = sbc_red_flags_df.set_index("Fiscal Year")
normalization_by_year = normalization_red_flags_df.set_index("Fiscal Year")


def _ar_growth_rule(fiscal_year):
    source = accrual_by_year.loc[fiscal_year]
    result = "Flag" if source["AR Flag"] else "No Flag"
    severity = source["Severity"] if source["AR Flag"] else "None"
    return _row(
        result,
        severity,
        raw_data=(
            f"AR Growth = {pct(source['AR Growth'])}; "
            f"Revenue Growth = {pct(source['Revenue Growth'])}"
        ),
        calculation=(
            f"{pct(source['AR Growth'])} - {pct(source['Revenue Growth'])} = "
            f"{pp(source['AR Revenue Gap'])}"
        ),
        rule=source["AR Rule"],
        explanation=source["Explanation"],
    )


def _ni_ocf_rule(fiscal_year):
    source = accrual_by_year.loc[fiscal_year]
    result = "Flag" if source["NI OCF Flag"] else "No Flag"
    severity = source["Severity"] if source["NI OCF Flag"] else "None"
    return _row(
        result,
        severity,
        raw_data=(
            f"NI Growth = {pct(source['Net Income Growth'])}; "
            f"OCF Growth = {pct(source['OCF Growth'])}"
        ),
        calculation=(
            f"NI Growth > 0 = {source['Net Income Growth'] > 0}; "
            f"OCF Growth < 0 = {source['OCF Growth'] < 0}"
        ),
        rule=source["NI OCF Rule"],
        explanation=source["Explanation"],
    )


def _inventory_rule(fiscal_year):
    source = working_capital_by_year.loc[fiscal_year]
    return _row(
        source["Inventory Result"],
        source["Inventory Severity"],
        raw_data=(
            f"Inventory Growth = {pct(source['Inventory Growth'])}; "
            f"Revenue Growth = {pct(source['Revenue Growth'])}"
        ),
        calculation=(
            f"{pct(source['Inventory Growth'])} - "
            f"{pct(source['Revenue Growth'])} = "
            f"{source['Inventory Revenue Gap Display']}"
        ),
        rule=source["Inventory Rule"],
        explanation=source["Explanation"],
    )


def _ap_rule(fiscal_year):
    source = working_capital_by_year.loc[fiscal_year]
    return _row(
        source["AP Result"],
        source["AP Severity"],
        raw_data=(
            f"AP Growth = {pct(source['AP Growth'])}; "
            f"Revenue Growth = {pct(source['Revenue Growth'])}; "
            f"OCF Growth = {pct(source['OCF Growth'])}"
        ),
        calculation=(
            f"AP Growth - Revenue Growth = {source['AP Revenue Gap Display']}; "
            f"classification = {source['AP Classification']}"
        ),
        rule=source["AP Rule"],
        explanation=source["Explanation"],
    )


def _working_capital_proxy_rule(fiscal_year):
    source = working_capital_by_year.loc[fiscal_year]
    return _row(
        source["WC Result"],
        source["WC Severity"],
        raw_data=(
            f"AR Change = {number(source['AR Change'])}; "
            f"Inventory Change = {number(source['Inventory Change'])}; "
            f"AP Change = {number(source['AP Change'])}"
        ),
        calculation=source["WC Calculation"],
        rule=WORKING_CAPITAL_PROXY_RULE,
        explanation=source["Explanation"],
    )


def _capex_rule(fiscal_year):
    source = capex_by_year.loc[fiscal_year]
    triggered = source["Status"] == "Needs investigation"
    return _row(
        "Flag" if triggered else "No Flag",
        "Medium" if triggered else "None",
        raw_data=f"CapEx = {number(source['CapEx'])}; D&A = {number(source['D&A'])}",
        calculation=(
            f"{number(source['CapEx'])} / {number(source['D&A'])} = "
            f"{source['CapEx / D&A Display']}"
        ),
        rule=source["Exact Rule"],
        explanation=(
            "CapEx exceeded the existing CapEx/D&A investigation threshold."
            if triggered
            else "Existing rule did not trigger."
        ),
    )


def _dta_rule(fiscal_year):
    source = tax_by_year.loc[fiscal_year]
    return _row(
        source["DTA Result"],
        source["DTA Severity"],
        raw_data=(
            f"DTA = {number(source['Deferred Tax Assets'])}; "
            f"Net Income = {number(source['Net Income'])}; "
            f"NI Growth = {pct(source['Net Income Growth'])}"
        ),
        calculation=(
            f"DTA / |Net Income| = {source['DTA / Net Income Display']}"
        ),
        rule=source["DTA Risk Rule"],
        explanation=source["Explanation"],
    )


def _deferred_tax_movement_rule(fiscal_year):
    source = tax_by_year.loc[fiscal_year]
    return _row(
        source["Deferred Tax Movement Result"],
        source["Deferred Tax Movement Severity"],
        raw_data=(
            f"DTA Growth = {source['DTA Growth Display']}; "
            f"DTL Growth = {source['DTL Growth Display']}"
        ),
        calculation=source["Deferred Tax Movement Classification"],
        rule=source["Deferred Tax Movement Rule"],
        explanation=source["Explanation"],
    )


def _large_sbc_rule(fiscal_year):
    source = sbc_by_year.loc[fiscal_year]
    return _row(
        source["Large SBC Result"],
        source["Large SBC Severity"],
        raw_data=(
            f"SBC = {number(source['SBC'])}; "
            f"Net Income = {number(source['Net Income'])}"
        ),
        calculation=f"SBC / |Net Income| = {source['SBC / Net Income Display']}",
        rule=source["Large SBC Rule"],
        explanation=source["Explanation"],
    )


def _sbc_dilution_rule(fiscal_year):
    source = sbc_by_year.loc[fiscal_year]
    return _row(
        source["Dilution Result"],
        source["Dilution Severity"],
        raw_data=(
            f"Shares Outstanding = {number(source['Shares Outstanding'])}; "
            f"Shares Growth = {source['Shares Outstanding Growth Display']}"
        ),
        calculation=(
            f"Shares Growth {source['Shares Outstanding Growth Display']} >= 1% = "
            f"{source['Dilution Flag']}"
        ),
        rule=source["Dilution Rule"],
        explanation=source["Explanation"],
    )


def _buyback_offset_rule(fiscal_year):
    source = sbc_by_year.loc[fiscal_year]
    return _row(
        source["Buyback Offset Result"],
        source["Buyback Offset Severity"],
        raw_data=(
            f"Shares Issued Net = {number(source['Shares Issued Net'])}; "
            f"Shares Repurchased = {number(source['Shares Repurchased'])}"
        ),
        calculation=source["Buyback Offset Classification"],
        rule=BUYBACK_OFFSET_RULE,
        explanation=source["Explanation"],
    )


def _large_normalization_rule(fiscal_year):
    source = normalization_by_year.loc[fiscal_year]
    return _row(
        source["Large Normalization Difference Result"],
        source["Large Normalization Difference Severity"],
        raw_data=(
            f"Reported Net Income = {number(source['Reported Net Income'])}; "
            f"Normalized Net Income = {number(source['Normalized Net Income'])}"
        ),
        calculation=(
            f"Percentage Difference = {source['Percentage Difference Display']}"
        ),
        rule=source["Large Difference Rule"],
        explanation=source["Explanation"],
    )


def _repeated_one_off_rule(fiscal_year):
    source = normalization_by_year.loc[fiscal_year]
    return _row(
        source["Repeated One-Off Result"],
        source["Repeated One-Off Severity"],
        raw_data=(
            f"Categories identified in {fiscal_year} = "
            f"{source['One-Off Categories Identified']}"
        ),
        calculation=f"Repeated categories = {source['Repeated Categories']}",
        rule=source["Repeated One-Off Rule"],
        explanation=source["Explanation"],
    )


# Explicit one-to-one mapping from each finalized component rule to its
# consolidated metric. Aggregate category signals are intentionally excluded.
RULE_AGGREGATION_MAPPING = (
    ("AR growth vs Revenue growth", _ar_growth_rule),
    ("Net Income growth vs OCF growth", _ni_ocf_rule),
    ("Inventory growth vs Revenue growth", _inventory_rule),
    ("Accounts Payable pattern", _ap_rule),
    ("Selected-account working-capital proxy", _working_capital_proxy_rule),
    ("CapEx vs D&A", _capex_rule),
    ("Deferred Tax Asset risk", _dta_rule),
    ("Deferred tax movement", _deferred_tax_movement_rule),
    ("Large SBC", _large_sbc_rule),
    ("SBC dilution", _sbc_dilution_rule),
    ("Buyback offset", _buyback_offset_rule),
    ("Large normalization difference", _large_normalization_rule),
    ("Repeated one-off items", _repeated_one_off_rule),
)


rows = []
for fiscal_year in REQUIRED_YEARS:
    for metric, builder in RULE_AGGREGATION_MAPPING:
        rows.append(
            {
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                **builder(fiscal_year),
            }
        )


red_flag_table_df = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
red_flag_table_df["_Severity Priority"] = red_flag_table_df[
    "Internal Severity"
].map(SEVERITY_PRIORITY)
red_flag_table_df = (
    red_flag_table_df.sort_values(
        ["Fiscal Year", "_Severity Priority", "Metric"], kind="stable"
    )
    .drop(columns="_Severity Priority")
    .reset_index(drop=True)
)
triggered_red_flags_df = red_flag_table_df.loc[
    red_flag_table_df["Result"].isin(("Flag", "Review"))
].copy()
severity_summary_df = pd.DataFrame(
    {
        "Severity": ["High", "Medium", "Low", "None", "Unavailable"],
        "Count": [
            int(red_flag_table_df["Internal Severity"].eq(severity).sum())
            for severity in ["High", "Medium", "Low", "None", "Unavailable"]
        ],
    }
)


validation_errors = []
if list(red_flag_table_df.columns) != REQUIRED_COLUMNS:
    validation_errors.append("The consolidated table columns are unexpected")
if red_flag_table_df[REQUIRED_COLUMNS].isna().any().any() or (
    red_flag_table_df[REQUIRED_COLUMNS].astype(str).eq("").any().any()
):
    validation_errors.append("Every consolidated row must contain every field")
expected_metrics = {metric for metric, _ in RULE_AGGREGATION_MAPPING}
for fiscal_year in REQUIRED_YEARS:
    year_rows = red_flag_table_df.loc[
        red_flag_table_df["Fiscal Year"].eq(fiscal_year)
    ]
    if len(year_rows) != len(RULE_AGGREGATION_MAPPING):
        validation_errors.append(f"Fiscal year {fiscal_year} has an incorrect row count")
    if set(year_rows["Metric"]) != expected_metrics:
        validation_errors.append(f"Fiscal year {fiscal_year} has a mapping mismatch")
    if year_rows["Metric"].duplicated().any():
        validation_errors.append(f"Fiscal year {fiscal_year} contains duplicate rules")
if not red_flag_table_df["Final Severity"].eq(
    red_flag_table_df["Internal Severity"].map(INTERNAL_TO_FINAL_SEVERITY)
).all():
    validation_errors.append("Final severity does not match internal severity")
if not red_flag_table_df["Severity"].equals(
    red_flag_table_df["Internal Severity"]
):
    validation_errors.append("Compatibility severity differs from internal severity")

print("Complete red-flag table:")
print(red_flag_table_df.to_string(index=False))
print("\nRows requiring attention:")
print(triggered_red_flags_df.to_string(index=False))
print("\nSummary count by Internal Severity:")
print(severity_summary_df.to_string(index=False))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Red-flag table validated successfully")
