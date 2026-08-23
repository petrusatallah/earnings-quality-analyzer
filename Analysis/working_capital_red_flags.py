import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Reuse the existing rule outputs, rule text, and working-capital calculation.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.ap_warning import (
        ap_warning_df,
        payment_pressure_rule,
        supplier_financing_rule,
    )
    from Analysis.inventory_warning import (
        exact_rule as inventory_rule,
        inventory_warning_df,
        rule_threshold as inventory_threshold,
    )
    from Calculations.working_capital_analysis import (
        working_capital_analysis_df,
    )


REQUIRED_YEARS = [2023, 2024, 2025]
AP_RULE = (
    f"Possible payment pressure: {payment_pressure_rule}; "
    f"Normal supplier financing pattern: {supplier_financing_rule}"
)
SEVERITY_PRIORITY = {"None": 0, "Low": 1, "Medium": 2}


inventory_by_year = inventory_warning_df.set_index("Fiscal Year")
ap_by_year = ap_warning_df.set_index("Fiscal Year")
cash_effect_by_year = working_capital_analysis_df.set_index("Fiscal Year")
analysis_rows = []

for fiscal_year in REQUIRED_YEARS:
    inventory = inventory_by_year.loc[fiscal_year]
    ap = ap_by_year.loc[fiscal_year]
    cash_effect = cash_effect_by_year.loc[fiscal_year]

    inventory_flag = bool(inventory["Flag"])
    inventory_result = "Flag" if inventory_flag else "No Flag"
    inventory_severity = "Medium" if inventory_flag else "None"

    ap_classification = ap["Classification"]
    if ap_classification == "Possible payment pressure":
        ap_result = "Flag"
        ap_severity = "Medium"
    elif ap_classification == "Normal supplier financing pattern":
        ap_result = "Review"
        ap_severity = "Low"
    else:
        ap_result = "No Flag"
        ap_severity = "None"

    net_cash_effect = cash_effect["Net Working-Capital Cash Effect"]
    working_capital_cash_use = bool(net_cash_effect < 0)
    if net_cash_effect < 0:
        wc_classification = (
            "Selected-account working-capital proxy suggests a cash use"
        )
        wc_result = "Review"
        wc_severity = "Low"
    elif net_cash_effect > 0:
        wc_classification = (
            "Selected-account working-capital proxy suggests a cash benefit"
        )
        wc_result = "No Flag"
        wc_severity = "None"
    else:
        wc_classification = (
            "Selected-account working-capital proxy suggests no cash use or benefit"
        )
        wc_result = "No Flag"
        wc_severity = "None"

    severities = [inventory_severity, ap_severity, wc_severity]
    overall_severity = max(severities, key=SEVERITY_PRIORITY.get)
    signal_by_severity = {
        "Medium": "Working-capital warning",
        "Low": "Working capital requires review",
        "None": "No working-capital warning",
    }

    explanations = []
    if inventory_flag:
        explanations.append(
            "Inventory growth exceeded revenue growth by the existing threshold; "
            "inventory build-up requires investigation."
        )
    if ap_classification == "Possible payment pressure":
        explanations.append(
            "Accounts payable grew materially faster than revenue while operating "
            "cash flow declined; payment pressure may require investigation."
        )
    elif ap_classification == "Normal supplier financing pattern":
        explanations.append(
            "Accounts payable grew faster than revenue while operating cash flow "
            "remained positive; the existing rule classifies this as a "
            "supplier-financing pattern for review."
        )
    if working_capital_cash_use:
        explanations.append(
            "The selected-account working-capital proxy suggests a cash use based "
            "on accounts receivable, inventory, and accounts payable; the cause "
            "should be reviewed. Other working-capital accounts, "
            "acquisitions, foreign exchange, and non-cash effects may cause this "
            "proxy to differ from the cash-flow statement."
        )
    else:
        explanations.append(
            f"{wc_classification}. Other working-capital accounts, acquisitions, "
            "foreign exchange, and non-cash effects may cause this proxy to differ "
            "from the cash-flow statement."
        )
    if not explanations:
        explanations.append("Existing working-capital rules did not trigger.")

    analysis_rows.append(
        {
            "Fiscal Year": fiscal_year,
            "Inventory Growth": inventory["Inventory Growth"],
            "Revenue Growth": inventory["Revenue Growth"],
            "Inventory Revenue Gap": inventory["Difference"],
            "Inventory Revenue Gap Display": (
                f"{inventory['Difference'] * 100:.2f}pp"
            ),
            "Inventory Rule": inventory_rule,
            "Inventory Flag": inventory_flag,
            "Inventory Result": inventory_result,
            "Inventory Severity": inventory_severity,
            "AP Growth": ap["AP Growth"],
            "OCF Growth": ap["OCF Growth"],
            "AP Revenue Gap": ap["AP minus Revenue Growth"],
            "AP Revenue Gap Display": (
                f"{ap['AP minus Revenue Growth'] * 100:.2f}pp"
            ),
            "AP Rule": AP_RULE,
            "AP Classification": ap_classification,
            "AP Result": ap_result,
            "AP Severity": ap_severity,
            "AR Change": cash_effect["AR Change"],
            "Inventory Change": cash_effect["Inventory Change"],
            "AP Change": cash_effect["AP Change"],
            "Net Working Capital Cash Effect": net_cash_effect,
            "WC Calculation": (
                f"-{cash_effect['AR Change']:g} - "
                f"{cash_effect['Inventory Change']:g} + "
                f"{cash_effect['AP Change']:g} = {net_cash_effect:g}"
            ),
            "Working Capital Cash Use": working_capital_cash_use,
            "WC Classification": wc_classification,
            "WC Result": wc_result,
            "WC Severity": wc_severity,
            "Working Capital Signal": signal_by_severity[overall_severity],
            "Overall Severity": overall_severity,
            "Explanation": " ".join(explanations),
        }
    )


working_capital_red_flags_df = pd.DataFrame(analysis_rows)
working_capital_attention_df = working_capital_red_flags_df.loc[
    working_capital_red_flags_df["Overall Severity"] != "None"
].copy()


validation_errors = []
if len(working_capital_red_flags_df) != 3:
    validation_errors.append("The analysis must contain exactly three rows")
if working_capital_red_flags_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("Fiscal years must be 2023, 2024, and 2025")
if inventory_threshold != 0.10 or inventory_rule != (
    "Inventory Growth - Revenue Growth >= 10 percentage points"
):
    validation_errors.append("The existing inventory threshold was changed")
if payment_pressure_rule != (
    "AP Growth - Revenue Growth >= 10 percentage points AND OCF Growth < 0"
) or supplier_financing_rule != (
    "AP Growth > Revenue Growth AND OCF Growth >= 0"
):
    validation_errors.append("The existing AP rules were changed")

source_cash_effects = working_capital_analysis_df.set_index("Fiscal Year")[
    "Net Working-Capital Cash Effect"
]
output_cash_effects = working_capital_red_flags_df.set_index("Fiscal Year")[
    "Net Working Capital Cash Effect"
]
if not output_cash_effects.equals(source_cash_effects):
    validation_errors.append(
        "Working-capital cash effects do not match the existing module"
    )

by_year = working_capital_red_flags_df.set_index("Fiscal Year")
expected_cash_effects = {2023: -4213, 2024: 1492, 2025: -3899}
if output_cash_effects.to_dict() != expected_cash_effects:
    validation_errors.append("Apple working-capital cash effects are unexpected")
if by_year.loc[2023, "Inventory Severity"] != "Medium":
    validation_errors.append("2023 inventory severity must be Medium")
if by_year.loc[2024, "Inventory Severity"] != "Medium":
    validation_errors.append("2024 inventory severity must be Medium")
if not (
    by_year.loc[2024, "AP Result"] == "Review"
    and by_year.loc[2024, "AP Severity"] == "Low"
):
    validation_errors.append("2024 AP must be Review / Low")
if not (
    by_year.loc[2025, "WC Result"] == "Review"
    and by_year.loc[2025, "WC Severity"] == "Low"
):
    validation_errors.append("2025 working-capital cash use must be Review / Low")
severity_columns = [
    "Inventory Severity",
    "AP Severity",
    "WC Severity",
    "Overall Severity",
]
if working_capital_red_flags_df[severity_columns].eq("High").any().any():
    validation_errors.append("Task 32 must not create High severity")
if working_capital_attention_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("All three Apple years must appear in the review table")

display_df = working_capital_red_flags_df.copy()
for column in [
    "Inventory Growth",
    "Revenue Growth",
    "AP Growth",
    "OCF Growth",
]:
    display_df[column] = display_df[column].map(lambda value: f"{value:.2%}")

print("Working-capital red-flag analysis:")
print(display_df.to_string(index=False))
print("\nYears requiring attention:")
print(
    display_df.loc[display_df["Overall Severity"] != "None"].to_string(
        index=False
    )
)

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Working-capital red flags validated successfully")
