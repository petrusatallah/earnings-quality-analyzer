import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# The existing dataset prints its own verification output when imported.
# Suppress that output here so this script prints only the Task 4 results.
with contextlib.redirect_stdout(io.StringIO()):
    from Data.apple_test_dataset import apple_financial_data_df


revenue_data = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Revenue",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

calculation_records = []

for fiscal_year in [2023, 2024, 2025]:
    current_year_revenue = revenue_data.loc[fiscal_year]
    previous_year_revenue = revenue_data.loc[fiscal_year - 1]
    result = (
        current_year_revenue - previous_year_revenue
    ) / previous_year_revenue

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "Metric": "Revenue Growth",
            "Current Year Revenue": current_year_revenue,
            "Previous Year Revenue": previous_year_revenue,
            "Formula": (
                f"({current_year_revenue:g} - {previous_year_revenue:g}) "
                f"/ {previous_year_revenue:g}"
            ),
            "Result": result,
        }
    )

revenue_growth_df = pd.DataFrame(calculation_records)
print_table = revenue_growth_df.copy()
print_table["Percentage Result"] = print_table["Result"].map(
    lambda value: f"{value:.2%}"
)

print(print_table.to_string(index=False))

expected_results = {
    2023: -0.028004605303199367,
    2024: 0.020219940775141214,
    2025: 0.0642551178283274,
}
validation_tolerance = 1e-12

validation_passed = all(
    abs(row["Result"] - expected_results[row["Fiscal Year"]])
    <= validation_tolerance
    for row in calculation_records
)

if validation_passed:
    print("Revenue growth calculations validated successfully")
else:
    print("Revenue growth calculation validation failed")
