import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress output produced by the existing calculation modules during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.ocf_growth import ocf_growth_df
    from Calculations.revenue_growth import revenue_growth_df
    from Calculations.working_capital_movements import (
        working_capital_movements_df,
    )


required_years = [2023, 2024, 2025]
payment_pressure_rule = (
    "AP Growth - Revenue Growth >= 10 percentage points AND OCF Growth < 0"
)
supplier_financing_rule = "AP Growth > Revenue Growth AND OCF Growth >= 0"
no_rule_triggered = "Neither AP rule triggered"

ap_movements = working_capital_movements_df.loc[
    working_capital_movements_df["Metric"] == "Accounts Payable"
].set_index("Fiscal Year")
revenue_growth_by_year = revenue_growth_df.set_index("Fiscal Year")["Result"]
ocf_growth_by_year = ocf_growth_df.set_index("Fiscal Year")[
    "OCF Growth Result"
]

calculation_records = []

for fiscal_year in required_years:
    current_ap = ap_movements.loc[fiscal_year, "Current Year Value"]
    previous_ap = ap_movements.loc[fiscal_year, "Previous Year Value"]
    ap_growth = (current_ap - previous_ap) / previous_ap
    revenue_growth = revenue_growth_by_year.loc[fiscal_year]
    ap_minus_revenue_growth = ap_growth - revenue_growth
    ocf_growth = ocf_growth_by_year.loc[fiscal_year]

    if ap_minus_revenue_growth >= 0.10 and ocf_growth < 0:
        exact_rule_triggered = payment_pressure_rule
        classification = "Possible payment pressure"
    elif ap_growth > revenue_growth and ocf_growth >= 0:
        exact_rule_triggered = supplier_financing_rule
        classification = "Normal supplier financing pattern"
    else:
        exact_rule_triggered = no_rule_triggered
        classification = "No AP concern triggered"

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "Current Year AP": current_ap,
            "Previous Year AP": previous_ap,
            "AP Growth": ap_growth,
            "AP Growth Percentage": f"{ap_growth:.2%}",
            "Revenue Growth": revenue_growth,
            "Revenue Growth Percentage": f"{revenue_growth:.2%}",
            "AP minus Revenue Growth": ap_minus_revenue_growth,
            "Difference Percentage Points": f"{ap_minus_revenue_growth:.2%}",
            "OCF Growth": ocf_growth,
            "OCF Growth Percentage": f"{ocf_growth:.2%}",
            "Liquidity Data": "Not available",
            "Exact Rule Triggered": exact_rule_triggered,
            "Classification": classification,
        }
    )

ap_warning_df = pd.DataFrame(calculation_records)
triggered_ap_rules_df = ap_warning_df.loc[
    ap_warning_df["Classification"].isin(
        [
            "Possible payment pressure",
            "Normal supplier financing pattern",
        ]
    )
].copy()

print(ap_warning_df.to_string(index=False))
print("\nTriggered AP classifications:")
print(triggered_ap_rules_df.to_string(index=False))

expected_classifications = {
    2023: "No AP concern triggered",
    2024: "Normal supplier financing pattern",
    2025: "No AP concern triggered",
}

validation_passed = (
    len(ap_warning_df) == 3
    and ap_warning_df["Fiscal Year"].tolist() == required_years
    and (ap_warning_df["Liquidity Data"] == "Not available").all()
    and all(
        row["Classification"]
        == expected_classifications[row["Fiscal Year"]]
        for _, row in ap_warning_df.iterrows()
    )
    and not (
        ap_warning_df["Classification"] == "Possible payment pressure"
    ).any()
)

if validation_passed:
    print("AP warning rules validated successfully")
else:
    print("AP warning rules validation failed")
