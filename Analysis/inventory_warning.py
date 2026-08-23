import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress output produced by the existing modules during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Data.apple_test_dataset import apple_financial_data_df
    from Calculations.revenue_growth import revenue_growth_df


required_years = [2023, 2024, 2025]
rule_name = "Inventory Growth vs Revenue Growth"
exact_rule = "Inventory Growth - Revenue Growth >= 10 percentage points"
rule_threshold = 0.10

inventory_data = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Inventory",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

revenue_growth_by_year = revenue_growth_df.set_index("Fiscal Year")["Result"]
calculation_records = []

for fiscal_year in required_years:
    current_inventory = inventory_data.loc[fiscal_year]
    previous_inventory = inventory_data.loc[fiscal_year - 1]
    inventory_growth = (
        current_inventory - previous_inventory
    ) / previous_inventory
    revenue_growth = revenue_growth_by_year.loc[fiscal_year]
    difference = inventory_growth - revenue_growth

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "Current Year Inventory": current_inventory,
            "Previous Year Inventory": previous_inventory,
            "Inventory Growth": inventory_growth,
            "Inventory Growth Percentage": f"{inventory_growth:.2%}",
            "Revenue Growth": revenue_growth,
            "Revenue Growth Percentage": f"{revenue_growth:.2%}",
            "Difference": difference,
            "Difference Percentage Points": f"{difference:.2%}",
            "Exact Rule": exact_rule,
            "Flag": bool(difference >= rule_threshold),
        }
    )

inventory_warning_df = pd.DataFrame(calculation_records)
triggered_inventory_flags_df = inventory_warning_df.loc[
    inventory_warning_df["Flag"]
].copy()

print(inventory_warning_df.to_string(index=False))
print("\nTriggered flags:")
print(triggered_inventory_flags_df.to_string(index=False))

expected_flags = {2023: True, 2024: True, 2025: False}
validation_tolerance = 1e-12

validation_passed = (
    len(inventory_warning_df) == 3
    and inventory_warning_df["Fiscal Year"].tolist() == required_years
    and all(
        abs(
            row["Difference"]
            - (row["Inventory Growth"] - row["Revenue Growth"])
        )
        <= validation_tolerance
        for _, row in inventory_warning_df.iterrows()
    )
    and all(
        row["Flag"] == expected_flags[row["Fiscal Year"]]
        and row["Flag"]
        == bool(row["Difference"] + validation_tolerance >= rule_threshold)
        for _, row in inventory_warning_df.iterrows()
    )
)

if validation_passed:
    print("Inventory warning rules validated successfully")
else:
    print("Inventory warning rules validation failed")
