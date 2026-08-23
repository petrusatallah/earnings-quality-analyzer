import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Reuse the established DTA rule results and the existing DTA/DTL balances.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.dta_analysis import dta_analysis_df, exact_rule as dta_risk_rule
    from Analysis.dtl_analysis import dtl_analysis_df


REQUIRED_YEARS = [2023, 2024, 2025]
MOVEMENT_THRESHOLD = 0.25
MOVEMENT_RULE = "abs(DTA Growth) >= 25% OR abs(DTL Growth) >= 25%"


def calculate_growth(current_value, previous_value):
    if pd.isna(current_value) or pd.isna(previous_value) or previous_value == 0:
        return None
    return (current_value - previous_value) / abs(previous_value)


def classify_dta_risk(dta_ratio, net_income_growth, net_income):
    large_dta = dta_ratio is not None and dta_ratio >= 0.50
    weak_profitability = (
        net_income_growth is not None and net_income_growth <= -0.10
    )
    negative_profitability = net_income <= 0
    return bool(large_dta and (weak_profitability or negative_profitability))


def classify_overall(dta_risk_flag, movement_flag):
    if dta_risk_flag and movement_flag:
        return "Strong tax-accounting review signal", "High"
    if dta_risk_flag or movement_flag:
        return "Tax items require investigation", "Medium"
    return "No tax red flag", "None"


dta_by_year = dta_analysis_df.set_index("Fiscal Year")
dtl_by_year = dtl_analysis_df.set_index("Fiscal Year")
analysis_rows = []

for fiscal_year in REQUIRED_YEARS:
    dta = dta_by_year.loc[fiscal_year]
    dtl = dtl_by_year.loc[fiscal_year]
    previous_dta = dta_by_year.loc[fiscal_year - 1, "DTA"]
    previous_dtl = dtl_by_year.loc[fiscal_year - 1, "DTL"]

    dta_growth = calculate_growth(dta["DTA"], previous_dta)
    dtl_growth = calculate_growth(dtl["DTL"], previous_dtl)
    dta_movement_trigger = bool(
        dta_growth is not None and abs(dta_growth) >= MOVEMENT_THRESHOLD
    )
    dtl_movement_trigger = bool(
        dtl_growth is not None and abs(dtl_growth) >= MOVEMENT_THRESHOLD
    )
    movement_flag = dta_movement_trigger or dtl_movement_trigger

    if dta_movement_trigger and dtl_movement_trigger:
        movement_classification = "Large DTA and DTL movements"
    elif dta_movement_trigger:
        movement_classification = "Large DTA movement"
    elif dtl_movement_trigger:
        movement_classification = "Large DTL movement"
    else:
        movement_classification = "No unusual deferred-tax movement"

    dta_risk_flag = dta["Status"] == "Needs investigation"
    tax_signal, overall_severity = classify_overall(
        dta_risk_flag, movement_flag
    )

    explanations = []
    if dta_risk_flag:
        explanations.append(
            "Deferred tax assets are large relative to net income while "
            "profitability is weak or negative under the existing rule; "
            "recoverability requires investigation."
        )
    if dta_movement_trigger:
        explanations.append(
            "Deferred tax assets changed by at least 25% year over year; the "
            "underlying tax-note drivers require review."
        )
    if dtl_movement_trigger:
        explanations.append(
            "Deferred tax liabilities changed by at least 25% year over year; the "
            "underlying tax-note drivers require review."
        )
    if not explanations:
        explanations.append("Existing tax red-flag rules did not trigger.")

    analysis_rows.append(
        {
            "Fiscal Year": fiscal_year,
            "Deferred Tax Assets": dta["DTA"],
            "Deferred Tax Liabilities": dtl["DTL"],
            "Net Income": dta["Net Income"],
            "Net Income Growth": dta["Net Income Growth"],
            "DTA / Net Income": dta["DTA / Net Income"],
            "DTA / Net Income Display": dta["DTA / Net Income Percentage"],
            "DTA Risk Rule": dta_risk_rule,
            "DTA Risk Flag": dta_risk_flag,
            "DTA Result": "Flag" if dta_risk_flag else "No Flag",
            "DTA Severity": "Medium" if dta_risk_flag else "None",
            "DTA Growth": dta_growth,
            "DTA Growth Display": (
                "N/A" if dta_growth is None else f"{dta_growth:.2%}"
            ),
            "DTL Growth": dtl_growth,
            "DTL Growth Display": (
                "N/A" if dtl_growth is None else f"{dtl_growth:.2%}"
            ),
            "Deferred Tax Movement Rule": MOVEMENT_RULE,
            "DTA Movement Trigger": dta_movement_trigger,
            "DTL Movement Trigger": dtl_movement_trigger,
            "Deferred Tax Movement Flag": movement_flag,
            "Deferred Tax Movement Classification": movement_classification,
            "Deferred Tax Movement Result": (
                "Review" if movement_flag else "No Flag"
            ),
            "Deferred Tax Movement Severity": (
                "Medium" if movement_flag else "None"
            ),
            "Tax Signal": tax_signal,
            "Overall Tax Severity": overall_severity,
            "Explanation": " ".join(explanations),
        }
    )


tax_red_flags_df = pd.DataFrame(analysis_rows)
tax_attention_df = tax_red_flags_df.loc[
    tax_red_flags_df["Overall Tax Severity"] != "None"
].copy()


validation_errors = []
if len(tax_red_flags_df) != 3:
    validation_errors.append("The analysis must contain exactly three rows")
if tax_red_flags_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("Fiscal years must be 2023, 2024, and 2025")
if dta_risk_rule != (
    "DTA / |Net Income| >= 50% AND "
    "(NI Growth <= -10% OR Net Income <= 0)"
):
    validation_errors.append("The existing Task 19 DTA rule was changed")
if MOVEMENT_THRESHOLD != 0.25:
    validation_errors.append("The deferred-tax movement threshold must remain 25%")
if not (
    abs(-0.25) >= MOVEMENT_THRESHOLD and abs(0.25) >= MOVEMENT_THRESHOLD
):
    validation_errors.append("The movement threshold must use absolute growth")

by_year = tax_red_flags_df.set_index("Fiscal Year")
for fiscal_year in REQUIRED_YEARS:
    if abs(by_year.loc[fiscal_year, "DTA Growth"] - dta_by_year.loc[fiscal_year, "DTA Growth"]) > 1e-12:
        validation_errors.append(f"DTA growth does not match for {fiscal_year}")
    if abs(by_year.loc[fiscal_year, "DTL Growth"] - dtl_by_year.loc[fiscal_year, "DTL Growth"]) > 1e-12:
        validation_errors.append(f"DTL growth does not match for {fiscal_year}")

expected_2023_dta_growth = (24369 - 20094) / abs(20094)
expected_2023_dtl_growth = (7118 - 5557) / abs(5557)
if abs(by_year.loc[2023, "DTA Growth"] - expected_2023_dta_growth) > 1e-12:
    validation_errors.append("The 2023 DTA growth must be about 21.28%")
if abs(by_year.loc[2023, "DTL Growth"] - expected_2023_dtl_growth) > 1e-12:
    validation_errors.append("The 2023 DTL growth must be about 28.09%")
if not by_year.loc[2023, "DTL Movement Trigger"]:
    validation_errors.append("The 2023 DTL movement must trigger")
if by_year.loc[2023, "Overall Tax Severity"] != "Medium":
    validation_errors.append("The 2023 overall tax severity must be Medium")
if by_year.loc[2024, "Overall Tax Severity"] != "None":
    validation_errors.append("2024 must have no tax trigger")
if by_year.loc[2025, "Overall Tax Severity"] != "None":
    validation_errors.append("2025 must have no tax trigger")

temporary_dta_risk = classify_dta_risk(0.60, -0.15, 100.0)
if not temporary_dta_risk:
    validation_errors.append("The temporary DTA-risk test did not trigger")
temporary_signal, temporary_severity = classify_overall(True, True)
if not (
    temporary_signal == "Strong tax-accounting review signal"
    and temporary_severity == "High"
):
    validation_errors.append("The temporary combined test did not produce High")
if tax_attention_df["Fiscal Year"].tolist() != [2023]:
    validation_errors.append("Only 2023 may appear in the attention table")
if not dta_analysis_df["Taxable Income Data"].eq("Not available").all():
    validation_errors.append("Taxable income must not be inferred from Net Income")

display_df = tax_red_flags_df.copy()
display_df["Net Income Growth"] = display_df["Net Income Growth"].map(
    lambda value: f"{value:.2%}"
)

print("Tax red-flag analysis:")
print(display_df.to_string(index=False))
print("\nYears requiring attention:")
print(
    display_df.loc[display_df["Overall Tax Severity"] != "None"].to_string(
        index=False
    )
)

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Tax red flags validated successfully")
